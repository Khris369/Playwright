from __future__ import annotations

import json
import secrets
import asyncio
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, InvalidStatus

from .protocol import parse_command
from .session import AgentSession
from .preview import LocalPreviewExecutor, PreviewError
from .selection import SelectionCoordinator
from .storage import clear_device_token, load_device_token, save_device_token


class AgentConnection:
    def __init__(self, server: str, token: str | None = None, pairing_code: str | None = None) -> None:
        self.server, self.token, self.pairing_code = server.rstrip("/"), token, pairing_code
        self.sessions: dict[str, AgentSession] = {}
        self.previews: dict[str, LocalPreviewExecutor] = {}
        self.selection = SelectionCoordinator()
        self.socket = None

    async def emit(self, event_type: str, session_id: str | None, payload: dict) -> None:
        await self.socket.send(json.dumps({"version": 1, "type": event_type, "session_id": session_id, "payload": {"message_id": secrets.token_urlsafe(12), **payload}}))

    async def run(self) -> None:
        explicit_token = self.token is not None
        stored_token = load_device_token() if self.token is None else None
        token = self.token or stored_token
        retry_delay = 1.0
        while True:
            if token:
                try:
                    await self._run_authenticated(token)
                    retry_delay = 1.0
                except InvalidStatus:
                    if explicit_token:
                        raise
                    clear_device_token()
                    stored_token = None
                    token = None
                    print("Picker device token was rejected; starting a new pairing.")
                    continue
                except (ConnectionClosed, OSError) as exc:
                    print(f"Picker connection lost ({type(exc).__name__}); retrying in {retry_delay:g}s.")
                    await asyncio.sleep(retry_delay)
                    retry_delay = min(retry_delay * 2, 30.0)
                    continue
            token = await self._pair_with_retry()
            retry_delay = 1.0

    async def _pair_with_retry(self) -> str:
        """Pair until FastAPI is reachable, without requiring a new process."""
        code_override = self.pairing_code
        while True:
            raw_code = secrets.token_hex(4).upper()
            code = code_override or f"{raw_code[:4]}-{raw_code[4:]}"
            code_override = None
            print(f"Workflow Picker pairing code: {code}")
            print("Enter this code in the authenticated workflow editor within 5 minutes.")
            uri = f"{self.server}/editor-picker/pair?code={code}"
            try:
                async with websockets.connect(uri, max_size=64 * 1024) as socket:
                    async for raw in socket:
                        message = json.loads(raw)
                        if message.get("type") == "pairing.approved":
                            token = str(message.get("payload", {}).get("device_token", ""))
                            if not token:
                                raise ValueError("Pairing response did not contain a device token")
                            save_device_token(token)
                            self.token = token
                            return token
            except (ConnectionClosed, OSError):
                print("Picker server unavailable; retrying pairing in 2s.")
                await asyncio.sleep(2)

    async def _run_authenticated(self, token: str) -> None:
        uri = f"{self.server}/editor-picker/agent?device_token={token}"
        async with websockets.connect(uri, max_size=64 * 1024) as socket:
            self.socket = socket
            await self.emit("agent.ready", None, {"agent_version": "0.1.0", "platform": "windows", "capabilities": ["chromium", "cdp_inspection", "locator_validation"]})
            try:
                async for raw in socket:
                    await self.handle(json.loads(raw))
            except ConnectionClosed:
                # Let the outer loop apply bounded reconnect backoff. Cleanup
                # below still runs before the exception is propagated.
                raise
            finally:
                for session in list(self.sessions.values()):
                    await session.close()
                for preview in list(self.previews.values()):
                    await preview.close()
                self.sessions.clear()
                self.previews.clear()

    async def handle(self, raw: dict[str, Any]) -> None:
        message = parse_command(raw)
        if message.type == "preview.start":
            if not message.session_id or message.session_id in self.previews or self.previews:
                raise ValueError("Invalid or duplicate preview session")
            payload = message.payload
            run_id = payload.get("run_id")
            steps = payload.get("steps")
            if not isinstance(run_id, int) or not isinstance(steps, list) or not isinstance(payload.get("inputs"), dict) or not isinstance(payload.get("target_node_id"), str):
                raise ValueError("Invalid preview plan")
            allowed = {"goto_url", "click", "fill_input", "select_option", "wait_for_element", "wait_timeout", "verify_element", "assert_url_not_equal", "assert_text_visible", "ticket_create_new_ticket", "ticket_fill_fields", "__if__", "__loop__"}
            if not steps or any(not isinstance(step, dict) or str(step.get("type", "")) not in allowed for step in steps) or not any(str(step.get("id", "")) == payload["target_node_id"] for step in steps):
                raise ValueError("Unsupported preview plan")
            for existing in list(self.previews.values()):
                await existing.close("replaced")
            self.previews.clear()
            preview = LocalPreviewExecutor(message.session_id, run_id, str(payload.get("target_node_id", "")), steps, payload["inputs"], self.selection, self.emit, lambda session_id=message.session_id: self.previews.pop(session_id or "", None))
            self.previews[message.session_id] = preview
            asyncio.create_task(self._run_preview(preview))
            return
        if message.type == "preview.stop":
            preview = self.previews.get(message.session_id or "")
            if preview is None:
                raise ValueError("Unknown preview session")
            await preview.stop()
            return
        if message.type == "preview.close":
            preview = self.previews.get(message.session_id or "")
            if preview is None:
                raise ValueError("Unknown preview session")
            await preview.close()
            self.previews.pop(preview.session_id, None)
            return
        if message.type == "preview.inspection.pick.start":
            preview = self.previews.get(message.session_id or "")
            request_id = message.payload.get("pick_request_id")
            if preview is None or not isinstance(request_id, str) or not request_id or len(request_id) > 100:
                raise ValueError("Invalid preview pick request")
            try:
                await preview.start_inspection(request_id)
            except PreviewError as exc:
                await self.emit("preview.inspection.unavailable", preview.session_id, {"run_id": preview.run_id, "pick_request_id": request_id, "code": "inspection_unavailable", "message": str(exc)})
            return
        if message.type == "preview.inspection.pick.cancel":
            preview = self.previews.get(message.session_id or "")
            request_id = message.payload.get("pick_request_id")
            if preview is None or not isinstance(request_id, str):
                raise ValueError("Invalid preview pick request")
            try:
                await preview.cancel_inspection(request_id)
            except PreviewError as exc:
                await self.emit("preview.inspection.unavailable", preview.session_id, {"run_id": preview.run_id, "pick_request_id": request_id, "code": "inspection_unavailable", "message": str(exc)})
            return
        if message.type == "preview.inspection.close":
            preview = self.previews.get(message.session_id or "")
            if preview is None:
                raise ValueError("Unknown preview session")
            await preview.close()
            self.previews.pop(preview.session_id, None)
            return
        if message.type == "picker.session.requested":
            session_id = message.session_id
            if not session_id or session_id in self.sessions:
                raise ValueError("Invalid or duplicate picker session")
            session = AgentSession(session_id, self.emit, self.selection)
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

    async def _run_preview(self, preview: LocalPreviewExecutor) -> None:
        await preview.run()
        if preview.inspection_state != "inspection_ready":
            self.previews.pop(preview.session_id, None)
