from __future__ import annotations

from fastapi import BackgroundTasks

from app.services.workflow_runner import WorkflowRunnerService


class WorkflowRunDispatcher:
    """Dispatch workflow execution behind a Celery-ready boundary."""

    @staticmethod
    def dispatch(run_id: int, background_tasks: BackgroundTasks) -> None:
        # Production launch path: replace this with
        # app.worker.tasks.execute_workflow_run.delay(run_id).
        background_tasks.add_task(WorkflowRunnerService.execute_run, run_id)
