from __future__ import annotations

from typing import Any

from app.engine.executor import StepExecutionError, execute_step
from app.engine.graph import GraphValidationError, compile_definition
from app.engine.template import resolve_value
from app.services.workflow_version_repository import WorkflowVersionRepository
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


def _condition_matches(args: dict[str, Any], state: dict[str, Any], inputs: dict[str, Any]) -> bool:
    key = str(args.get("state_key", ""))
    actual = inputs.get(key.removeprefix("inputs.")) if key.startswith("inputs.") else state.get(key)
    expected = args.get("value")
    operator = args.get("operator")
    if operator == "truthy":
        return bool(actual)
    if operator == "falsy":
        return not bool(actual)
    if operator == "not_equals":
        return actual != expected
    if operator == "contains":
        return str(expected) in str(actual or "")
    return actual == expected


class WorkflowRunnerService:
    @staticmethod
    def run_workflow_version(version_id: int, inputs: dict[str, Any] | None = None) -> int:
        version = WorkflowVersionRepository.get(version_id)
        if version is None:
            raise ValueError("workflow_version_not_found")

        try:
            compiled = compile_definition(version["definition_json"])
        except GraphValidationError as exc:
            raise ValueError("invalid_workflow_definition") from exc
        workflow_id = int(version["workflow_id"])
        run_id = WorkflowRunRepository.create_queued_run(
            workflow_id=workflow_id,
            workflow_version_id=version_id,
            resolved_definition={"schema_version": 2, "steps": compiled},
            inputs=inputs or {},
        )
        return run_id

    @staticmethod
    def execute_run(run_id: int) -> None:
        run = WorkflowRunRepository.get_run(run_id)
        if run is None:
            raise ValueError("workflow_run_not_found")

        definition = run.get("resolved_definition_json") or {}
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
            slow_mo = int(inputs.get("slow_mo_ms", 0))

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
                context_pw = browser.new_context()
                page = context_pw.new_page()
                state["page"] = page

                by_id = {str(step.get("id")): step for step in steps}
                current_id = str(steps[0].get("id")) if steps else None
                loop_counts: dict[str, int] = {}
                execution_index = 0
                while current_id is not None:
                    if execution_index >= 10_000:
                        raise StepExecutionError("Workflow exceeded the 10,000 node execution safety limit")
                    step = by_id.get(current_id)
                    if step is None:
                        raise StepExecutionError("Workflow points to an unknown node")
                    step_type = str(step.get("type", ""))
                    raw_args = step.get("args", {}) or {}
                    step_id = step.get("id")
                    args = resolve_value(raw_args, context)

                    try:
                        if step_type in {"__if__", "__loop__"}:
                            matched = _condition_matches(args, state, inputs)
                            if step_type == "__if__":
                                branch = "true" if matched else "false"
                            else:
                                count = loop_counts.get(current_id, 0)
                                maximum = int(args.get("max_iterations", 10))
                                branch = "done" if matched or count >= maximum else "body"
                                if branch == "body":
                                    loop_counts[current_id] = count + 1
                            next_id = (step.get("branches") or {}).get(branch)
                            from app.engine.executor import StepResult
                            result = StepResult(f"Control condition selected {branch}")
                        else:
                            result = execute_step(step_type, args, state)
                            next_id = step.get("next")
                        WorkflowRunRepository.create_step_run(
                            workflow_run_id=run_id,
                            step_index=execution_index,
                            step_id=str(step_id) if step_id is not None else None,
                            step_type=step_type,
                            status="passed",
                            args_json=args,
                            log_text=result.log,
                        )
                    except (KeyError, StepExecutionError, ValueError) as exc:
                        WorkflowRunRepository.create_step_run(
                            workflow_run_id=run_id,
                            step_index=execution_index,
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
                    execution_index += 1
                    current_id = str(next_id) if next_id is not None else None

                context_pw.close()
                browser.close()

            WorkflowRunRepository.finalize_run(run_id, status="passed")
            return
        except Exception as exc:
            WorkflowRunRepository.finalize_run(run_id, status="failed", error_summary="runner_error")
            return
