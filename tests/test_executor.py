import pytest

from app.engine.contracts import Locator, VerifyElementArgs, WaitForElementArgs
from app.engine import executor
from app.engine.executor import StepExecutionError, verify_element, wait_for_element
from app.engine.locators import LocatorResolutionError


class DelayedLocator:
    def __init__(self, count_after_wait: int = 1, wait_error: Exception | None = None):
        self.count_after_wait = count_after_wait
        self.wait_error = wait_error
        self.waited = False
        self.wait_call = None
        self.first = self
        self.last = self

    def get_by_text(self, text: str, **kwargs):
        return self

    def get_by_role(self, role: str, **kwargs):
        return self

    def get_by_label(self, label: str, **kwargs):
        return self

    def locator(self, selector: str):
        return self

    def nth(self, index: int):
        return self

    def wait_for(self, **kwargs):
        self.waited = True
        self.wait_call = kwargs
        if self.wait_error is not None:
            raise self.wait_error

    def count(self):
        assert self.waited, "wait_for_element must wait before checking strict count"
        return self.count_after_wait


def test_wait_for_element_waits_before_enforcing_strict_count() -> None:
    page = DelayedLocator(count_after_wait=1)

    result = wait_for_element(
        WaitForElementArgs(target=Locator(strategy="text", text="Dashboard"), timeout_ms=5000),
        {"page": page},
    )

    assert page.wait_call == {"state": "visible", "timeout": 5000}
    assert result.log == "Waited for target to become visible (5000ms)"


def test_wait_for_element_supports_hidden_state() -> None:
    page = DelayedLocator(count_after_wait=1)

    wait_for_element(
        WaitForElementArgs(
            target=Locator(strategy="css", selector=".loading"),
            state="hidden",
            timeout_ms=5000,
        ),
        {"page": page},
    )

    assert page.wait_call == {"state": "hidden", "timeout": 5000}


def test_wait_for_element_rejects_strict_ambiguity_after_wait() -> None:
    page = DelayedLocator(count_after_wait=2)

    with pytest.raises(LocatorResolutionError):
        wait_for_element(
            WaitForElementArgs(target=Locator(strategy="text", text="Dashboard"), timeout_ms=5000),
            {"page": page},
        )

    assert page.waited is True


def test_wait_for_element_runtime_error_fails_the_step() -> None:
    page = DelayedLocator(wait_error=RuntimeError("timed out waiting for locator"))

    with pytest.raises(StepExecutionError, match="timed out waiting for locator"):
        wait_for_element(
            WaitForElementArgs(target=Locator(strategy="text", text="Dashboard"), timeout_ms=5000),
            {"page": page},
        )

    assert page.wait_call == {"state": "visible", "timeout": 5000}


class AssertionRecorder:
    def __init__(self, error: Exception | None = None):
        self.calls: list[tuple[str, dict]] = []
        self.error = error

    def _record(self, name: str, **kwargs):
        self.calls.append((name, kwargs))
        if self.error is not None:
            raise self.error

    def to_be_attached(self, **kwargs): self._record("attached", **kwargs)
    def to_be_visible(self, **kwargs): self._record("visible", **kwargs)
    def to_be_hidden(self, **kwargs): self._record("hidden", **kwargs)
    def to_be_enabled(self, **kwargs): self._record("enabled", **kwargs)
    def to_be_disabled(self, **kwargs): self._record("disabled", **kwargs)
    def to_be_editable(self, **kwargs): self._record("editable", **kwargs)
    def to_be_checked(self, **kwargs): self._record("checked", **kwargs)


@pytest.mark.parametrize(("expected_state", "method", "kwargs"), [
    ("attached", "attached", {"timeout": 5000}),
    ("visible", "visible", {"timeout": 5000}),
    ("hidden", "hidden", {"timeout": 5000}),
    ("detached", "attached", {"attached": False, "timeout": 5000}),
    ("enabled", "enabled", {"timeout": 5000}),
    ("disabled", "disabled", {"timeout": 5000}),
    ("editable", "editable", {"timeout": 5000}),
    ("not_editable", "editable", {"editable": False, "timeout": 5000}),
    ("checked", "checked", {"timeout": 5000}),
    ("unchecked", "checked", {"checked": False, "timeout": 5000}),
])
def test_verify_element_maps_states_to_retrying_playwright_assertions(monkeypatch, expected_state: str, method: str, kwargs: dict) -> None:
    page = DelayedLocator(count_after_wait=1)
    page.count = lambda: 1
    assertion = AssertionRecorder()
    monkeypatch.setattr(executor, "expect", lambda locator: assertion)

    result = verify_element(
        VerifyElementArgs(target=Locator(strategy="text", text="Status"), expected_state=expected_state, timeout_ms=5000),
        {"page": page},
    )

    assert assertion.calls == [(method, kwargs)]
    assert result.log == f"Verified target is {expected_state} (5000ms)"


def test_verify_element_assertion_failure_becomes_a_controlled_step_failure(monkeypatch) -> None:
    page = DelayedLocator(count_after_wait=1)
    page.count = lambda: 1
    monkeypatch.setattr(executor, "expect", lambda locator: AssertionRecorder(RuntimeError("timed out")))

    with pytest.raises(StepExecutionError, match="Expected text \"Status\" to be visible within 5 seconds"):
        verify_element(
            VerifyElementArgs(target=Locator(strategy="text", text="Status"), timeout_ms=5000),
            {"page": page},
        )


def test_verify_element_checked_failure_explains_target_compatibility(monkeypatch) -> None:
    page = DelayedLocator(count_after_wait=1)
    page.count = lambda: 1
    monkeypatch.setattr(executor, "expect", lambda locator: AssertionRecorder(RuntimeError("not a checkbox")))

    with pytest.raises(StepExecutionError, match="checkbox or radio"):
        verify_element(
            VerifyElementArgs(target=Locator(strategy="text", text="Status"), expected_state="checked", timeout_ms=5000),
            {"page": page},
        )
