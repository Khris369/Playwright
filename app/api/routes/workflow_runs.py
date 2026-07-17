from __future__ import annotations

import shutil
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
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
from app.services.workflow_run_control import WorkflowRunControl
from app.services.workflow_run_repository import WorkflowRunRepository
from app.services.workflow_run_dispatcher import WorkflowRunDispatcher
from app.services.workflow_runner import WorkflowRunnerService
from app.core.auth import require_permission, require_workflow_access
from app.services.permission_repository import PermissionRepository

# Coordinates run APIs while keeping execution, persistence, and artifact path
# rules in their respective services. Trace viewing uses a non-shell command.
router = APIRouter(prefix="/workflow-runs", tags=["workflow-runs"])
logger = logging.getLogger(__name__)


def _playwright_executable() -> str | None:
    """Find the Playwright CLI beside the interpreter or on PATH."""
    local_exe = Path(sys.executable).with_name("playwright.exe")
    if local_exe.exists() and local_exe.is_file():
        return str(local_exe)
    return shutil.which("playwright")


def _open_trace_viewer(trace_path: Path) -> None:
    """Open a validated trace archive using the local Playwright CLI."""
    executable = _playwright_executable()
    if executable is None:
        raise RuntimeError("Playwright CLI not found")
    subprocess.Popen(
        [executable, "show-trace", str(trace_path)],
        shell=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


@router.get("", response_model=list[WorkflowRunResponse])
def list_workflow_runs(
    workflow_version_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    user: dict = Depends(require_permission("workflow.view")),
) -> list[WorkflowRunResponse]:
    """List recent runs, optionally filtered to a workflow version."""
    return [
        WorkflowRunResponse(**row)
        for row in WorkflowRunRepository.list_runs(
            workflow_version_id,
            limit,
            int(user["id"]),
            "admin" in user.get("roles", []),
        )
    ]


@router.post("", response_model=WorkflowRunResponse, status_code=status.HTTP_201_CREATED)
def create_workflow_run(
    payload: WorkflowRunCreate,
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_workflow_access("workflow.run")),
) -> WorkflowRunResponse:
    """Validate and queue a run, then schedule its execution."""
    if "admin" not in user.get("roles", []):
        workflow_id = PermissionRepository.resource_workflow_id("version", payload.workflow_version_id)
        if workflow_id is None or not PermissionRepository.can_access_workflow(int(user["id"]), workflow_id, "workflow.run"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow version not found")
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
    WorkflowRunDispatcher.dispatch(run_id, background_tasks)

    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Run record not found after execution",
        )
    return WorkflowRunResponse(**run)


@router.get("/{run_id}", response_model=WorkflowRunResponse)
def get_workflow_run(run_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> WorkflowRunResponse:
    """Return one run or a not-found response."""
    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found"
        )
    return WorkflowRunResponse(**run)


@router.post("/{run_id}/stop")
def stop_workflow_run(run_id: int, user: dict = Depends(require_workflow_access("workflow.run"))) -> dict[str, str]:
    """Cancel queued work immediately or request cooperative cancellation."""
    run = WorkflowRunRepository.get_run(run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow run not found"
        )
    current_status = str(run.get("status", "")).lower()
    if current_status == "queued":
        WorkflowRunRepository.cancel_queued_run(run_id)
        WorkflowRunControl.request_cancel(run_id)
        return {"status": "cancelled"}
    if current_status == "running":
        WorkflowRunControl.request_cancel(run_id)
        return {"status": "stopping"}
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Run is not active",
    )


@router.get("/{run_id}/steps", response_model=list[WorkflowStepRunResponse])
def list_workflow_run_steps(run_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> list[WorkflowStepRunResponse]:
    """Return persisted step attempts for a run."""
    rows = WorkflowRunRepository.list_step_runs(run_id)
    return [WorkflowStepRunResponse(**row) for row in rows]


@router.get("/{run_id}/artifacts", response_model=list[WorkflowRunArtifactResponse])
def list_workflow_run_artifacts(run_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> list[WorkflowRunArtifactResponse]:
    """List artifact metadata and construct client download URLs."""
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
def download_workflow_run_artifact(run_id: int, artifact_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> FileResponse:
    """Serve a run-owned artifact after containment and file checks."""
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


@router.post("/{run_id}/artifacts/{artifact_id}/open-trace")
def open_workflow_run_trace(run_id: int, artifact_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> dict[str, str]:
    """Launch only a run-owned ZIP trace through the local viewer."""
    artifact = WorkflowRunRepository.get_artifact(run_id, artifact_id)
    if artifact is None or str(artifact.get("artifact_type")) != "trace":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trace artifact not found"
        )
    try:
        path = resolve_artifact_path(str(artifact["file_path"]))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trace artifact not found"
        ) from exc
    if not path.exists() or not path.is_file() or path.suffix.lower() != ".zip":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Trace artifact not found"
        )
    try:
        _open_trace_viewer(path)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc
    return {"status": "opened"}


@router.post("/{run_id}/troubleshoot", response_model=TroubleshootResponse)
def troubleshoot_workflow_run(
    run_id: int, payload: TroubleshootRequest, user: dict = Depends(require_workflow_access("workflow.view"))
) -> TroubleshootResponse:
    """Send run diagnostics to the AI service and return structured advice."""
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
        logger.exception("Workflow troubleshooting provider or parsing failure: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Troubleshooting assistant could not produce a safe response",
        ) from exc
    return TroubleshootResponse(
        run_id=run_id,
        model=used_model,
        prompt=prompt,
        analysis_raw=analysis,
        analysis_structured=structured,
    )
