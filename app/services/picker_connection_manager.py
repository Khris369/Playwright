from __future__ import annotations

from dataclasses import dataclass, field
import asyncio
import json
from datetime import UTC, datetime
from fastapi import WebSocket


class RedisPickerRelay:
    """Best-effort cross-process picker message relay.

    WebSocket objects stay process-local; Redis only carries typed JSON commands
    between broker instances. Local delivery remains the fast/default path.
    """

    def __init__(self, url: str, prefix: str = "workflow-picker") -> None:
        self.url = url
        self.prefix = prefix
        self.client = None
        self.task: asyncio.Task | None = None
        self._deliver = None

    async def start(self, deliver) -> None:
        from redis import asyncio as redis_async

        self._deliver = deliver
        self.client = redis_async.from_url(self.url, decode_responses=True)
        self.task = asyncio.create_task(self._listen())

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
        if self.client:
            await self.client.aclose()
            self.client = None

    def _channel(self, kind: str, *parts: object) -> str:
        return ":".join((self.prefix, kind, *(str(part) for part in parts)))

    async def publish(self, kind: str, parts: tuple[object, ...], message: dict) -> None:
        if self.client is not None:
            await self.client.publish(self._channel(kind, *parts), json.dumps(message, separators=(",", ":")))

    async def _listen(self) -> None:
        if self.client is None:
            return
        pubsub = self.client.pubsub()
        await pubsub.psubscribe(f"{self.prefix}:*")
        try:
            async for item in pubsub.listen():
                if item.get("type") != "pmessage":
                    continue
                channel = str(item.get("channel", ""))
                parts = channel.split(":")
                if len(parts) < 3 or parts[0] != self.prefix:
                    continue
                try:
                    await self._deliver(parts[1], parts[2:], json.loads(item["data"]))
                except (ValueError, TypeError, json.JSONDecodeError):
                    continue
        finally:
            await pubsub.close()


@dataclass
class PickerConnectionManager:
    agents: dict[int, WebSocket] = field(default_factory=dict)
    editors: dict[tuple[int, str], WebSocket] = field(default_factory=dict)
    pairings: dict[str, WebSocket] = field(default_factory=dict)
    agent_info: dict[int, dict] = field(default_factory=dict)
    relay: RedisPickerRelay | None = None

    async def start_relay(self, redis_url: str | None) -> None:
        if not redis_url:
            return
        relay = RedisPickerRelay(redis_url)
        await relay.start(self._deliver_relay_message)
        self.relay = relay

    async def stop_relay(self) -> None:
        if self.relay:
            await self.relay.stop()
            self.relay = None

    def set_agent_info(self, user_id: int, payload: dict) -> None:
        self.agent_info[user_id] = {
            "agent_version": str(payload.get("agent_version", ""))[:40],
            "platform": str(payload.get("platform", ""))[:40],
            "last_seen": datetime.now(UTC).isoformat(),
        }

    def clear_agent_info(self, user_id: int) -> None:
        self.agent_info.pop(user_id, None)

    async def _deliver_relay_message(self, kind: str, parts: list[str], message: dict) -> None:
        if kind == "agent" and len(parts) == 1:
            socket = self.agents.get(int(parts[0]))
        elif kind == "editor" and len(parts) == 2:
            socket = self.editors.get((int(parts[0]), parts[1]))
        else:
            return
        if socket is not None:
            await socket.send_json(message)

    async def send_agent(self, user_id: int, message: dict) -> bool:
        socket = self.agents.get(user_id)
        if socket is not None:
            await socket.send_json(message)
            return True
        if self.relay:
            await self.relay.publish("agent", (user_id,), message)
            return True
        return False

    async def send_editor(self, user_id: int, client_id: str, message: dict) -> bool:
        socket = self.editors.get((user_id, client_id))
        if socket is not None:
            await socket.send_json(message)
            return True
        if self.relay:
            await self.relay.publish("editor", (user_id, client_id), message)
            return True
        return False


picker_connections = PickerConnectionManager()
