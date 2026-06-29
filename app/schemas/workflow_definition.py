from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


class WorkflowDefinitionValidate(BaseModel):
    definition_json: dict[str, Any]


class ValidationIssueResponse(BaseModel):
    code: str
    message: str
    node_id: str | None = None
    edge_id: str | None = None


class WorkflowDefinitionValidationResponse(BaseModel):
    valid: bool
    compiled_steps: list[dict[str, Any]] = Field(default_factory=list)
    compiled_order: list[str] = Field(default_factory=list)
    errors: list[ValidationIssueResponse] = Field(default_factory=list)
