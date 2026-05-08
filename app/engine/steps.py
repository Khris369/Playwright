from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.engine.custom_actions import execute_custom_action


class StepExecutionError(RuntimeError):
    pass


@dataclass
class StepResult:
    log: str


def _page(state: dict[str, Any]) -> Any | None:
    return state.get("page")


def _goto_url(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    url = str(args["url"])
    page = _page(state)
    if page is not None:
        page.goto(url)
        state["current_url"] = page.url
    else:
        state["current_url"] = url
    return StepResult(log=f"Navigated to {url}")


def _fill_input(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    value = str(args["value"])
    page = _page(state)
    if page is not None:
        page.locator(selector).fill(value)
    else:
        fields = state.setdefault("fields", {})
        fields[selector] = value
    return StepResult(log=f"Filled {selector}")


def _click(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    page = _page(state)
    if page is not None:
        page.locator(selector).click()
        state["current_url"] = page.url
    else:
        clicks = state.setdefault("clicks", [])
        clicks.append(selector)
    return StepResult(log=f"Clicked {selector}")


def _click_by_role(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    role = str(args.get("role", "button"))
    name = str(args["name"])
    scope_selector = args.get("scope_selector")
    nth = int(args.get("nth", 0))
    exact = bool(args.get("exact", True))
    page = _page(state)
    if page is not None:
        root = page.locator(str(scope_selector)) if scope_selector else page
        locator = root.get_by_role(role, name=name, exact=exact)
        locator.nth(nth).click()
        state["current_url"] = page.url
    else:
        clicks = state.setdefault("clicks", [])
        clicks.append({"role": role, "name": name, "scope_selector": scope_selector, "nth": nth})
    scope_part = f" within {scope_selector}" if scope_selector else ""
    return StepResult(log=f"Clicked role={role} name={name}{scope_part} (nth={nth})")


def _select_option(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    value = str(args["value"])
    page = _page(state)
    if page is not None:
        locator = page.locator(selector)
        try:
            locator.select_option(label=value)
        except Exception:
            locator.select_option(value=value)
    else:
        selects = state.setdefault("selects", {})
        selects[selector] = value
    return StepResult(log=f"Selected {value} in {selector}")


def _wait_for_element(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    timeout_ms = int(args.get("timeout_ms", 30000))
    page = _page(state)
    if page is not None:
        page.locator(selector).wait_for(state="visible", timeout=timeout_ms)
    return StepResult(log=f"Waited for element {selector} (timeout {timeout_ms}ms)")


def _assert_url_not_equal(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    expected_not = str(args["url"])
    page = _page(state)
    current = str(page.url if page is not None else state.get("current_url", ""))
    if current == expected_not:
        raise StepExecutionError(f"Current URL must not equal {expected_not}")
    return StepResult(log=f"URL assertion passed: current URL != {expected_not}")


def _assert_text_visible(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    expected_text = str(args["text"])
    page = _page(state)
    if page is not None:
        locator = page.get_by_text(expected_text)
        if not locator.first.is_visible():
            raise StepExecutionError(f"Text not visible: {expected_text}")
    else:
        visible = state.get("visible_texts", [])
        if expected_text not in visible:
            raise StepExecutionError(f"Text not visible: {expected_text}")
    return StepResult(log=f"Text visible assertion passed: {expected_text}")


def _run_custom_action(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    action = str(args["action"])
    try:
        log = execute_custom_action(action, args, state)
        return StepResult(log=log)
    except Exception as exc:
        raise StepExecutionError(str(exc)) from exc


def _ticket_select_scenario(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    try:
        log = execute_custom_action("ticket_select_scenario", args, state)
        return StepResult(log=log)
    except Exception as exc:
        raise StepExecutionError(str(exc)) from exc


def _ticket_create_new_ticket(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    try:
        log = execute_custom_action("ticket_create_new_ticket", args, state)
        return StepResult(log=log)
    except Exception as exc:
        raise StepExecutionError(str(exc)) from exc


def _ticket_fill_fields_from_scenario(
    args: dict[str, Any], state: dict[str, Any]
) -> StepResult:
    try:
        log = execute_custom_action("ticket_fill_fields_from_scenario", args, state)
        return StepResult(log=log)
    except Exception as exc:
        raise StepExecutionError(str(exc)) from exc


def _ticket_fill_fields(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    try:
        log = execute_custom_action("ticket_fill_fields", args, state)
        return StepResult(log=log)
    except Exception as exc:
        raise StepExecutionError(str(exc)) from exc


def _ticket_submit(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    try:
        log = execute_custom_action("ticket_submit", args, state)
        return StepResult(log=log)
    except Exception as exc:
        raise StepExecutionError(str(exc)) from exc


STEP_HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], StepResult]] = {
    "goto_url": _goto_url,
    "fill_input": _fill_input,
    "click": _click,
    "click_by_role": _click_by_role,
    "select_option": _select_option,
    "wait_for_element": _wait_for_element,
    "assert_url_not_equal": _assert_url_not_equal,
    "assert_text_visible": _assert_text_visible,
    "run_custom_action": _run_custom_action,
    "ticket_select_scenario": _ticket_select_scenario,
    "ticket_create_new_ticket": _ticket_create_new_ticket,
    "ticket_fill_fields": _ticket_fill_fields,
    "ticket_fill_fields_from_scenario": _ticket_fill_fields_from_scenario,
    "ticket_submit": _ticket_submit,
}


def execute_step(step_type: str, args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    handler = STEP_HANDLERS.get(step_type)
    if handler is None:
        raise StepExecutionError(f"Unsupported step type: {step_type}")
    return handler(args, state)
