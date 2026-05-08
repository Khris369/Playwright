from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class WorkflowRunCreate(BaseModel):
    workflow_version_id: int = Field(ge=1)
    inputs: dict[str, Any] = Field(default_factory=dict)


class WorkflowRunResponse(BaseModel):
    id: int
    workflow_id: int
    workflow_version_id: int
    status: str
    trigger_source: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_summary: str | None = None
    created_at: datetime | None = None


class WorkflowStepRunResponse(BaseModel):
    id: int
    workflow_run_id: int
    step_index: int
    step_id: str | None = None
    step_type: str
    status: str
    args_json: dict[str, Any] | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None
    log_text: str | None = None
    error_text: str | None = None
    screenshot_path: str | None = None
    created_at: datetime | None = None
