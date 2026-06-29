from __future__ import annotations

from typing import Any

from app.engine.contracts import Locator, LocatorTarget


class LocatorResolutionError(RuntimeError):
    pass


def _base_locator(root: Any, target: LocatorTarget) -> Any:
    if target.strategy == "role":
        return root.get_by_role(target.role, name=target.name, exact=target.exact)
    if target.strategy == "label":
        return root.get_by_label(target.label, exact=target.exact)
    if target.strategy == "text":
        return root.get_by_text(target.text, exact=target.exact)
    return root.locator(target.selector)


def resolve_locator(page_or_scope: Any, spec: Locator, *, require_unique: bool = True) -> Any:
    root = _base_locator(page_or_scope, spec.scope) if spec.scope else page_or_scope
    locator = _base_locator(root, spec)
    if spec.match == "first":
        return locator.first
    if spec.match == "last":
        return locator.last
    if spec.match == "nth":
        return locator.nth(spec.nth)
    if require_unique:
        count = locator.count()
        if count != 1:
            raise LocatorResolutionError(f"strict locator matched {count} elements; expected exactly one")
    return locator
