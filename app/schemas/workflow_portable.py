from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PortableVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    definition_json: dict[str, Any]


class PortableWorkflow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    format: Literal["workflow-builder"]
    format_version: Literal[1]
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=65_535)
    versions: list[PortableVersion] = Field(min_length=1, max_length=100)
