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
    created_by_user_id: int | None = None
    status: str
    trigger_source: str
    execution_mode: str = "server"
    target_step_id: str | None = None
    definition_hash: str | None = None
    error_code: str | None = None
    inputs_json: dict[str, Any] | None = None
    resolved_definition_json: dict[str, Any] | None = None
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


class WorkflowRunArtifactResponse(BaseModel):
    id: int
    workflow_run_id: int
    created_by_user_id: int | None = None
    step_run_id: int | None = None
    artifact_type: str
    file_path: str
    mime_type: str
    size_bytes: int
    created_at: datetime | None = None
    download_url: str
