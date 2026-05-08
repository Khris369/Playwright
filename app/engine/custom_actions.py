from __future__ import annotations

import json
from pathlib import Path
from typing import Any

def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


def _select_scenario(page: Any, scenario_name: str) -> None:
    page.get_by_text("Scenario :").locator(
        "xpath=following::*[contains(@class, 'select2-selection')][1]"
    ).click()
    search_box = page.locator("input.select2-search__field")
    if search_box.is_visible():
        search_box.fill(scenario_name)
    option = page.locator(
        f"xpath=//*[contains(@class, 'select2-results__option') and normalize-space(.)={_xpath_literal(scenario_name)}]"
    ).first
    option.wait_for(state="visible")
    option.click()


def _get_new_ticket_scope(page: Any) -> tuple[Any, str]:
    headers = page.locator("[id^='card-header-action-']")
    headers.first.wait_for(state="attached", timeout=30000)
    header_ids = [
        h for h in headers.evaluate_all("elements => elements.map(element => element.id)") if h
    ]
    new_ticket_header_ids = [
        hid
        for hid in header_ids
        if "-" not in hid.replace("card-header-action-", "")
    ]
    new_header_id = sorted(new_ticket_header_ids or header_ids)[-1]
    ticket_suffix = new_header_id.replace("card-header-action-", "")
    scope = page.locator(f"#{new_header_id}").locator(
        "xpath=ancestor::*[.//button[normalize-space()='Submit']][1]"
    )
    return scope, ticket_suffix


def _load_ticket_fields(ticket_data_path: str, scenario_name: str, brand: str) -> list[dict[str, Any]]:
    path = Path(ticket_data_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise RuntimeError(f"ticket_data_path not found: {path}")
    with path.open(encoding="utf-8") as f:
        scenarios = json.load(f)
    matches = [
        s for s in scenarios
        if str(s.get("brand", "")).lower() == brand.lower()
        and str(s.get("scenario_name", "")).strip() == scenario_name
    ]
    if not matches:
        raise RuntimeError(
            f"No ticket scenario found for brand='{brand}', scenario_name='{scenario_name}'"
        )
    return list(matches[0].get("fields", []))


def _fill_by_label(scope: Any, label: str, value: str) -> None:
    max_len = len(label) + 4
    locator = scope.locator(
        f"xpath=//*[self::label or self::span or self::div]"
        f"[contains(normalize-space(.), {_xpath_literal(label)})]"
        f"[string-length(normalize-space(.)) <= {max_len}]"
        "/following::*[self::input or self::textarea or self::select][1]"
    ).first
    locator.wait_for(state="visible")
    locator.fill(value)


def _fill_field(scope: Any, field: dict[str, Any]) -> None:
    field_type = str(field.get("type", "text")).lower()
    value = field.get("value", "")
    selector = field.get("selector")
    label = field.get("label", "")
    if selector:
        locator = scope.locator(selector).last
    else:
        if not label:
            raise StepExecutionError("Field missing both selector and label.")
        if field_type in {"dropdown", "select2"}:
            locator = scope.locator(
                f"xpath=//*[contains(normalize-space(.), {_xpath_literal(label)})]"
                "/following::*[self::select][1]"
            ).first
        else:
            _fill_by_label(scope, str(label), str(value))
            return

    if field_type in {"dropdown", "select2"}:
        try:
            locator.select_option(label=str(value))
        except Exception:
            locator.select_option(value=str(value))
        return
    locator.wait_for(state="visible")
    locator.fill(str(value))


def execute_custom_action(action: str, args: dict[str, Any], state: dict[str, Any]) -> str:
    page = state.get("page")
    if page is None:
        raise RuntimeError("Custom action requires browser page context.")

    if action != "create_ticket_flow":
        raise RuntimeError(f"Unsupported custom action: {action}")

    scenario_name = str(args.get("scenario_name", "")).strip()
    brand = str(args.get("brand", "")).strip()
    ticket_data_path = str(args.get("ticket_data_path", "test_data/ticket_scenarios.json"))
    if not scenario_name or not brand:
        raise RuntimeError("create_ticket_flow requires scenario_name and brand")

    _select_scenario(page, scenario_name)
    page.get_by_role("button", name="Create New Ticket").click()
    page.wait_for_timeout(1500)

    scope, ticket_suffix = _get_new_ticket_scope(page)
    fields = _load_ticket_fields(ticket_data_path, scenario_name, brand)
    for field in fields:
        scoped = dict(field)
        if "selector" in scoped and isinstance(scoped["selector"], str):
            scoped["selector"] = scoped["selector"].replace("{ticket_suffix}", ticket_suffix)
        _fill_field(scope, scoped)

    scope.get_by_role("button", name="Submit").click()
    page.get_by_role("button", name="Yes").click()
    return f"Executed custom action create_ticket_flow for brand={brand}, scenario={scenario_name}"
