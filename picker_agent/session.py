from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from .browser_manager import BrowserManager
from .inspector import CdpInspector, InjectedInspector
from .locator_generator import generate_candidates, redact_text


class AgentSession:
    def __init__(self, session_id: str, emit: Callable[[str, str, dict], Awaitable[None]]) -> None:
        self.session_id, self.emit = session_id, emit
        self.browser = BrowserManager(on_page=self._page_changed)
        self.inspector: CdpInspector | InjectedInspector | None = None
        self.inspector_mode = "cdp"
        self.inspection_active = False

    async def open(self, start_url: str | None) -> None:
        await self.emit("picker.session.accepted", self.session_id, {})
        page = await self.browser.open(start_url)
        self.inspector = CdpInspector(page, self._selected)
        await self.emit("browser.opened", self.session_id, {"url": page.url})

    async def start_inspection(self) -> None:
        if not self.inspector:
            raise RuntimeError("Browser is not ready")
        try:
            await self.inspector.start()
        except Exception:
            await self.inspector.stop()
            self.inspector = InjectedInspector(self.browser.context, self.browser.page, self._selected)  # type: ignore[arg-type]
            self.inspector_mode = "injected"
            await self.inspector.start()
        self.inspection_active = True
        await self.emit("picker.inspect.started", self.session_id, {})

    async def cancel_inspection(self) -> None:
        self.inspection_active = False
        if self.inspector:
            await self.inspector.stop()
        await self.emit("picker.inspect.cancelled", self.session_id, {})

    def _page_changed(self, page: Any) -> None:
        asyncio.create_task(self._handle_page_changed(page))

    async def _handle_page_changed(self, page: Any) -> None:
        await self.emit("browser.page_changed", self.session_id, {"url": page.url, "page_index": max(0, len(self.browser.pages) - 1)})
        if not self.inspection_active:
            return
        if self.inspector:
            await self.inspector.stop()
        self.inspector = CdpInspector(page, self._selected)
        try:
            await self.inspector.start()
            self.inspector_mode = "cdp"
        except Exception:
            self.inspector = InjectedInspector(self.browser.context, page, self._selected)  # type: ignore[arg-type]
            self.inspector_mode = "injected"
            await self.inspector.start()

    async def _selected(self, node: dict[str, Any]) -> None:
        # Selection ends local CDP inspection, but it is not a cancellation:
        # the selected event must arrive while the broker is still in
        # inspection_active so it can transition to element_selected.
        if self.inspector:
            await self.inspector.stop()
        self.inspection_active = False
        page = self.browser.page
        if page is None or page.is_closed():
            await self.emit("picker.error", self.session_id, {"code": "page_closed", "message": "The picker page closed before the element could be validated"})
            return
        frame_id = node.get("picker_frame_id")
        main_frame_id = node.get("picker_main_frame_id")
        if frame_id and main_frame_id and frame_id != main_frame_id:
            await self.emit("picker.error", self.session_id, {"code": "frame_unsupported", "message": "This element is inside a frame; frame-aware locators are not available yet"})
            return
        attributes = dict(zip(node.get("attributes", [])[::2], node.get("attributes", [])[1::2]))
        tag = str(node.get("nodeName", "")).lower()
        metadata = node.get("picker_metadata") if isinstance(node.get("picker_metadata"), dict) else {}
        metadata = {"tag_name": metadata.get("tag_name") or tag, "attributes": metadata.get("attributes") or attributes, "text": redact_text(metadata.get("text") or node.get("nodeValue")), "role": metadata.get("role"), "name": metadata.get("name"), "label": metadata.get("label")}
        candidates = generate_candidates(metadata)
        if not candidates:
            await self.emit("picker.error", self.session_id, {"code": "no_supported_locator", "message": "No supported locator candidates were found. Choose a different element or try again.", "recoverable": True})
            return
        validated = []
        try:
            for candidate in candidates:
                count = await self._count(candidate.locator)
                if count == 1:
                    validated.append((candidate, count))
        except Exception:
            await self.emit("picker.error", self.session_id, {"code": "page_closed", "message": "The picker page changed or closed before the locator could be validated"})
            return
        if not validated:
            await self.emit("picker.error", self.session_id, {"code": "no_unique_locator", "message": "No unique supported locator could be validated. Choose a different element or try again.", "recoverable": True})
            return
        # Every candidate originates from CDP's selected backend node and must
        # resolve uniquely through the same Playwright locator APIs as the runner.
        preferred, count = validated[0]
        await self.emit("picker.element.selected", self.session_id, {"page": {"url": self.browser.page.url if self.browser.page else "", "title": await self.browser.page.title() if self.browser.page else ""}, "element": {"tag_name": metadata["tag_name"], "text": metadata["text"], "role": metadata["role"], "input_type": metadata["attributes"].get("type")}, "locator": preferred.locator, "fallback_locators": [candidate.locator for candidate, _ in validated[1:]], "candidates": [{"locator": candidate.locator, "score": candidate.score, "source": candidate.source, "match_count": match_count} for candidate, match_count in validated], "frame_path": [], "validation": {"match_count": count, "matches_selected_element": True}})

    async def _count(self, locator: dict[str, Any]) -> int:
        page = self.browser.page
        if page is None or page.is_closed():
            return 0
        if locator["strategy"] == "role":
            return await page.get_by_role(locator["role"], name=locator["name"], exact=locator.get("exact", True)).count()
        if locator["strategy"] == "label":
            return await page.get_by_label(locator["label"], exact=locator.get("exact", True)).count()
        if locator["strategy"] == "text":
            return await page.get_by_text(locator["text"], exact=locator.get("exact", True)).count()
        return await page.locator(locator["selector"]).count()

    async def close(self) -> None:
        await self.browser.close()
