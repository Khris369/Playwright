from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.schemas.workflow_run import (
    WorkflowRunArtifactResponse,
    WorkflowRunCreate,
    WorkflowRunResponse,
    WorkflowStepRunResponse,
)
from app.schemas.troubleshoot import TroubleshootRequest, TroubleshootResponse
from app.services.troubleshoot_ai_service import TroubleshootAIService
from app.services.workflow_artifacts import resolve_artifact_path
from app.services.workflow_run_repository import WorkflowRunRepository
from app.services.workflow_runner import WorkflowRunnerService

router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])


@router.get("", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    workflow_version_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[WorkflowRunResponse]:
    return [WorkflowRunResponse(**row) for row in WorkflowRunRepository.list_runs(workflow_version_id, limit)]


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


@router.get("/{run_id}/artifacts", response_model=list[WorkflowRunArtifactResponse])
def list_workflow_run_artifacts(run_id: int) -> list[WorkflowRunArtifactResponse]:
    if WorkflowRunRepository.get_run(run_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found"
        )
    rows = WorkflowRunRepository.list_artifacts_for_run(run_id)
    return [
        WorkflowRunArtifactResponse(
            **row,
            download_url=f"/workflow-runs/{run_id}/artifacts/{row['id']}",
        )
        for row in rows
    ]


@router.get("/{run_id}/artifacts/{artifact_id}")
def download_workflow_run_artifact(run_id: int, artifact_id: int) -> FileResponse:
    artifact = WorkflowRunRepository.get_artifact(run_id, artifact_id)
    if artifact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found"
        )
    try:
        path = resolve_artifact_path(str(artifact["file_path"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found"
        ) from exc
    if not path.exists() or not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found"
        )
    mime_type = str(artifact["mime_type"])
    opens_in_browser = mime_type.startswith("image/") or mime_type.startswith("video/")
    return FileResponse(
        str(path),
        media_type=mime_type,
        filename=path.name,
        content_disposition_type="inline" if opens_in_browser else "attachment",
    )


@router.post("/{run_id}/troubleshoot", response_model=TroubleshootResponse)
def troubleshoot_workflow_run(
    run_id: int, payload: TroubleshootRequest
) -> TroubleshootResponse:
    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found"
        )
    step_rows = WorkflowRunRepository.list_step_runs(run_id)
    prompt = TroubleshootAIService.build_prompt(
        run=run, step_runs=step_rows, extra_prompt=payload.extra_prompt
    )
    try:
        used_model, analysis = TroubleshootAIService.call_chat_model(
            prompt=prompt, model=payload.model, temperature=payload.temperature
        )
        structured = TroubleshootAIService.parse_structured_analysis(analysis)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Troubleshoot AI error: {exc}",
        ) from exc
    return TroubleshootResponse(
        run_id=run_id,
        model=used_model,
        prompt=prompt,
        analysis_raw=analysis,
        analysis_structured=structured,
    )
