from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class TroubleshootRequest(BaseModel):
    model: str | None = None
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    extra_prompt: str | None = None


class TroubleshootResponse(BaseModel):
    run_id: int
    model: str
    prompt: str
    analysis_raw: str
    analysis_structured: dict[str, Any]
