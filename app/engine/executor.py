from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.engine.contracts import *
from app.engine.locators import LocatorResolutionError, resolve_locator

# Step handlers receive validated arguments and mutable run state. Browser
# actions are skipped when no page exists, while logical state remains usable.

class StepExecutionError(RuntimeError):
    """Raised when a step cannot complete under the workflow contract."""
    pass


@dataclass
class StepResult:
    """Execution summary persisted in workflow step history."""
    log: str


def _page(state: dict[str, Any]) -> Any | None:
    """Read the optional Playwright page from shared execution state."""
    return state.get("page")


def goto_url(args: GotoUrlArgs, state: dict[str, Any]) -> StepResult:
    """Navigate when possible and always update the logical URL state."""
    page = _page(state)
    if page is not None:
        page.goto(args.url)
        state["current_url"] = page.url
    else:
        state["current_url"] = args.url
    return StepResult(f"Navigated to {args.url}")


def fill_input(args: TargetValueArgs, state: dict[str, Any]) -> StepResult:
    """Fill a resolved target using the configured locator strategy."""
    if (page := _page(state)) is not None:
        resolve_locator(page, args.target).fill(args.value)
    return StepResult("Filled input")


def click(args: ClickArgs, state: dict[str, Any]) -> StepResult:
    """Click a target and refresh tracked URL state after the action."""
    if (page := _page(state)) is not None:
        resolve_locator(page, args.target).click()
        state["current_url"] = page.url
    return StepResult("Clicked target")


def select_option(args: SelectOptionArgs, state: dict[str, Any]) -> StepResult:
    """Select an option using its explicit label, value, or index selector."""
    if (page := _page(state)) is not None:
        resolve_locator(page, args.target).select_option(**{args.option.by: args.option.value})
    return StepResult(f"Selected option by {args.option.by}")


def wait_for_element(args: WaitForElementArgs, state: dict[str, Any]) -> StepResult:
    """Wait for the requested locator state and enforce uniqueness for strict locators."""
    if (page := _page(state)) is not None:
        locator = resolve_locator(page, args.target, require_unique=False)
        try:
            locator.wait_for(state=args.state, timeout=args.timeout_ms)
        except Exception as exc:
            raise StepExecutionError(str(exc)) from exc
        if args.target.match == "strict":
            count = locator.count()
            if count != 1:
                raise LocatorResolutionError(f"strict locator matched {count} elements; expected exactly one")
    return StepResult(f"Waited for target to become {args.state} ({args.timeout_ms}ms)")


def wait_timeout(args: WaitTimeoutArgs, state: dict[str, Any]) -> StepResult:
    """Pause for asynchronous UI changes that have no direct locator signal."""
    if (page := _page(state)) is not None:
        page.wait_for_timeout(args.timeout_ms)
    return StepResult(f"Waited for {args.timeout_ms}ms")


def assert_url_not_equal(args: AssertUrlNotEqualArgs, state: dict[str, Any]) -> StepResult:
    """Fail when the current logical/browser URL equals the forbidden URL."""
    page = _page(state)
    current = str(page.url if page is not None else state.get("current_url", ""))
    if current == args.url:
        raise StepExecutionError("URL assertion failed")
    return StepResult("URL assertion passed")


def assert_text_visible(args: AssertTextVisibleArgs, state: dict[str, Any]) -> StepResult:
    """Require exactly one visible text match when a browser page is available."""
    if (page := _page(state)) is not None:
        locator = page.get_by_text(args.text, exact=args.exact)
        if locator.count() != 1 or not locator.is_visible():
            raise StepExecutionError("Expected text is not uniquely visible")
    return StepResult("Text visibility assertion passed")


def ticket_select_scenario(args: TicketScenarioArgs, state: dict[str, Any]) -> StepResult:
    """Select a scenario from the application's Select2-style control."""
    page = _page(state)
    if page is not None:
        page.get_by_text("Scenario :", exact=True).locator(
            "xpath=following::*[contains(@class, 'select2-selection')][1]"
        ).click()
        search = page.locator("input.select2-search__field")
        if search.is_visible():
            search.fill(args.scenario_name)
        option = page.get_by_text(args.scenario_name, exact=True)
        if option.count() != 1:
            raise StepExecutionError("Scenario option was not unique")
        option.click()
    return StepResult(f"Selected scenario: {args.scenario_name}")


def _capture_new_ticket(page: Any, old_ids: list[str], timeout_ms: int) -> tuple[Any, str]:
    """Wait for and uniquely scope the ticket created by a ticket action."""
    page.wait_for_function(
        """(oldIds) => Array.from(document.querySelectorAll("[id^='card-header-action-']"))
        .filter(e => e.querySelector("[id^='TicketTitle_']")).map(e => e.id)
        .some(id => !oldIds.includes(id) && /^card-header-action-\\d+$/.test(id))""",
        arg=old_ids, timeout=timeout_ms,
    )
    ids = page.locator("[id^='card-header-action-']:has([id^='TicketTitle_'])").evaluate_all(
        "elements => elements.map(e => e.id)"
    )
    new_ids = [value for value in ids if value not in old_ids and value.removeprefix("card-header-action-").isdigit()]
    if len(new_ids) != 1:
        raise StepExecutionError("Could not identify exactly one newly created ticket")
    suffix = new_ids[0].removeprefix("card-header-action-")
    scope = page.locator(f"#TicketID_{suffix}")
    if scope.count() != 1:
        raise StepExecutionError("New ticket scope was not unique")
    return scope, suffix


def ticket_create_new_ticket(args: TicketCreateArgs, state: dict[str, Any]) -> StepResult:
    """Create a ticket and retain its DOM scope for subsequent field steps."""
    page = _page(state)
    if page is None:
        state["ticket_scope"] = object()
    else:
        old_ids = page.locator("[id^='card-header-action-']:has([id^='TicketTitle_'])").evaluate_all(
            "elements => elements.map(e => e.id)"
        )
        resolve_locator(page, args.target).click()
        scope, suffix = _capture_new_ticket(page, old_ids, args.timeout_ms)
        state.update(ticket_scope=scope, ticket_suffix=suffix)
    return StepResult("Created new ticket and captured its scope")


def ticket_fill_fields(args: TicketFillFieldsArgs, state: dict[str, Any]) -> StepResult:
    """Fill validated ticket fields within the scope captured by creation."""
    scope = state.get("ticket_scope")
    if scope is None:
        raise StepExecutionError("ticket_scope is unavailable")
    if _page(state) is not None:
        for field in args.fields:
            locator = resolve_locator(scope, field.target)
            if field.control_type == "select":
                assert field.option is not None
                locator.select_option(**{field.option.by: field.option.value}, force=True)
            else:
                locator.fill(field.value)
    return StepResult(f"Filled {len(args.fields)} ticket fields")


def ticket_submit(args: TicketSubmitArgs, state: dict[str, Any]) -> StepResult:
    """Submit the scoped ticket and confirm the application's dialog."""
    scope = state.get("ticket_scope")
    if scope is None:
        raise StepExecutionError("ticket_scope is unavailable")
    if (page := _page(state)) is not None:
        resolve_locator(scope, args.submit_target).click()
        resolve_locator(page, args.confirm_target).click()
    return StepResult("Submitted ticket and confirmed dialog")


def execute_step(step_type: str, args: dict[str, Any], state: dict[str, Any]) -> StepResult:
    """Validate registry arguments and invoke the selected step handler."""
    from app.engine.registry import STEP_REGISTRY
    definition = STEP_REGISTRY.get(step_type)
    if definition is None:
        raise StepExecutionError("Unsupported step type")
    try:
        return definition.handler(definition.args_model.model_validate(args), state)
    except (LocatorResolutionError, ValueError) as exc:
        raise StepExecutionError(str(exc)) from exc
