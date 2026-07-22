import pytest

from app.engine.contracts import Locator
from app.engine.locators import LocatorResolutionError, resolve_locator


class FakeLocator:
    def __init__(self, count=1, label="root"):
        self._count = count; self.label = label
        self.first = FakeSelected(f"{label}:first"); self.last = FakeSelected(f"{label}:last")
    def count(self): return self._count
    def nth(self, index): return FakeSelected(f"{self.label}:nth:{index}")
    def get_by_role(self, role, **kwargs): return FakeLocator(self._count, f"role:{role}:{kwargs['name']}")
    def get_by_label(self, label, **kwargs): return FakeLocator(self._count, f"label:{label}")
    def get_by_text(self, text, **kwargs): return FakeLocator(self._count, f"text:{text}")
    def locator(self, selector): return FakeLocator(self._count, f"css:{selector}")


class FakeSelected:
    def __init__(self, label): self.label = label


def test_strict_mode_rejects_ambiguity() -> None:
    with pytest.raises(LocatorResolutionError):
        resolve_locator(FakeLocator(count=2), Locator(strategy="text", text="Save"))


def test_explicit_match_mode_and_scope_are_applied() -> None:
    result = resolve_locator(FakeLocator(), Locator(
        strategy="role", role="button", name="Save", match="nth", nth=2,
        scope={"strategy": "css", "selector": ".dialog"},
    ))
    assert result.label == "role:button:Save:nth:2"
