import pytest

from app.engine.contracts import Locator, WaitForElementArgs
from app.engine.executor import StepExecutionError, wait_for_element
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
    assert result.log == "Waited for target (5000ms)"


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
