from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.run_arg_preset import (
    RunArgPresetCreate,
    RunArgPresetResponse,
    RunArgPresetUpdate,
)
from app.services.run_arg_preset_repository import RunArgPresetRepository
from app.core.auth import current_user

router = APIRouter(prefix="/run-arg-presets", tags=["run-arg-presets"])


@router.post("", response_model=RunArgPresetResponse, status_code=status.HTTP_201_CREATED)
def create_run_arg_preset(payload: RunArgPresetCreate, user: dict = Depends(current_user)) -> RunArgPresetResponse:
    row = RunArgPresetRepository.create_preset(payload)
    return RunArgPresetResponse(**row)


@router.get("", response_model=list[RunArgPresetResponse])
def list_run_arg_presets(
    workflow_id: int | None = Query(default=None),
    workflow_version_id: int | None = Query(default=None),
    user: dict = Depends(current_user),
) -> list[RunArgPresetResponse]:
    rows = RunArgPresetRepository.list_presets(
        workflow_id=workflow_id, workflow_version_id=workflow_version_id
    )
    return [RunArgPresetResponse(**row) for row in rows]


@router.put("/{preset_id}", response_model=RunArgPresetResponse)
def update_run_arg_preset(
    preset_id: int, payload: RunArgPresetUpdate, user: dict = Depends(current_user)
) -> RunArgPresetResponse:
    row = RunArgPresetRepository.update_preset(preset_id, payload)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run args preset not found"
        )
    return RunArgPresetResponse(**row)


@router.delete("/{preset_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_run_arg_preset(preset_id: int, user: dict = Depends(current_user)) -> None:
    deleted = RunArgPresetRepository.delete_preset(preset_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Run args preset not found"
        )
