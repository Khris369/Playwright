from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: str = Field(default="active", min_length=1, max_length=30)


class WorkflowResponse(BaseModel):
    id: int
    owner_user_id: int | None = None
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    updated_by_display_name: str | None = None
    name: str
    description: str | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class WorkflowVersionCreate(BaseModel):
    base_version_id: int | None = Field(default=None, ge=1)
    definition_json: dict[str, Any] | None = None


class WorkflowVersionUpdate(BaseModel):
    definition_json: dict[str, Any]
    expected_lock_version: int = Field(ge=0)


class WorkflowVersionLockRequest(BaseModel):
    expected_lock_version: int = Field(ge=0)


class WorkflowVersionResponse(BaseModel):
    id: int
    workflow_id: int
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    version_number: int
    is_published: bool
    definition_json: dict[str, Any]
    lock_version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
