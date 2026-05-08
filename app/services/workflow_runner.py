from __future__ import annotations

from typing import Any

from app.engine.steps import StepExecutionError, execute_step
from app.engine.template import resolve_value
from app.services.workflow_repository import WorkflowRepository
from app.services.workflow_run_repository import WorkflowRunRepository


class WorkflowRunnerService:
    @staticmethod
    def run_workflow_version(version_id: int, inputs: dict[str, Any] | None = None) -> int:
        version = WorkflowRepository.get_workflow_version(version_id)
        if version is None:
            raise ValueError("workflow_version_not_found")

        workflow_id = int(version["workflow_id"])
        run_id = WorkflowRunRepository.create_queued_run(
            workflow_id=workflow_id,
            workflow_version_id=version_id,
            inputs=inputs or {},
        )
        return run_id

    @staticmethod
    def execute_run(run_id: int) -> None:
        run = WorkflowRunRepository.get_run(run_id)
        if run is None:
            raise ValueError("workflow_run_not_found")

        version = WorkflowRepository.get_workflow_version(int(run["workflow_version_id"]))
        if version is None:
            WorkflowRunRepository.finalize_run(
                run_id, status="failed", error_summary="workflow_version_not_found"
            )
            return

        definition = version["definition_json"] or {}
        steps = definition.get("steps", [])
        if not isinstance(steps, list):
            WorkflowRunRepository.finalize_run(
                run_id, status="failed", error_summary="invalid_workflow_definition"
            )
            return

        state: dict[str, Any] = {"visible_texts": [], "current_url": ""}
        context = {"inputs": run.get("inputs_json") or {}, "secrets": {}}
        WorkflowRunRepository.mark_run_running(run_id)

        try:
            for idx, step in enumerate(steps):
                step_type = str(step.get("type", ""))
                raw_args = step.get("args", {}) or {}
                step_id = step.get("id")
                args = resolve_value(raw_args, context)

                try:
                    result = execute_step(step_type, args, state)
                    WorkflowRunRepository.create_step_run(
                        workflow_run_id=run_id,
                        step_index=idx,
                        step_id=str(step_id) if step_id is not None else None,
                        step_type=step_type,
                        status="passed",
                        args_json=args,
                        log_text=result.log,
                    )
                except (KeyError, StepExecutionError, ValueError) as exc:
                    WorkflowRunRepository.create_step_run(
                        workflow_run_id=run_id,
                        step_index=idx,
                        step_id=str(step_id) if step_id is not None else None,
                        step_type=step_type,
                        status="failed",
                        args_json=args if isinstance(args, dict) else {},
                        error_text=str(exc),
                    )
                    WorkflowRunRepository.finalize_run(
                        run_id, status="failed", error_summary=str(exc)
                    )
                    return

            WorkflowRunRepository.finalize_run(run_id, status="passed")
            return
        except Exception as exc:
            WorkflowRunRepository.finalize_run(run_id, status="failed", error_summary=str(exc))
            raise
