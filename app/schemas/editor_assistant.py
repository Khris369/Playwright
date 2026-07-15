from __future__ import annotations

from typing import Any

from typing import Literal

from pydantic import BaseModel, Field


class EditorAssistantRequest(BaseModel):
    question: str = Field(min_length=1, max_length=10_000)
    html_snippet: str | None = Field(default=None, max_length=100_000)
    workflow_id: int | None = None
    workflow_version_id: int | None = None
    current_definition_json: dict[str, Any] | None = None
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class EditorAssistantResponse(BaseModel):
    model: str
    answer: str
    actions: list["EditorAssistantAction"] = Field(default_factory=list)


class EditorAssistantAction(BaseModel):
    action: Literal["add_step"]
    step_type: str = Field(min_length=1, max_length=200)
    args: dict[str, Any] = Field(default_factory=dict)
