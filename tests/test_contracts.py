import pytest
from pydantic import ValidationError

from app.engine.contracts import Locator, SelectOption, TicketField, VerifyElementArgs, WaitTimeoutArgs
from app.engine.registry import STEP_REGISTRY, public_step_types


def test_locator_is_typed_and_rejects_non_css_selector_engines() -> None:
    assert Locator(strategy="role", role="button", name="Save").match == "strict"
    with pytest.raises(ValidationError):
        Locator(strategy="css", selector="xpath=//button")
    with pytest.raises(ValidationError):
        Locator(strategy="role", role="button", name="Save", selector="#save")


def test_xpath_locator_strategies_are_supported_explicitly() -> None:
    assert Locator(strategy="xpath", selector="//button[@id='save']").strategy == "xpath"
    assert Locator(strategy="fullxpath", selector="/html[1]/body[1]/button[1]").strategy == "fullxpath"
    with pytest.raises(ValidationError):
        Locator(strategy="xpath", selector="javascript:alert(1)")


def test_explicit_bounded_match_modes() -> None:
    assert Locator(strategy="text", text="Save", match="nth", nth=3).nth == 3
    with pytest.raises(ValidationError):
        Locator(strategy="text", text="Save", match="nth")
    with pytest.raises(ValidationError):
        Locator(strategy="text", text="Save", match="nth", nth=100)


def test_strict_booleans_indices_and_timeouts() -> None:
    with pytest.raises(ValidationError):
        Locator(strategy="text", text="Save", exact="false")
    with pytest.raises(ValidationError):
        SelectOption(by="index", value="1")
    with pytest.raises(ValidationError):
        WaitTimeoutArgs(timeout_ms=120001)


def test_verify_element_contract_supports_only_expected_states() -> None:
    supported = {
        "attached", "visible", "hidden", "detached", "enabled", "disabled",
        "editable", "not_editable", "checked", "unchecked",
    }
    for expected_state in supported:
        assert VerifyElementArgs(
            target=Locator(strategy="text", text="Status"), expected_state=expected_state
        ).expected_state == expected_state
    assert VerifyElementArgs(target=Locator(strategy="text", text="Status")).timeout_ms == 30_000
    with pytest.raises(ValidationError):
        VerifyElementArgs(target=Locator(strategy="text", text="Status"), expected_state="readonly")
    with pytest.raises(ValidationError):
        VerifyElementArgs(target=Locator(strategy="text", text="Status"), timeout_ms=120_001)


def test_ticket_select_requires_explicit_option() -> None:
    with pytest.raises(ValidationError):
        TicketField(target={"strategy": "label", "label": "Type"}, control_type="select")


def test_registry_public_schema_is_consistent() -> None:
    public = public_step_types()
    assert {item["key"] for item in public} == set(STEP_REGISTRY)
    assert "click_by_role" not in STEP_REGISTRY
    assert "run_custom_action" not in STEP_REGISTRY
    for item in public:
        STEP_REGISTRY[item["key"]].args_model.model_validate(item["default_args"])
    verify = next(item for item in public if item["key"] == "verify_element")
    assert verify["category"] == "Assertion"
    assert verify["editor_schema"]["fields"][1]["path"] == "expected_state"
