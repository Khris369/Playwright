from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
    WorkflowVersionUpdate,
)
from app.services.workflow_repository import WorkflowRepository

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate) -> WorkflowResponse:
    row = WorkflowRepository.create_workflow(payload)
    return WorkflowResponse(**row)


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(active_only: bool = Query(default=False)) -> list[WorkflowResponse]:
    rows = WorkflowRepository.list_workflows(active_only=active_only)
    return [WorkflowResponse(**row) for row in rows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int) -> WorkflowResponse:
    row = WorkflowRepository.get_workflow(workflow_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return WorkflowResponse(**row)


@router.post(
    "/{workflow_id}/versions",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_version(
    workflow_id: int, payload: WorkflowVersionCreate
) -> WorkflowVersionResponse:
    try:
        row = WorkflowRepository.create_workflow_version(workflow_id, payload)
    except ValueError as exc:
        if str(exc) == "workflow_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
            ) from exc
        raise
    return WorkflowVersionResponse(**row)


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionResponse])
def list_workflow_versions(workflow_id: int) -> list[WorkflowVersionResponse]:
    rows = WorkflowRepository.list_workflow_versions(workflow_id)
    return [WorkflowVersionResponse(**row) for row in rows]


@router.get("/versions/{version_id}", response_model=WorkflowVersionResponse)
def get_workflow_version(version_id: int) -> WorkflowVersionResponse:
    row = WorkflowRepository.get_workflow_version(version_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow version not found"
        )
    return WorkflowVersionResponse(**row)


@router.put("/versions/{version_id}", response_model=WorkflowVersionResponse)
def update_workflow_version(
    version_id: int, payload: WorkflowVersionUpdate
) -> WorkflowVersionResponse:
    row = WorkflowRepository.update_workflow_version(version_id, payload)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow version not found"
        )
    return WorkflowVersionResponse(**row)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int) -> None:
    updated = WorkflowRepository.deactivate_workflow(workflow_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Active workflow not found"
        )
