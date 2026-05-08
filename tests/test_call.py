import json

from pathlib import Path

import allure

from conftest import TEST_CALLER_NUMBER

CALLER_CONTACT_NUMBER = TEST_CALLER_NUMBER
SCENARIO_DATA_PATH = (
    Path(__file__).resolve().parents[1] / "test_data" / "ticket_scenarios.json"
)


def load_ticket_scenarios():
    with SCENARIO_DATA_PATH.open(encoding="utf-8") as file:
        return json.load(file)


def pytest_generate_tests(metafunc):
    if "ticket_data" not in metafunc.fixturenames:
        return

    brand = metafunc.config.getoption("--brand")
    ticket_scenarios = load_ticket_scenarios()

    if brand:
        ticket_scenarios = [
            scenario
            for scenario in ticket_scenarios
            if scenario["brand"].lower() == brand.lower()
        ]

    test_ids = [
        f"{scenario['brand']}-{scenario['scenario_name']}"
        for scenario in ticket_scenarios
    ]
    metafunc.parametrize("ticket_data", ticket_scenarios, ids=test_ids)


def scroll_to_scenario_dropdown(page):
    scenario_label = page.get_by_text("Scenario :")
    scenario_label.evaluate(
        "element => element.scrollIntoView({ block: 'center', inline: 'nearest' })"
    )
    page.mouse.wheel(0, 250)


def xpath_literal(value):
    if "'" not in value:
        return f"'{value}'"

    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


def select_scenario(page, scenario_name):
    page.get_by_text("Scenario :").locator(
        "xpath=following::*[contains(@class, 'select2-selection')][1]"
    ).click()

    search_box = page.locator("input.select2-search__field")
    if search_box.is_visible():
        search_box.fill(scenario_name)

    option = page.locator(
        f"xpath=//*[contains(@class, 'select2-results__option') and normalize-space(.)={xpath_literal(scenario_name)}]"
    ).first
    option.wait_for(state="visible")
    option.click()


def click_caller_contact_search(page):
    page.get_by_text("Caller Contact Number:").locator(
        "xpath=following::button[normalize-space()='Search'][1]"
    ).click()


def wait_for_scenario_dropdown(page):
    page.wait_for_timeout(3000)
    page.get_by_text("Scenario :").locator(
        "xpath=following::*[contains(@class, 'select2-selection')][1]"
    ).wait_for(state="visible", timeout=30000)


def get_field_locator_by_label(page, label):
    max_label_length = len(label) + 4
    return page.locator(
        f"xpath=//*[self::label or self::span or self::div]"
        f"[contains(normalize-space(.), {xpath_literal(label)})]"
        f"[string-length(normalize-space(.)) <= {max_label_length}]"
        "/following::*[self::input or self::textarea or self::select][1]"
    ).first


def select_dropdown_value(dropdown, value):
    dropdown.wait_for(state="attached")
    dropdown_id = dropdown.get_attribute("id")
    dropdown_name = dropdown.get_attribute("name")
    dropdown_tag = dropdown.evaluate("element => element.tagName.toLowerCase()")
    option_texts = dropdown.locator("option").all_text_contents()

    print(
        f"[DEBUG] Dropdown found: tag={dropdown_tag}, id={dropdown_id}, "
        f"name={dropdown_name}, visible={dropdown.is_visible()}, value_to_select={value}"
    )
    print(f"[DEBUG] Dropdown options: {option_texts}")

    if not dropdown.is_visible():
        selected = dropdown.evaluate(
            """(element, requestedValue) => {
                const options = Array.from(element.options);
                const option = requestedValue === "FIRST_AVAILABLE"
                    ? options.find(item => item.value && item.textContent.trim())
                    : options.find(item => item.textContent.trim() === requestedValue || item.value === requestedValue);

                if (!option) {
                    return false;
                }

                element.value = option.value;
                element.dispatchEvent(new Event("change", { bubbles: true }));

                if (window.jQuery) {
                    window.jQuery(element).trigger("change");
                }

                return true;
            }""",
            value,
        )

        if selected:
            selected_value = dropdown.input_value()
            print(
                f"[DEBUG] Selected hidden dropdown via JS: id={dropdown_id}, "
                f"selected_value={selected_value}"
            )
            dropdown.page.wait_for_timeout(1000)
            return

        select2_selection = dropdown.page.locator(
            f"span.select2-selection[aria-labelledby='select2-{dropdown_id}-container']"
        )
        select2_selection.click()

        if value != "FIRST_AVAILABLE":
            search_box = dropdown.page.locator("input.select2-search__field")
            if search_box.is_visible():
                search_box.fill(value)

        if value == "FIRST_AVAILABLE":
            option = dropdown.page.locator(
                ".select2-results__option:not(.select2-results__option--disabled)"
            ).first
        else:
            option = dropdown.page.locator(
                f"xpath=//*[contains(@class, 'select2-results__option') and normalize-space(.)={xpath_literal(value)}]"
            ).first

        option.wait_for(state="visible", timeout=30000)
        option.click()
        print(
            f"[DEBUG] Selected hidden dropdown via visible Select2 UI: id={dropdown_id}"
        )
        dropdown.page.wait_for_timeout(1000)
        return

    if value == "FIRST_AVAILABLE":
        option_count = dropdown.locator("option").count()
        if option_count > 1:
            dropdown.select_option(index=1)
            print(
                f"[DEBUG] Selected visible dropdown first option: "
                f"id={dropdown_id}, selected_value={dropdown.input_value()}"
            )
            dropdown.page.wait_for_timeout(1000)
        return

    dropdown.select_option(label=value)
    print(
        f"[DEBUG] Selected visible dropdown by label: "
        f"id={dropdown_id}, selected_value={dropdown.input_value()}"
    )
    dropdown.page.wait_for_timeout(1000)


def get_new_ticket_scope(page):
    headers = page.locator("[id^='card-header-action-']")
    headers.first.wait_for(state="attached", timeout=30000)

    header_ids = [
        header_id
        for header_id in headers.evaluate_all(
            "elements => elements.map(element => element.id)"
        )
        if header_id
    ]
    new_ticket_header_ids = [
        header_id
        for header_id in header_ids
        if "-" not in header_id.replace("card-header-action-", "")
    ]
    new_header_id = sorted(new_ticket_header_ids or header_ids)[-1]
    ticket_suffix = new_header_id.replace("card-header-action-", "")

    print(
        f"[DEBUG] Ticket headers found: {header_ids}, "
        f"new ticket headers found: {new_ticket_header_ids}, "
        f"using new ticket suffix={ticket_suffix}"
    )

    scope = page.locator(f"#{new_header_id}").locator(
        "xpath=ancestor::*[.//button[normalize-space()='Submit']][1]"
    )
    return scope, ticket_suffix


def get_dropdown_by_selector(scope, selector, value):
    matches = scope.locator(selector)
    match_count = matches.count()
    print(
        f"[DEBUG] Looking for usable dropdown: selector={selector}, matches={match_count}"
    )

    for index in range(match_count):
        candidate = matches.nth(index)
        candidate_id = candidate.get_attribute("id")
        option_texts = [
            text.strip()
            for text in candidate.locator("option").all_text_contents()
            if text.strip()
        ]
        print(
            f"[DEBUG] Candidate dropdown index={index}, id={candidate_id}, "
            f"visible={candidate.is_visible()}, options={option_texts}"
        )

        if value == "FIRST_AVAILABLE" and len(option_texts) > 1:
            return candidate

        if value in option_texts:
            return candidate

    return matches.last


def fill_field_by_label(scope, field):
    label = field["label"]
    field_type = field["type"]
    value = field["value"]

    if "selector" in field:
        locator_count = scope.locator(field["selector"]).count()
        print(
            f"[DEBUG] Field '{label}' using selector {field['selector']} "
            f"matched {locator_count} element(s)"
        )
        if field_type in ["dropdown", "select2"]:
            locator = get_dropdown_by_selector(scope, field["selector"], value)
        else:
            locator = scope.locator(field["selector"]).last
    else:
        print(f"[DEBUG] Field '{label}' using label lookup")
        locator = get_field_locator_by_label(scope, label)

    if field_type in ["dropdown", "select2"]:
        print(f"[DEBUG] Filling dropdown field '{label}' with '{value}'")
        select_dropdown_value(locator, value)
        return

    locator.wait_for(state="visible")
    print(f"[DEBUG] Filling text field '{label}' with '{value}'")
    locator.fill(value)


def test_create_new_ticket_by_brand(logged_in_page, ticket_data):
    assert CALLER_CONTACT_NUMBER, "TEST_CALLER_NUMBER not set"

    page = logged_in_page

    with allure.step("Open Call Platform"):
        page.get_by_text("Call Platform").click()

    with allure.step("Enter caller contact number"):
        page.get_by_text("Caller Contact Number:").locator(
            "xpath=following::input[1]"
        ).fill(CALLER_CONTACT_NUMBER)

    with allure.step("Select IVR language as English"):
        page.get_by_text("IVR Language:").locator(
            "xpath=following::select[1]"
        ).select_option(label="English")

    with allure.step("Click Search"):
        click_caller_contact_search(page)
        wait_for_scenario_dropdown(page)

    with allure.step("Scroll to Scenario dropdown"):
        scroll_to_scenario_dropdown(page)

    with allure.step(f"Select scenario: {ticket_data['scenario_name']}"):
        select_scenario(page, ticket_data["scenario_name"])

    with allure.step("Click Create New Ticket"):
        page.get_by_role("button", name="Create New Ticket").click()
        page.wait_for_timeout(2000)
        ticket_scope, ticket_suffix = get_new_ticket_scope(page)

    with allure.step(f"Fill form fields for brand: {ticket_data['brand']}"):
        for field in ticket_data["fields"]:
            scoped_field = field.copy()
            if "selector" in scoped_field:
                scoped_field["selector"] = scoped_field["selector"].replace(
                    "{ticket_suffix}", ticket_suffix
                )
            fill_field_by_label(ticket_scope, scoped_field)

    with allure.step("Submit ticket"):
        ticket_scope.get_by_role("button", name="Submit").click()

    with allure.step("Confirm ticket submission"):
        page.get_by_role("button", name="Yes").click()
