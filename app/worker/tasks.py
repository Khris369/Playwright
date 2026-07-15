from __future__ import annotations

from app.services.workflow_runner import WorkflowRunnerService
from app.worker.celery_app import celery_app


@celery_app.task(name="workflow_runs.execute")
def execute_workflow_run(run_id: int) -> None:
    WorkflowRunnerService.execute_run(run_id)
