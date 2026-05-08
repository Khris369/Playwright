from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
)
from app.services.workflow_repository import WorkflowRepository

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(payload: WorkflowCreate) -> WorkflowResponse:
    row = WorkflowRepository.create_workflow(payload)
    return WorkflowResponse(**row)


@router.get("", response_model=list[WorkflowResponse])
def list_workflows() -> list[WorkflowResponse]:
    rows = WorkflowRepository.list_workflows()
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
