from __future__ import annotations

import json
import secrets
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from .protocol import parse_command
from .session import AgentSession
from .storage import clear_device_token, load_device_token, save_device_token


class AgentConnection:
    def __init__(self, server: str, token: str | None = None, pairing_code: str | None = None) -> None:
        self.server, self.token, self.pairing_code = server.rstrip("/"), token, pairing_code
        self.sessions: dict[str, AgentSession] = {}
        self.socket = None

    async def emit(self, event_type: str, session_id: str | None, payload: dict) -> None:
        await self.socket.send(json.dumps({"version": 1, "type": event_type, "session_id": session_id, "payload": payload}))

    async def run(self) -> None:
        stored_token = load_device_token() if self.token is None else None
        token = self.token or stored_token
        if token:
            try:
                await self._run_authenticated(token)
                return
            except (ConnectionClosed, InvalidStatus):
                if stored_token is None:
                    raise
                clear_device_token()
                print("Stored picker device token was rejected; starting a new pairing.")
        raw_code = secrets.token_hex(4).upper()
        code = self.pairing_code or f"{raw_code[:4]}-{raw_code[4:]}"
        print(f"Workflow Picker pairing code: {code}")
        print("Enter this code in the authenticated workflow editor within 5 minutes.")
        uri = f"{self.server}/editor-picker/pair?code={code}"
        async with websockets.connect(uri, max_size=64 * 1024) as socket:
            async for raw in socket:
                message = json.loads(raw)
                if message.get("type") == "pairing.approved":
                    token = str(message.get("payload", {}).get("device_token", ""))
                    if not token:
                        raise ValueError("Pairing response did not contain a device token")
                    save_device_token(token)
                    self.token = token
                    break
        await self._run_authenticated(token)

    async def _run_authenticated(self, token: str) -> None:
        uri = f"{self.server}/editor-picker/agent?device_token={token}"
        async with websockets.connect(uri, max_size=64 * 1024) as socket:
            self.socket = socket
            await self.emit("agent.ready", None, {"agent_version": "0.1.0", "platform": "windows", "capabilities": ["chromium", "cdp_inspection", "locator_validation"]})
            try:
                async for raw in socket:
                    await self.handle(json.loads(raw))
            except ConnectionClosed:
                # Normal server/browser shutdown may not include a close
                # frame; cleanup below remains the source of truth.
                pass
            finally:
                for session in list(self.sessions.values()):
                    await session.close()
                self.sessions.clear()

    async def handle(self, raw: dict[str, Any]) -> None:
        message = parse_command(raw)
        if message.type == "picker.session.requested":
            session_id = message.session_id
            if not session_id or session_id in self.sessions:
                raise ValueError("Invalid or duplicate picker session")
            session = AgentSession(session_id, self.emit)
            self.sessions[session_id] = session
            try:
                await session.open(message.payload.get("start_url"))
            except Exception:
                await session.close()
                self.sessions.pop(session_id, None)
                await self.emit("picker.error", session_id, {"message": "Unable to launch local Chromium"})
        else:
            session = self.sessions.get(message.session_id or "")
            if not session:
                raise ValueError("Unknown picker session")
            try:
                if message.type == "picker.inspect.start":
                    await session.start_inspection()
                elif message.type == "picker.inspect.cancel":
                    await session.cancel_inspection()
                elif message.type == "session.close":
                    await session.close()
                    self.sessions.pop(session.session_id, None)
                    await self.emit("session.closed", session.session_id, {})
            except Exception:
                await self.emit("picker.error", session.session_id, {"code": "picker_operation_failed", "message": "The local picker could not complete that operation"})
