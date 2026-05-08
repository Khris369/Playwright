from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.workflow_run import (
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowStepRunResponse,
)
from app.services.workflow_run_repository import WorkflowRunRepository
from app.services.workflow_runner import WorkflowRunnerService

router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])


@router.post("", response_model=WorkflowRunResponse, status_code=status.HTTP_201_CREATED)
def create_workflow_run(payload: WorkflowRunCreate) -> WorkflowRunResponse:
    try:
        run_id = WorkflowRunnerService.run_workflow_version(
            version_id=payload.workflow_version_id,
            inputs=payload.inputs,
        )
    except ValueError as exc:
        if str(exc) == "workflow_version_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Workflow version not found",
            ) from exc
        if str(exc) == "invalid_workflow_definition":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Invalid workflow definition",
            ) from exc
        raise

    # Execute inline so the browser launches from the same interactive process/session.
    WorkflowRunnerService.execute_run(run_id)

    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run record not found after execution",
        )
    return WorkflowRunResponse(**run)


@router.get("/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: int) -> WorkflowRunResponse:
    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found"
        )
    return WorkflowRunResponse(**run)


@router.get("/{run_id}/steps", response_model=list[WorkflowStepRunResponse])
def list_workflow_run_steps(run_id: int) -> list[WorkflowStepRunResponse]:
    rows = WorkflowRunRepository.list_step_runs(run_id)
    return [WorkflowStepRunResponse(**row) for row in rows]
