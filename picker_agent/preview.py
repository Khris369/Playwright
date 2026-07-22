"""Async, preview-only workflow executor; it never imports server runners."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.engine.contracts import (
    AssertTextVisibleArgs, AssertUrlNotEqualArgs, ClickArgs, GotoUrlArgs,
    SelectOptionArgs, TargetValueArgs, VerifyElementArgs, WaitForElementArgs,
    WaitTimeoutArgs, TicketCreateArgs, TicketFillFieldsArgs,
)
from app.engine.template import resolve_value

from .browser_manager import BrowserManager


class PreviewError(RuntimeError):
    pass


def _condition_matches(args: dict[str, Any], state: dict[str, Any], inputs: dict[str, Any]) -> bool:
    key = str(args.get("state_key", ""))
    actual = inputs.get(key.removeprefix("inputs.")) if key.startswith("inputs.") else state.get(key)
    expected, operator = args.get("value"), args.get("operator")
    if operator == "truthy": return bool(actual)
    if operator == "falsy": return not bool(actual)
    if operator == "not_equals": return actual != expected
    if operator == "contains": return str(expected) in str(actual or "")
    return actual == expected


def _locator(root: Any, spec: Any) -> Any:
    target = spec.scope if getattr(spec, "scope", None) else None
    if target:
        root = _locator(root, target)
    if spec.strategy == "role":
        locator = root.get_by_role(spec.role, name=spec.name, exact=spec.exact)
    elif spec.strategy == "label":
        locator = root.get_by_label(spec.label, exact=spec.exact)
    elif spec.strategy == "text":
        locator = root.get_by_text(spec.text, exact=spec.exact)
    elif spec.strategy in {"xpath", "fullxpath"}:
        locator = root.locator(f"xpath={spec.selector}")
    else:
        locator = root.locator(spec.selector)
    if spec.match == "first":
        return locator.first
    if spec.match == "last":
        return locator.last
    if spec.match == "nth":
        return locator.nth(spec.nth)
    return locator


async def _strict(locator: Any, spec: Any) -> Any:
    if spec.match == "strict" and await locator.count() != 1:
        raise PreviewError("Strict locator did not match exactly one element")
    return locator


@dataclass
class LocalPreviewExecutor:
    session_id: str
    run_id: int
    target_node_id: str
    steps: list[dict[str, Any]]
    inputs: dict[str, Any]
    keep_browser_open: bool
    emit: Callable[[str, str, dict[str, Any]], Awaitable[None]]

    def __post_init__(self) -> None:
        self.cancelled = asyncio.Event()
        self.browser = BrowserManager()

    async def stop(self) -> None:
        self.cancelled.set()

    async def close(self) -> None:
        await self.browser.close()

    async def run(self) -> None:
        try:
            page = await self.browser.open(None)
            state: dict[str, Any] = {"page": page, "current_url": ""}
            await self._emit("preview.accepted", {})
            by_id = {str(step["id"]): step for step in self.steps}
            current_id = str(self.steps[0]["id"]) if self.steps else None
            loop_counts: dict[str, int] = {}
            context = {"inputs": self.inputs, "secrets": {}}
            for index in range(10_000):
                if self.cancelled.is_set():
                    await self._emit("preview.cancelled", {})
                    return
                if current_id is None:
                    await self._emit("preview.target_not_reached", {})
                    return
                step = by_id.get(current_id)
                if step is None:
                    raise PreviewError("Preview plan points to an unknown node")
                node_type = str(step["type"])
                await self._emit("preview.step.started", {"node_id": current_id, "node_type": node_type, "step_index": index, "url": page.url})
                try:
                    args = resolve_value(step.get("args") or {}, context)
                    if node_type in {"__if__", "__loop__"}:
                        matched = _condition_matches(args, state, self.inputs)
                        if node_type == "__if__":
                            branch = "true" if matched else "false"
                        else:
                            count, maximum = loop_counts.get(current_id, 0), int(args.get("max_iterations", 10))
                            branch = "done" if matched or count >= maximum else "body"
                            if branch == "body":
                                loop_counts[current_id] = count + 1
                        log, next_id = f"Control condition selected {branch}", (step.get("branches") or {}).get(branch)
                    else:
                        log = await self._execute(node_type, args, state)
                        next_id = step.get("next")
                    await self._emit("preview.step.completed", {"node_id": current_id, "node_type": node_type, "step_index": index, "log": log, "url": page.url})
                    if current_id == self.target_node_id:
                        await self._emit("preview.passed", {"url": page.url})
                        return
                    current_id = str(next_id) if next_id is not None else None
                except Exception as exc:
                    await self._emit("preview.step.failed", {"node_id": current_id, "node_type": node_type, "step_index": index, "error": "Preview step failed", "url": page.url})
                    await self._emit("preview.failed", {"code": "step_failed", "message": "Preview step failed"})
                    return
            await self._emit("preview.failed", {"code": "step_failed", "message": "Preview exceeded execution safety limit"})
        except Exception:
            await self._emit("preview.rejected", {"code": "step_failed", "message": "Unable to start local preview"})
        finally:
            # Keep the headed preview context available for inspection after a
            # terminal result. It is released only by preview.close, agent
            # disconnect, or a manual browser close.
            if not self.keep_browser_open:
                await self.browser.close()

    async def _execute(self, node_type: str, raw: dict[str, Any], state: dict[str, Any]) -> str:
        page = state["page"]
        if node_type == "goto_url":
            args = GotoUrlArgs.model_validate(raw); await page.goto(args.url, wait_until="domcontentloaded"); state["current_url"] = page.url; return f"Navigated to {args.url}"
        if node_type == "click":
            args = ClickArgs.model_validate(raw); locator = await _strict(_locator(page, args.target), args.target); await locator.click(); state["current_url"] = page.url; return "Clicked target"
        if node_type == "fill_input":
            args = TargetValueArgs.model_validate(raw); locator = await _strict(_locator(page, args.target), args.target); await locator.fill(args.value); return "Filled input"
        if node_type == "select_option":
            args = SelectOptionArgs.model_validate(raw); locator = await _strict(_locator(page, args.target), args.target); await locator.select_option(**{args.option.by: args.option.value}); return f"Selected option by {args.option.by}"
        if node_type == "wait_timeout":
            args = WaitTimeoutArgs.model_validate(raw); await page.wait_for_timeout(args.timeout_ms); return f"Waited for {args.timeout_ms}ms"
        if node_type == "wait_for_element":
            args = WaitForElementArgs.model_validate(raw); locator = _locator(page, args.target); await locator.wait_for(state=args.state, timeout=args.timeout_ms); await _strict(locator, args.target); return f"Waited for target to become {args.state}"
        if node_type == "verify_element":
            args = VerifyElementArgs.model_validate(raw); locator = _locator(page, args.target)
            if args.expected_state == "visible": await locator.wait_for(state="visible", timeout=args.timeout_ms)
            elif args.expected_state == "hidden": await locator.wait_for(state="hidden", timeout=args.timeout_ms)
            elif args.expected_state == "attached": await locator.wait_for(state="attached", timeout=args.timeout_ms)
            elif args.expected_state == "detached": await locator.wait_for(state="detached", timeout=args.timeout_ms)
            elif args.expected_state == "enabled": await locator.wait_for(state="visible", timeout=args.timeout_ms); assert await locator.is_enabled()
            elif args.expected_state == "disabled": await locator.wait_for(state="visible", timeout=args.timeout_ms); assert await locator.is_disabled()
            elif args.expected_state == "editable": await locator.wait_for(state="visible", timeout=args.timeout_ms); assert await locator.is_editable()
            elif args.expected_state == "not_editable": await locator.wait_for(state="visible", timeout=args.timeout_ms); assert not await locator.is_editable()
            elif args.expected_state == "checked": assert await locator.is_checked()
            else: assert not await locator.is_checked()
            await _strict(locator, args.target); return f"Verified target is {args.expected_state}"
        if node_type == "assert_url_not_equal":
            args = AssertUrlNotEqualArgs.model_validate(raw)
            if page.url == args.url: raise PreviewError("URL assertion failed")
            return "URL assertion passed"
        if node_type == "assert_text_visible":
            args = AssertTextVisibleArgs.model_validate(raw); locator = page.get_by_text(args.text, exact=args.exact)
            if await locator.count() != 1 or not await locator.is_visible(): raise PreviewError("Expected text is not uniquely visible")
            return "Text visibility assertion passed"
        if node_type == "ticket_create_new_ticket":
            args = TicketCreateArgs.model_validate(raw)
            old_ids = await page.locator("[id^='card-header-action-']:has([id^='TicketTitle_'])").evaluate_all("elements => elements.map(e => e.id)")
            locator = await _strict(_locator(page, args.target), args.target)
            await locator.click()
            await page.wait_for_function("""(oldIds) => Array.from(document.querySelectorAll("[id^='card-header-action-']"))
                .filter(e => e.querySelector("[id^='TicketTitle_']")).map(e => e.id)
                .some(id => !oldIds.includes(id) && /^card-header-action-\\d+$/.test(id))""", arg=old_ids, timeout=args.timeout_ms)
            ids = await page.locator("[id^='card-header-action-']:has([id^='TicketTitle_'])").evaluate_all("elements => elements.map(e => e.id)")
            new_ids = [value for value in ids if value not in old_ids and str(value).removeprefix("card-header-action-").isdigit()]
            if len(new_ids) != 1:
                raise PreviewError("Could not identify exactly one newly created ticket")
            suffix = str(new_ids[0]).removeprefix("card-header-action-")
            scope = page.locator(f"#TicketID_{suffix}")
            if await scope.count() != 1:
                raise PreviewError("New ticket scope was not unique")
            state.update(ticket_scope=scope, ticket_suffix=suffix)
            return "Created new ticket and captured its scope"
        if node_type == "ticket_fill_fields":
            args = TicketFillFieldsArgs.model_validate(raw)
            scope = state.get("ticket_scope")
            if scope is None:
                raise PreviewError("ticket_scope is unavailable")
            for field in args.fields:
                locator = await _strict(_locator(scope, field.target), field.target)
                if field.control_type == "select":
                    assert field.option is not None
                    await locator.select_option(**{field.option.by: field.option.value}, force=True)
                else:
                    await locator.fill(field.value)
            return f"Filled {len(args.fields)} ticket fields"
        raise PreviewError("Unsupported preview node")

    async def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        await self.emit(event_type, self.session_id, {"run_id": self.run_id, **payload})
