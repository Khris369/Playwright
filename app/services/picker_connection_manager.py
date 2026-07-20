from __future__ import annotations

from dataclasses import dataclass, field
from fastapi import WebSocket


@dataclass
class PickerConnectionManager:
    agents: dict[int, WebSocket] = field(default_factory=dict)
    editors: dict[tuple[int, str], WebSocket] = field(default_factory=dict)
    pairings: dict[str, WebSocket] = field(default_factory=dict)

    async def send_agent(self, user_id: int, message: dict) -> bool:
        socket = self.agents.get(user_id)
        if socket is None:
            return False
        await socket.send_json(message)
        return True

    async def send_editor(self, user_id: int, client_id: str, message: dict) -> bool:
        socket = self.editors.get((user_id, client_id))
        if socket is None:
            return False
        await socket.send_json(message)
        return True


picker_connections = PickerConnectionManager()
