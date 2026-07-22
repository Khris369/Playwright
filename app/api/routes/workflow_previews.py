from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.auth import current_user
from app.schemas.local_preview import CreateLocalPreviewRequest, LocalPreviewResponse, PreviewInspectionCancelRequest, PreviewInspectionPickRequest
from app.services.local_preview_service import local_previews
from app.services.permission_repository import PermissionRepository
from app.services.picker_connection_manager import picker_connections
from app.services.workflow_run_repository import WorkflowRunRepository

router = APIRouter(prefix="/workflow-previews", tags=["workflow-previews"])


def _response(run_id: int, session_id: str | None = None, session=None) -> LocalPreviewResponse:
    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Preview not found")
    return LocalPreviewResponse(**run, preview_session_id=session_id, current_node_id=getattr(session, "current_node_id", None), current_node_type=getattr(session, "current_node_type", None), current_url=getattr(session, "current_url", None), steps=WorkflowRunRepository.list_step_runs(run_id))


@router.post("", response_model=LocalPreviewResponse, status_code=status.HTTP_201_CREATED)
async def create_preview(payload: CreateLocalPreviewRequest, user: dict = Depends(current_user)) -> LocalPreviewResponse:
    user_id = int(user["id"])
    workflow_id = PermissionRepository.resource_workflow_id("version", payload.workflow_version_id)
    if workflow_id is None or ("admin" not in user.get("roles", []) and not PermissionRepository.can_access_workflow(user_id, workflow_id, "workflow.edit")):
        raise HTTPException(status_code=404, detail="Workflow version not found")
    connection = picker_connections.agents.get(user_id)
    if connection is None:
        raise HTTPException(status_code=409, detail="Local preview agent is not connected")
    try:
        session = local_previews.create(user_id=user_id, client_id=payload.client_id, workflow_version_id=payload.workflow_version_id, definition=payload.definition, inputs=payload.inputs, target_node_id=payload.target_node_id, connection=connection, confirm_side_effects=payload.confirm_side_effects)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    delivered = await picker_connections.send_agent(user_id, {"version": 1, "type": "preview.start", "session_id": session.id, "payload": {"run_id": session.run_id, "target_node_id": session.target_node_id, "steps": session.plan, "inputs": session.inputs, "max_steps": 10_000}})
    if not delivered:
        local_previews.disconnect(user_id, connection)
        raise HTTPException(status_code=409, detail="Local preview agent is not connected")
    return _response(session.run_id, session.id, session)


@router.get("/{run_id}", response_model=LocalPreviewResponse)
def get_preview(run_id: int, user: dict = Depends(current_user)) -> LocalPreviewResponse:
    session = local_previews.get_owned(run_id, int(user["id"]))
    run = WorkflowRunRepository.get_run(run_id)
    if run is None or run.get("execution_mode") != "local_preview" or int(run.get("created_by_user_id") or 0) != int(user["id"]):
        raise HTTPException(status_code=404, detail="Preview not found")
    return _response(run_id, session.id if session else None, session)


@router.post("/{run_id}/stop", response_model=LocalPreviewResponse)
async def stop_preview(run_id: int, user: dict = Depends(current_user)) -> LocalPreviewResponse:
    session = local_previews.get_owned(run_id, int(user["id"]))
    if session is None:
        raise HTTPException(status_code=404, detail="Active preview not found")
    await picker_connections.send_agent(session.user_id, {"version": 1, "type": "preview.stop", "session_id": session.id, "payload": {"run_id": run_id}})
    return _response(run_id, session.id, session)


@router.post("/{run_id}/close")
async def close_preview(run_id: int, user: dict = Depends(current_user)) -> dict[str, bool]:
    session = local_previews.get_owned(run_id, int(user["id"]))
    if session is None:
        raise HTTPException(status_code=404, detail="Preview browser not found")
    await picker_connections.send_agent(session.user_id, {"version": 1, "type": "preview.inspection.close", "session_id": session.id, "payload": {"run_id": run_id}})
    session.inspection_state = "closing"
    return {"closed": True}


@router.post("/{run_id}/inspection/pick")
async def start_preview_pick(run_id: int, payload: PreviewInspectionPickRequest, user: dict = Depends(current_user)) -> dict[str, str]:
    try:
        session, request_id = local_previews.begin_pick(run_id, int(user["id"]), payload.client_id, payload.node_id, payload.field_path)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    delivered = await picker_connections.send_agent(session.user_id, {"version": 1, "type": "preview.inspection.pick.start", "session_id": session.id, "payload": {"run_id": run_id, "pick_request_id": request_id}})
    if not delivered:
        session.inspection_state, session.pick_request = "closed", None
        raise HTTPException(status_code=409, detail="Preview browser is unavailable")
    return {"pick_request_id": request_id}


@router.post("/{run_id}/inspection/cancel")
async def cancel_preview_pick(run_id: int, payload: PreviewInspectionCancelRequest, user: dict = Depends(current_user)) -> dict[str, bool]:
    session = local_previews.cancel_pick(run_id, int(user["id"]), payload.pick_request_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Preview pick request not found")
    await picker_connections.send_agent(session.user_id, {"version": 1, "type": "preview.inspection.pick.cancel", "session_id": session.id, "payload": {"run_id": run_id, "pick_request_id": payload.pick_request_id}})
    return {"cancelled": True}
