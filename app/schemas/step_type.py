from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class StepTypeResponse(BaseModel):
    id: int
    key: str
    name: str
    description: str | None = None
    is_active: bool
    sort_order: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
