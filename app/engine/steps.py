from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


class StepExecutionError(RuntimeError):
    pass


@dataclass
class StepResult:
    log: str


def _goto_url(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    url = str(args["url"])
    state["current_url"] = url
    return StepResult(log=f"Navigated to {url}")


def _fill_input(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    value = str(args["value"])
    fields = state.setdefault("fields", {})
    fields[selector] = value
    return StepResult(log=f"Filled {selector}")


def _click(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    clicks = state.setdefault("clicks", [])
    clicks.append(selector)
    return StepResult(log=f"Clicked {selector}")


def _select_option(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    value = str(args["value"])
    selects = state.setdefault("selects", {})
    selects[selector] = value
    return StepResult(log=f"Selected {value} in {selector}")


def _wait_for_element(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    selector = str(args["selector"])
    timeout_ms = int(args.get("timeout_ms", 30000))
    return StepResult(log=f"Waited for element {selector} (timeout {timeout_ms}ms)")


def _assert_url_not_equal(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    expected_not = str(args["url"])
    current = str(state.get("current_url", ""))
    if current == expected_not:
        raise StepExecutionError(f"Current URL must not equal {expected_not}")
    return StepResult(log=f"URL assertion passed: current URL != {expected_not}")


def _assert_text_visible(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    expected_text = str(args["text"])
    visible = state.get("visible_texts", [])
    if expected_text not in visible:
        raise StepExecutionError(f"Text not visible: {expected_text}")
    return StepResult(log=f"Text visible assertion passed: {expected_text}")


def _run_custom_action(args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    action = str(args["action"])
    actions = state.setdefault("custom_actions", [])
    actions.append(args)
    return StepResult(log=f"Executed custom action: {action}")


STEP_HANDLERS: dict[str, Callable[[dict[str, Any], dict[str, Any]], StepResult]] = {
    "goto_url": _goto_url,
    "fill_input": _fill_input,
    "click": _click,
    "select_option": _select_option,
    "wait_for_element": _wait_for_element,
    "assert_url_not_equal": _assert_url_not_equal,
    "assert_text_visible": _assert_text_visible,
    "run_custom_action": _run_custom_action,
}


def execute_step(step_type: str, args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    handler = STEP_HANDLERS.get(step_type)
    if handler is None:
        raise StepExecutionError(f"Unsupported step type: {step_type}")
    return handler(args, state)
