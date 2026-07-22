from __future__ import annotations

from typing import Any

from .locator_generator import generate_candidates, generate_xpath_candidates, redact_text


class SelectionError(RuntimeError):
    def __init__(self, code: str, message: str, recoverable: bool = False) -> None:
        super().__init__(message)
        self.code, self.recoverable = code, recoverable


async def build_picker_result(page: Any, node: dict[str, Any]) -> dict[str, Any]:
    """Generate and validate the standard locator result for one selected node."""
    if page is None or page.is_closed():
        raise SelectionError("page_closed", "The picker page closed before the element could be validated")
    frame_id, main_frame_id = node.get("picker_frame_id"), node.get("picker_main_frame_id")
    if frame_id and main_frame_id and frame_id != main_frame_id:
        raise SelectionError("frame_unsupported", "This element is inside a frame; frame-aware locators are not available yet")
    attributes = dict(zip(node.get("attributes", [])[::2], node.get("attributes", [])[1::2]))
    tag = str(node.get("nodeName", "")).lower()
    raw = node.get("picker_metadata") if isinstance(node.get("picker_metadata"), dict) else {}
    metadata = {"tag_name": raw.get("tag_name") or tag, "attributes": raw.get("attributes") or attributes, "text": redact_text(raw.get("text") or node.get("nodeValue")), "role": raw.get("role"), "name": raw.get("name"), "label": raw.get("label"), "xpath": raw.get("xpath"), "full_xpath": raw.get("full_xpath")}
    candidates, xpath_candidates = generate_candidates(metadata), generate_xpath_candidates(metadata)
    if not candidates and not xpath_candidates:
        raise SelectionError("no_supported_locator", "No supported locator candidates were found. Choose a different element or try again.", True)

    async def count(locator: dict[str, Any]) -> int:
        if locator["strategy"] == "role": return await page.get_by_role(locator["role"], name=locator["name"], exact=locator.get("exact", True)).count()
        if locator["strategy"] == "label": return await page.get_by_label(locator["label"], exact=locator.get("exact", True)).count()
        if locator["strategy"] == "text": return await page.get_by_text(locator["text"], exact=locator.get("exact", True)).count()
        if locator["strategy"] in {"xpath", "fullxpath"}: return await page.locator(f"xpath={locator['selector']}").count()
        return await page.locator(locator["selector"]).count()

    validated = []
    try:
        for candidate in candidates + xpath_candidates:
            matched = await count(candidate.locator)
            if matched == 1:
                validated.append((candidate, matched))
    except Exception as exc:
        raise SelectionError("page_closed", "The picker page changed or closed before the locator could be validated") from exc
    if not validated:
        raise SelectionError("no_unique_locator", "No unique supported locator could be validated. Choose a different element or try again.", True)
    preferred, matched = validated[0]
    return {"page": {"url": page.url, "title": await page.title()}, "element": {"tag_name": metadata["tag_name"], "text": metadata["text"], "role": metadata["role"], "input_type": metadata["attributes"].get("type")}, "locator": preferred.locator, "fallback_locators": [candidate.locator for candidate, _ in validated[1:]], "candidates": [{"locator": candidate.locator, "score": candidate.score, "source": candidate.source, "match_count": count} for candidate, count in validated], "frame_path": [], "validation": {"match_count": matched, "matches_selected_element": True}}
