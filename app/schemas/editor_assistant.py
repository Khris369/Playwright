from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EditorAssistantRequest(BaseModel):
    question: str = Field(min_length=1)
    html_snippet: str | None = None
    workflow_id: int | None = None
    workflow_version_id: int | None = None
    current_definition_json: dict[str, Any] | None = None
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class EditorAssistantResponse(BaseModel):
    model: str
    answer: str
