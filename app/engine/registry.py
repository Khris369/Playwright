from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from pydantic import BaseModel

from app.engine import executor
from app.engine.contracts import *


@dataclass(frozen=True)
class StepDefinition:
    key: str
    title: str
    category: str
    description: str
    args_model: type[BaseModel]
    default_args: dict[str, Any]
    editor_schema: dict[str, Any]
    handler: Callable[[Any, dict[str, Any]], executor.StepResult]
    requires: frozenset[str] = frozenset()
    provides: frozenset[str] = frozenset()


def _editor(*names: str) -> dict[str, Any]:
    return {"fields": [{
        "path": n,
        "widget": (
            "ticket-fields" if n == "fields"
            else "locator" if n in {"target", "submit_target", "confirm_target"}
            else "select-option" if n == "option"
            else "text"
        ),
    } for n in names]}


ROLE_BUTTON = {"target": {"strategy": "role", "role": "button", "name": "Button", "exact": True}}
LABEL_TARGET = {"strategy": "label", "label": "Field label", "exact": True}


_items = (
    StepDefinition("goto_url", "Go to URL", "Navigation", "Navigate to a URL.", GotoUrlArgs, {"url": "https://example.com"}, _editor("url"), executor.goto_url),
    StepDefinition("click", "Click", "Interaction", "Click a typed locator.", ClickArgs, ROLE_BUTTON, _editor("target"), executor.click),
    StepDefinition("fill_input", "Fill input", "Interaction", "Fill a text control.", TargetValueArgs, {"target": LABEL_TARGET, "value": ""}, _editor("target", "value"), executor.fill_input),
    StepDefinition("select_option", "Select option", "Interaction", "Select explicitly by label, value, or index.", SelectOptionArgs, {"target": LABEL_TARGET, "option": {"by": "label", "value": "Option"}}, _editor("target", "option"), executor.select_option),
    StepDefinition("wait_for_element", "Wait for element", "Wait", "Wait for a visible target.", WaitForElementArgs, {"target": LABEL_TARGET, "timeout_ms": 30000}, _editor("target", "timeout_ms"), executor.wait_for_element),
    StepDefinition("wait_timeout", "Wait timeout", "Wait", "Wait a bounded duration.", WaitTimeoutArgs, {"timeout_ms": 1000}, _editor("Timeout (seconds)"), executor.wait_timeout),
    StepDefinition("assert_url_not_equal", "Assert URL changed", "Assertion", "Require the current URL to differ.", AssertUrlNotEqualArgs, {"url": "https://example.com/login"}, _editor("url"), executor.assert_url_not_equal),
    StepDefinition("assert_text_visible", "Assert text visible", "Assertion", "Require unique visible text.", AssertTextVisibleArgs, {"text": "Success", "exact": True}, _editor("text", "exact"), executor.assert_text_visible),
    StepDefinition("ticket_select_scenario", "Select ticket scenario", "Ticket", "Select a ticket scenario.", TicketScenarioArgs, {"scenario_name": "Scenario name"}, _editor("scenario_name"), executor.ticket_select_scenario),
    StepDefinition("ticket_create_new_ticket", "Create new ticket", "Ticket", "Create a ticket and capture its exact form scope.", TicketCreateArgs, TicketCreateArgs().model_dump(), _editor("target", "timeout_ms"), executor.ticket_create_new_ticket, provides=frozenset({"ticket_scope"})),
    StepDefinition("ticket_fill_fields", "Fill ticket fields", "Ticket", "Fill validated inline ticket rows.", TicketFillFieldsArgs, {"fields": [{"target": LABEL_TARGET, "control_type": "text", "value": ""}]}, _editor("fields"), executor.ticket_fill_fields, requires=frozenset({"ticket_scope"})),
    StepDefinition("ticket_submit", "Submit ticket", "Ticket", "Submit within the captured ticket scope.", TicketSubmitArgs, TicketSubmitArgs().model_dump(), _editor("submit_target", "confirm_target"), executor.ticket_submit, requires=frozenset({"ticket_scope"})),
)
STEP_REGISTRY = {item.key: item for item in _items}


def public_step_types() -> list[dict[str, Any]]:
    return [{
        "key": item.key, "name": item.title, "category": item.category,
        "description": item.description, "default_args": item.default_args,
        "args_schema": item.args_model.model_json_schema(), "editor_schema": item.editor_schema,
    } for item in _items]
