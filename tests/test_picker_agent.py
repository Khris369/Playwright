import pytest

from picker_agent.browser_manager import validate_navigation_url
from picker_agent.locator_generator import generate_candidates, generate_xpath_candidates, safe_attributes
from picker_agent.protocol import parse_command
from picker_agent.session import AgentSession
from picker_agent.inspector import INJECTED_INSPECTOR_SCRIPT


def test_agent_rejects_unknown_protocol_commands() -> None:
    with pytest.raises(ValueError, match="Unknown"):
        parse_command({"version": 1, "type": "execute", "payload": {}})


def test_agent_rejects_unsafe_navigation_schemes() -> None:
    for value in ("file:///secret", "javascript:alert(1)", "data:text/html,x", "about:blank"):
        with pytest.raises(ValueError):
            validate_navigation_url(value)
    assert validate_navigation_url("https://example.test/path") == "https://example.test/path"


def test_locator_candidates_are_ordered_and_redact_sensitive_attributes() -> None:
    attrs = safe_attributes({"data-testid": "submit", "id": "stable-submit", "value": "secret", "data-token": "nope"})
    candidates = generate_candidates({"tag_name": "button", "role": "button", "name": "Submit", "text": "Submit", "attributes": attrs})
    assert candidates[0].locator["strategy"] == "role"
    assert candidates[1].source == "test id"
    assert all("secret" not in str(candidate.locator) and "nope" not in str(candidate.locator) for candidate in candidates)


def test_select2_search_input_gets_a_safe_class_css_candidate() -> None:
    candidates = generate_candidates({
        "tag_name": "input",
        "role": "textbox",
        "name": "",
        "text": "",
        "attributes": {"class": "select2-search__field"},
    })
    assert any(candidate.locator.get("selector") == "input.select2-search__field" for candidate in candidates)


def test_dynamic_class_tokens_are_not_used_as_css_candidates() -> None:
    candidates = generate_candidates({
        "tag_name": "input",
        "attributes": {"class": "css-a1b2c3 stable-field"},
    })
    assert not any("css-a1b2c3" in str(candidate.locator) for candidate in candidates)
    assert any(candidate.locator.get("selector") == "input.stable-field" for candidate in candidates)


def test_dynamic_numeric_id_prefers_prefix_selector_and_keeps_exact_fallback() -> None:
    candidates = generate_candidates({
        "tag_name": "input",
        "attributes": {"id": "Subject_12345"},
    })
    assert candidates[0].locator == {
        "strategy": "css",
        "selector": 'input[id^="Subject_"]',
        "exact": True,
        "match": "strict",
    }
    assert candidates[1].locator["selector"] == "#Subject_12345"


def test_xpath_fallback_candidates_are_kept_separate_from_supported_candidates() -> None:
    candidates = generate_xpath_candidates({
        "xpath": "//*[@id='save']",
        "full_xpath": "/html[1]/body[1]/button[1]",
    })
    assert [candidate.locator["strategy"] for candidate in candidates] == ["xpath", "fullxpath"]


def test_agent_session_cleanup_closes_its_isolated_browser_context() -> None:
    class Browser:
        closed = False
        async def close(self): self.closed = True

    async def emit(*args):
        return None

    session = AgentSession("session", emit)
    browser = Browser()
    session.browser = browser  # type: ignore[assignment]
    import asyncio
    asyncio.run(session.close())
    assert browser.closed


def test_closed_picker_page_is_not_used_for_locator_validation() -> None:
    import asyncio
    from picker_agent.session import AgentSession

    class ClosedPage:
        def is_closed(self): return True

    async def emit(*args):
        return None

    session = AgentSession("session", emit)
    session.browser.page = ClosedPage()  # type: ignore[assignment]
    assert asyncio.run(session._count({"strategy": "css", "selector": "#submit"})) == 0


def test_injected_fallback_uses_fixed_local_selection_binding() -> None:
    assert "__picker_select" in INJECTED_INSPECTOR_SCRIPT
    assert "pointerover" in INJECTED_INSPECTOR_SCRIPT
    assert "stopImmediatePropagation" in INJECTED_INSPECTOR_SCRIPT
