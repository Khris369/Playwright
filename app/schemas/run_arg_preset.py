from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunArgPresetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    workflow_id: int | None = None
    workflow_version_id: int | None = None
    inputs_json: dict[str, Any]


class RunArgPresetUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    workflow_id: int | None = None
    workflow_version_id: int | None = None
    inputs_json: dict[str, Any]


class RunArgPresetResponse(BaseModel):
    id: int
    name: str
    workflow_id: int | None = None
    workflow_version_id: int | None = None
    inputs_json: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None
