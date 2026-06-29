from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class StepTypeResponse(BaseModel):
    key: str
    name: str
    category: str
    description: str | None = None
    default_args: dict[str, Any]
    args_schema: dict[str, Any]
    editor_schema: dict[str, Any]
