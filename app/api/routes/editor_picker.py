from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from app.core.auth import current_user, optional_current_user
from app.engine.contracts import Locator
from app.schemas.editor_picker import PickerAgentTokenResponse, PickerMessage, PickerPairingApprove, PickerSessionCreate, PickerSessionResponse
from app.services.permission_repository import PermissionRepository
from app.services.picker_connection_manager import picker_connections
from app.services.picker_session_service import TERMINAL_STATES, picker_sessions

router = APIRouter(prefix="/editor-picker", tags=["editor-picker"])

AGENT_EVENTS = {"agent.ready", "picker.session.accepted", "browser.opened", "browser.page_changed", "picker.inspect.started", "picker.inspect.cancelled", "picker.element.selected", "picker.error", "session.closed"}
EDITOR_EVENTS = {"editor.connect"}


def _safe_url(value: str | None) -> str | None:
    if value is None:
        return None
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise HTTPException(status_code=422, detail="Picker URL must use http or https")
    return value


def _can_edit(user: dict, workflow_id: int) -> bool:
    return "admin" in user.get("roles", []) or PermissionRepository.can_access_workflow(int(user["id"]), workflow_id, "workflow.edit")


def _session_response(session) -> PickerSessionResponse:
    return PickerSessionResponse(session_id=session.id, status=session.state, expires_at=session.expires_at)


async def _notify_editor(session, event_type: str, payload: dict | None = None) -> None:
    await picker_connections.send_editor(session.user_id, session.client_id, {
        "version": 1, "type": event_type, "session_id": session.id,
        "payload": payload or {"status": session.state, "expires_at": session.expires_at.isoformat()},
    })


@router.post("/agent-token", response_model=PickerAgentTokenResponse)
def create_agent_token(user: dict = Depends(current_user)) -> PickerAgentTokenResponse:
    """One-time POC token copied to the local agent; never a general API credential."""
    claim = picker_sessions.issue_agent_token(int(user["id"]))
    return PickerAgentTokenResponse(token=claim.token, expires_at=claim.expires_at)


@router.get("/agent-status")
def agent_status(user: dict = Depends(current_user)) -> dict:
    picker_sessions.expire()
    return {"connected": int(user["id"]) in picker_connections.agents}


@router.post("/pairings/approve")
async def approve_pairing(payload: PickerPairingApprove, user: dict = Depends(current_user)) -> dict:
    socket = picker_connections.pairings.get(payload.code)
    if socket is None:
        raise HTTPException(status_code=404, detail="Pairing code not found or expired")
    approved = picker_sessions.approve_pairing(payload.code, int(user["id"]))
    if approved is None:
        raise HTTPException(status_code=404, detail="Pairing code not found or expired")
    pairing, claim = approved
    await socket.send_json({"version": 1, "type": "pairing.approved", "payload": {"device_token": claim.token, "expires_at": claim.expires_at.isoformat()}})
    await socket.close()
    picker_connections.pairings.pop(payload.code, None)
    return {"paired": True}


@router.post("/sessions", response_model=PickerSessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(payload: PickerSessionCreate, user: dict = Depends(current_user)) -> PickerSessionResponse:
    if not _can_edit(user, payload.workflow_id):
        raise HTTPException(status_code=404, detail="Workflow not found")
    session = picker_sessions.create(int(user["id"]), payload.workflow_id, payload.node_id, payload.client_id, _safe_url(payload.requested_url))
    if await picker_connections.send_agent(session.user_id, {
        "version": 1, "type": "picker.session.requested", "session_id": session.id,
        "payload": {"start_url": session.requested_url},
    }):
        picker_sessions.transition(session, "agent_connected")
        await _notify_editor(session, "picker.session.updated")
    return _session_response(session)


@router.get("/sessions/{session_id}", response_model=PickerSessionResponse)
def get_session(session_id: str, user: dict = Depends(current_user)) -> PickerSessionResponse:
    session = picker_sessions.get_owned(session_id, int(user["id"]))
    if session is None:
        raise HTTPException(status_code=404, detail="Picker session not found")
    return _session_response(session)


@router.post("/sessions/{session_id}/inspect")
async def start_inspection(session_id: str, user: dict = Depends(current_user)) -> PickerSessionResponse:
    session = picker_sessions.get_owned(session_id, int(user["id"]))
    if session is None or not _can_edit(user, session.workflow_id):
        raise HTTPException(status_code=404, detail="Picker session not found")
    if session.state != "browser_ready":
        raise HTTPException(status_code=409, detail="Picker browser is not ready")
    await picker_connections.send_agent(session.user_id, {"version": 1, "type": "picker.inspect.start", "session_id": session.id, "payload": {}})
    return _session_response(session)


@router.post("/sessions/{session_id}/cancel", response_model=PickerSessionResponse)
async def cancel_session(session_id: str, user: dict = Depends(current_user)) -> PickerSessionResponse:
    session = picker_sessions.get_owned(session_id, int(user["id"]))
    if session is None or not _can_edit(user, session.workflow_id):
        raise HTTPException(status_code=404, detail="Picker session not found")
    if session.state not in TERMINAL_STATES:
        picker_sessions.transition(session, "cancelled")
        await picker_connections.send_agent(session.user_id, {"version": 1, "type": "session.close", "session_id": session.id, "payload": {}})
        await _notify_editor(session, "picker.session.updated")
    return _session_response(session)


@router.post("/sessions/{session_id}/inspect/cancel", response_model=PickerSessionResponse)
async def cancel_inspection(session_id: str, user: dict = Depends(current_user)) -> PickerSessionResponse:
    session = picker_sessions.get_owned(session_id, int(user["id"]))
    if session is None or not _can_edit(user, session.workflow_id):
        raise HTTPException(status_code=404, detail="Picker session not found")
    if session.state == "inspection_active":
        await picker_connections.send_agent(session.user_id, {"version": 1, "type": "picker.inspect.cancel", "session_id": session.id, "payload": {}})
    elif session.state != "browser_ready":
        raise HTTPException(status_code=409, detail="Picker inspection is not active")
    return _session_response(session)


@router.post("/sessions/{session_id}/complete", response_model=PickerSessionResponse)
async def complete_session(session_id: str, user: dict = Depends(current_user)) -> PickerSessionResponse:
    session = picker_sessions.get_owned(session_id, int(user["id"]))
    if session is None or not _can_edit(user, session.workflow_id):
        raise HTTPException(status_code=404, detail="Picker session not found")
    if session.state != "element_selected":
        raise HTTPException(status_code=409, detail="No selected element is ready to accept")
    picker_sessions.transition(session, "completed")
    await picker_connections.send_agent(session.user_id, {"version": 1, "type": "session.close", "session_id": session.id, "payload": {}})
    await _notify_editor(session, "picker.session.updated")
    return _session_response(session)


def _parse_message(raw: dict, allowed: set[str]) -> PickerMessage:
    try:
        message = PickerMessage.model_validate(raw)
    except ValidationError as exc:
        raise ValueError("Invalid picker protocol message") from exc
    if message.type not in allowed:
        raise ValueError("Unknown picker protocol message")
    return message


@router.websocket("/agent")
async def agent_socket(websocket: WebSocket) -> None:
    token = websocket.query_params.get("token", "")
    device_token = websocket.query_params.get("device_token", "")
    claim = picker_sessions.consume_agent_token(token) or picker_sessions.consume_device_token(device_token)
    if claim is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    picker_connections.agents[claim.user_id] = websocket
    try:
        while True:
            message = _parse_message(await websocket.receive_json(), AGENT_EVENTS)
            if message.type == "agent.ready":
                continue
            if not message.session_id:
                raise ValueError("Session message requires session_id")
            session = picker_sessions.get_owned(message.session_id, claim.user_id)
            if session is None:
                raise ValueError("Expired or unauthorized picker session")
            if session.state in TERMINAL_STATES:
                # Cancellation can race with browser startup. Ignore late
                # lifecycle events; the close command will clean up locally.
                if message.type == "session.closed":
                    await _notify_editor(session, message.type, message.payload)
                continue
            if message.type == "picker.session.accepted":
                picker_sessions.transition(session, "browser_starting")
            elif message.type == "browser.opened":
                picker_sessions.transition(session, "browser_ready")
            elif message.type == "browser.page_changed":
                if session.state not in {"browser_starting", "browser_ready", "inspection_active", "element_selected"}:
                    raise ValueError("Page change is invalid in the current picker state")
            elif message.type == "picker.inspect.started":
                picker_sessions.transition(session, "inspection_active")
            elif message.type == "picker.inspect.cancelled":
                picker_sessions.transition(session, "browser_ready")
            elif message.type == "picker.element.selected":
                if not _valid_result(message.payload):
                    raise ValueError("Invalid locator result")
                picker_sessions.transition(session, "element_selected")
                session.result = message.payload
            elif message.type == "picker.error":
                picker_sessions.transition(session, "failed")
            elif message.type == "session.closed":
                if session.state not in TERMINAL_STATES:
                    picker_sessions.transition(session, "cancelled")
            await _notify_editor(session, message.type, message.payload)
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        if picker_connections.agents.get(claim.user_id) is websocket:
            del picker_connections.agents[claim.user_id]
        for session in picker_sessions.sessions.values():
            if session.user_id == claim.user_id and session.state not in TERMINAL_STATES:
                session.state = "failed"
                await _notify_editor(session, "picker.error", {"message": "Local picker agent disconnected"})


@router.websocket("/pair")
async def pairing_socket(websocket: WebSocket) -> None:
    code = websocket.query_params.get("code", "").upper()
    if len(code) < 6 or any(char not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-" for char in code):
        await websocket.close(code=1008)
        return
    pairing = picker_sessions.create_pairing(code)
    await websocket.accept()
    picker_connections.pairings[code] = websocket
    try:
        await websocket.send_json({"version": 1, "type": "pairing.waiting", "payload": {"expires_at": pairing.expires_at.isoformat()}})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        picker_connections.pairings.pop(code, None)


@router.websocket("/editor")
async def editor_socket(websocket: WebSocket) -> None:
    user = optional_current_user(websocket)  # WebSocket has the same cookie interface as Request.
    if user is None:
        await websocket.close(code=1008)
        return
    await websocket.accept()
    client_id = ""
    try:
        message = _parse_message(await websocket.receive_json(), EDITOR_EVENTS)
        client_id = str(message.payload.get("client_id", ""))
        if not client_id or len(client_id) > 100:
            raise ValueError("Invalid editor client")
        picker_connections.editors[(int(user["id"]), client_id)] = websocket
        await websocket.send_json({"version": 1, "type": "editor.connected", "payload": {"agent_connected": int(user["id"]) in picker_connections.agents}})
        while True:
            await websocket.receive_text()  # Editor sends no further commands in Phase 1.
    except (WebSocketDisconnect, ValueError):
        pass
    finally:
        picker_connections.editors.pop((int(user["id"]), client_id), None)


def _valid_result(payload: dict) -> bool:
    locator = payload.get("locator")
    validation = payload.get("validation")
    if not isinstance(locator, dict) or not isinstance(validation, dict):
        return False
    try:
        Locator.model_validate(locator)
    except ValidationError:
        return False
    return validation.get("matches_selected_element") is True and isinstance(validation.get("match_count"), int)
