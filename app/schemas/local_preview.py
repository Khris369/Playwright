from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateLocalPreviewRequest(BaseModel):
    workflow_version_id: int = Field(ge=1)
    definition: dict[str, Any]
    inputs: dict[str, Any] = Field(default_factory=dict)
    target_node_id: str = Field(min_length=1, max_length=120)
    confirm_side_effects: bool = False
    client_id: str = Field(min_length=1, max_length=100)


class LocalPreviewResponse(BaseModel):
    id: int
    preview_session_id: str | None = None
    status: str
    execution_mode: str
    target_step_id: str | None = None
    definition_hash: str | None = None
    error_code: str | None = None
    error_summary: str | None = None
    current_node_id: str | None = None
    current_node_type: str | None = None
    current_url: str | None = None
    started_at: Any | None = None
    finished_at: Any | None = None
    created_at: Any | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)


class PreviewInspectionPickRequest(BaseModel):
    client_id: str = Field(min_length=1, max_length=100)
    node_id: str = Field(min_length=1, max_length=120)
    field_path: str = Field(min_length=1, max_length=200)


class PreviewInspectionCancelRequest(BaseModel):
    pick_request_id: str = Field(min_length=1, max_length=100)
