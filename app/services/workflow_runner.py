from __future__ import annotations

from typing import Any

from app.engine.steps import StepExecutionError, execute_step
from app.engine.template import resolve_value
from app.services.workflow_repository import WorkflowRepository
from app.services.workflow_run_repository import WorkflowRunRepository


def _parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return default


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

        inputs = run.get("inputs_json") or {}
        state: dict[str, Any] = {"visible_texts": [], "current_url": ""}
        context = {"inputs": inputs, "secrets": {}}
        WorkflowRunRepository.mark_run_running(run_id)

        try:
            from playwright.sync_api import sync_playwright

            headless_default = False
            headless = _parse_bool(inputs.get("headless"), headless_default)
            if "headed" in inputs:
                headless = not _parse_bool(inputs.get("headed"), True)
            headless = False
            slow_mo = int(inputs.get("slow_mo_ms", 0))

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
                context_pw = browser.new_context()
                page = context_pw.new_page()
                state["page"] = page

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
                        context_pw.close()
                        browser.close()
                        return

                context_pw.close()
                browser.close()

            WorkflowRunRepository.finalize_run(run_id, status="passed")
            return
        except Exception as exc:
            WorkflowRunRepository.finalize_run(
                run_id, status="failed", error_summary=f"runner_error: {exc}"
            )
            return
