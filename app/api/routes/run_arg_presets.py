from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.run_arg_preset import (
    RunArgPresetCreate,
    RunArgPresetResponse,
    RunArgPresetUpdate,
)
from app.services.run_arg_preset_repository import RunArgPresetRepository
from app.core.auth import require_permission, require_workflow_access
from app.services.permission_repository import PermissionRepository

router = APIRouter(prefix="/run-arg-presets", tags=["run-arg-presets"])


@router.post("", response_model=RunArgPresetResponse, status_code=status.HTTP_201_CREATED)
def create_run_arg_preset(payload: RunArgPresetCreate, user: dict = Depends(require_permission("workflow.run"))) -> RunArgPresetResponse:
    if payload.workflow_id is not None and "admin" not in user.get("roles", []):
        if not PermissionRepository.can_access_workflow(int(user["id"]), payload.workflow_id, "workflow.run"):
            raise HTTPException(status_code=404, detail="Workflow not found")
    row = RunArgPresetRepository.create_preset(payload, int(user["id"]))
    return RunArgPresetResponse(**row)


@router.get("", response_model=list[RunArgPresetResponse])
def list_run_arg_presets(
    workflow_id: int | None = Query(default=None),
    workflow_version_id: int | None = Query(default=None),
    user: dict = Depends(require_permission("workflow.view")),
) -> list[RunArgPresetResponse]:
    rows = RunArgPresetRepository.list_presets(
        workflow_id=workflow_id,
        workflow_version_id=workflow_version_id,
        owner_user_id=int(user["id"]),
        is_admin="admin" in user.get("roles", []),
    )
    return [RunArgPresetResponse(**row) for row in rows]


@router.put("/{preset_id}", response_model=RunArgPresetResponse)
def update_run_arg_preset(
    preset_id: int, payload: RunArgPresetUpdate, user: dict = Depends(require_workflow_access("workflow.run"))
) -> RunArgPresetResponse:
    row = RunArgPresetRepository.update_preset(
        preset_id,
        payload,
        owner_user_id=int(user["id"]),
        is_admin="admin" in user.get("roles", []),
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run args preset not found"
        )
    return RunArgPresetResponse(**row)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run_arg_preset(preset_id: int, user: dict = Depends(require_workflow_access("workflow.delete"))) -> None:
    deleted = RunArgPresetRepository.delete_preset(
        preset_id,
        owner_user_id=int(user["id"]),
        is_admin="admin" in user.get("roles", []),
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run args preset not found"
        )
