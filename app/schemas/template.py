from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowTemplateCreate(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=80)
    definition_json: dict[str, Any]


class WorkflowTemplateResponse(BaseModel):
    id: int
    key: str
    name: str
    category: str | None = None
    definition_json: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowTemplateImportRequest(BaseModel):
    workflow_name: str = Field(min_length=1, max_length=200)
    workflow_description: str | None = None
    workflow_status: str = Field(default="active", min_length=1, max_length=30)
    version_number: int = Field(default=1, ge=1)
    is_published: bool = True


class WorkflowTemplateImportResponse(BaseModel):
    workflow: dict[str, Any]
    version: dict[str, Any]
