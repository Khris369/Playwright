from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PickerModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


PickerState = Literal[
    "created", "waiting_for_agent", "agent_connected", "browser_starting",
    "browser_ready", "inspection_active", "element_selected", "completed",
    "cancelled", "expired", "failed",
]


class PickerSessionCreate(PickerModel):
    workflow_id: int = Field(gt=0)
    node_id: str = Field(min_length=1, max_length=100)
    client_id: str = Field(min_length=16, max_length=100)
    requested_url: str | None = Field(default=None, max_length=4096)


class PickerSessionResponse(PickerModel):
    session_id: str
    status: PickerState
    expires_at: datetime


class PickerAgentTokenResponse(PickerModel):
    token: str
    expires_at: datetime


class PickerPairingApprove(PickerModel):
    code: str = Field(min_length=6, max_length=20, pattern=r"^[A-Z0-9-]+$")


class PickerMessage(PickerModel):
    version: Literal[1]
    type: str = Field(min_length=1, max_length=80)
    message_id: str | None = Field(default=None, max_length=100)
    session_id: str | None = Field(default=None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)
