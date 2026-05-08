from __future__ import annotations

import re
from typing import Any

TEMPLATE_RE = re.compile(r"^\{\{\s*([a-zA-Z0-9_.]+)\s*\}\}$")


def _resolve_path(path: str, context: dict[str, Any]) -> Any:
    parts = path.split(".")
    current: Any = context
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"Template path not found: {path}")
        current = current[part]
    return current


def resolve_value(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str):
        match = TEMPLATE_RE.match(value)
        if match:
            return _resolve_path(match.group(1), context)
        return value
    if isinstance(value, list):
        return [resolve_value(item, context) for item in value]
    if isinstance(value, dict):
        return {key: resolve_value(item, context) for key, item in value.items()}
    return value
