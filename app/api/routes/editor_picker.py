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
from app.services.local_preview_service import local_previews
from app.services.workflow_run_repository import WorkflowRunRepository

router = APIRouter(prefix="/editor-picker", tags=["editor-picker"])

AGENT_EVENTS = {"agent.ready", "picker.session.accepted", "browser.opened", "browser.page_changed", "picker.inspect.started", "picker.inspect.cancelled", "picker.element.selected", "picker.error", "session.closed", "preview.accepted", "preview.step.started", "preview.step.completed", "preview.step.failed", "preview.passed", "preview.target_not_reached", "preview.cancelled", "preview.rejected", "preview.failed"}
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
    user_id = int(user["id"])
    return {"connected": user_id in picker_connections.agents, **picker_connections.agent_info.get(user_id, {})}


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
    return {"paired": True, "expires_at": claim.expires_at}


@router.delete("/pairings/device")
async def unpair_device(user: dict = Depends(current_user)) -> dict:
    user_id = int(user["id"])
    revoked = picker_sessions.revoke_device_tokens(user_id)
    socket = picker_connections.agents.get(user_id)
    if socket is not None:
        await socket.close(code=1000, reason="Picker agent unpaired")
    picker_connections.clear_agent_info(user_id)
    return {"unpaired": revoked > 0, "revoked": revoked}


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
    elif session.state == "element_selected":
        # The agent stops its inspector immediately after a selection. Discard
        # that pending result without closing the browser so the user can pick
        # a different element in the same authenticated browser context.
        picker_sessions.transition(session, "browser_ready")
        session.result = None
        await _notify_editor(session, "picker.inspect.cancelled")
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
    # Accepting a locator releases the result, not the browser. This lets the
    # same user/editor choose another workflow node and inspect it in the same
    # page, including its cookies and in-page state.
    picker_sessions.transition(session, "browser_ready")
    session.result = None
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
                picker_connections.set_agent_info(claim.user_id, message.payload)
                continue
            if not message.session_id:
                raise ValueError("Session message requires session_id")
            if message.type.startswith("preview."):
                run_id = message.payload.get("run_id")
                message_id = message.payload.get("message_id")
                if not isinstance(run_id, int) or not isinstance(message_id, str) or len(message_id) > 100:
                    raise ValueError("Invalid preview event")
                preview = local_previews.event(message.session_id, run_id, message.type, message.payload, message_id)
                if preview is None or preview.connection is not websocket:
                    raise ValueError("Expired or unauthorized preview event")
                run = WorkflowRunRepository.get_run(run_id)
                await picker_connections.send_editor(claim.user_id, preview.client_id, {"version": 1, "type": message.type, "session_id": message.session_id, "payload": {"run_id": run_id, "status": run.get("status") if run else "failed", **message.payload}})
                continue
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
                if message.payload.get("recoverable") is True and session.state == "inspection_active":
                    # A locator can be ambiguous without making the open browser
                    # unusable. Return to ready so the user can select again.
                    picker_sessions.transition(session, "browser_ready")
                    await _notify_editor(session, "picker.inspect.cancelled", {"message": str(message.payload.get("message", "Choose a different element or try again."))})
                    continue
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
            picker_connections.clear_agent_info(claim.user_id)
        for preview in local_previews.disconnect(claim.user_id, websocket):
            await picker_connections.send_editor(claim.user_id, preview.client_id, {"version": 1, "type": "preview.failed", "session_id": preview.id, "payload": {"run_id": preview.run_id, "status": "agent_disconnected", "code": "agent_disconnected", "message": "Local preview agent disconnected"}})
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
        user_id = int(user["id"])
        await websocket.send_json({"version": 1, "type": "editor.connected", "payload": {"agent_connected": user_id in picker_connections.agents, **picker_connections.agent_info.get(user_id, {})}})
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
