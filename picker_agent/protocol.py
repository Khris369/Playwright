from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ALLOWED_COMMANDS = {"picker.session.requested", "picker.inspect.start", "picker.inspect.cancel", "session.close"}


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1, le=1)
    type: str = Field(min_length=1, max_length=80)
    session_id: str | None = Field(default=None, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)


def parse_command(raw: dict[str, Any]) -> Message:
    try:
        message = Message.model_validate(raw)
    except ValidationError as exc:
        raise ValueError("Invalid picker protocol message") from exc
    if message.type not in ALLOWED_COMMANDS:
        raise ValueError("Unknown picker command")
    if message.type != "picker.session.requested" and not message.session_id:
        raise ValueError("Picker command requires a session")
    return message
