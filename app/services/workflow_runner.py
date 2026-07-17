from __future__ import annotations

from typing import Any

from app.core.settings import get_settings
from app.engine.executor import StepExecutionError, execute_step
from app.engine.graph import GraphValidationError, compile_definition
from app.engine.template import resolve_value
from app.services.workflow_artifacts import record_artifact, run_artifact_dir, step_artifact_dir
from app.services.workflow_run_control import RunCancelledError, WorkflowRunControl
from app.services.workflow_version_repository import WorkflowVersionRepository
from app.services.workflow_run_repository import WorkflowRunRepository

SCREENSHOT_DELAY_MS = 1500

# Creates and executes persisted workflow runs, including status transitions,
# cancellation checks, step history, and best-effort diagnostic artifacts.

def _parse_bool(value: Any, default: bool) -> bool:
    """Convert common input/config representations to a boolean safely."""
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
    """Evaluate an if/loop condition against runtime state or user inputs."""
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


def _record_artifact_safely(
    run_id: int,
    artifact_type: str,
    path: Any,
    step_run_id: int | None = None,
    mime_type: str | None = None,
) -> None:
    """Persist an artifact when possible without masking the run outcome."""
    try:
        record_artifact(
            run_id=run_id,
            artifact_type=artifact_type,
            path=path,
            step_run_id=step_run_id,
            mime_type=mime_type,
        )
    except Exception:
        return


def _safe_artifact_name(value: str) -> str:
    """Make a step type suitable for use in a local artifact filename."""
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned[:80] or "step"


def _wait_before_screenshot(page: Any) -> None:
    """Allow transient loading states and animations to settle before capture."""
    page.wait_for_timeout(SCREENSHOT_DELAY_MS)


class WorkflowRunnerService:
    @staticmethod
    def run_workflow_version(version_id: int, inputs: dict[str, Any] | None = None) -> int:
        """Validate a version, snapshot its compiled steps, and queue a run."""
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
        """Execute a run and persist its status, step history, and failures.

        Cancellation is cooperative during the step loop; the registered
        callback also closes the browser so blocked Playwright calls can stop.
        Traces and screenshots are best-effort diagnostics, not run outcomes.
        """
        run = WorkflowRunRepository.get_run(run_id)
        if run is None:
            raise ValueError("workflow_run_not_found")
        if str(run.get("status", "")).lower() == "cancelled":
            WorkflowRunControl.clear(run_id)
            return

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
        if not WorkflowRunRepository.try_mark_run_running(run_id):
            WorkflowRunControl.clear(run_id)
            return

        settings = get_settings()
        artifacts_enabled = settings.workflow_artifacts_enabled
        trace_enabled = artifacts_enabled and settings.workflow_trace_enabled
        final_screenshot_enabled = (
            artifacts_enabled and settings.workflow_final_screenshot_enabled
        )
        step_screenshots_enabled = artifacts_enabled and _parse_bool(
            inputs.get("capture_step_screenshots"),
            settings.workflow_step_screenshots_enabled,
        )
        artifact_dir = run_artifact_dir(run_id) if artifacts_enabled else None
        step_dir = step_artifact_dir(run_id) if step_screenshots_enabled else None
        trace_path = artifact_dir / "trace.zip" if artifact_dir is not None else None
        final_screenshot_path = artifact_dir / "final.png" if artifact_dir is not None else None
        failure_screenshot_path = artifact_dir / "failure.png" if artifact_dir is not None else None

        try:
            from playwright.sync_api import sync_playwright

            headless_default = settings.playwright_headless
            headless = _parse_bool(inputs.get("headless"), headless_default)
            if "headed" in inputs:
                headless = not _parse_bool(inputs.get("headed"), True)
            slow_mo = int(inputs.get("slow_mo_ms", 0))

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless, slow_mo=slow_mo)
                context_pw = browser.new_context()
                WorkflowRunControl.register_cancel_callback(
                    run_id,
                    lambda: _close_run_browser(context_pw, browser),
                )
                if WorkflowRunControl.is_cancel_requested(run_id):
                    raise RunCancelledError("cancelled_by_user")
                if trace_enabled:
                    context_pw.tracing.start(
                        screenshots=True, snapshots=True, sources=True
                    )
                page = context_pw.new_page()
                state["page"] = page

                # Compiled steps contain explicit targets, so ID lookup avoids
                # repeatedly scanning the workflow definition.
                by_id = {str(step.get("id")): step for step in steps}
                current_id = str(steps[0].get("id")) if steps else None
                loop_counts: dict[str, int] = {}
                execution_index = 0
                while current_id is not None:
                    if WorkflowRunControl.is_cancel_requested(run_id):
                        raise RunCancelledError("cancelled_by_user")
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
                        # Control nodes select a target; registered step types
                        # perform the corresponding browser/state operation.
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
                        step_run_id = WorkflowRunRepository.create_step_run(
                            workflow_run_id=run_id,
                            step_index=execution_index,
                            step_id=str(step_id) if step_id is not None else None,
                            step_type=step_type,
                            status="passed",
                            args_json=args,
                            log_text=result.log,
                        )
                        if step_screenshots_enabled and step_dir is not None:
                            try:
                                screenshot_path = step_dir / (
                                    f"{execution_index:03d}-{_safe_artifact_name(step_type)}.png"
                                )
                                _wait_before_screenshot(page)
                                page.screenshot(path=str(screenshot_path), full_page=True)
                                _record_artifact_safely(
                                    run_id,
                                    "step_screenshot",
                                    screenshot_path,
                                    step_run_id=step_run_id,
                                    mime_type="image/png",
                                )
                            except Exception:
                                pass
                    except (KeyError, StepExecutionError, ValueError) as exc:
                        step_run_id = WorkflowRunRepository.create_step_run(
                            workflow_run_id=run_id,
                            step_index=execution_index,
                            step_id=str(step_id) if step_id is not None else None,
                            step_type=step_type,
                            status="failed",
                            args_json=args if isinstance(args, dict) else {},
                            error_text=str(exc),
                        )
                        if artifacts_enabled and failure_screenshot_path is not None:
                            try:
                                _wait_before_screenshot(page)
                                page.screenshot(
                                    path=str(failure_screenshot_path), full_page=True
                                )
                                _record_artifact_safely(
                                    run_id,
                                    "failure_screenshot",
                                    failure_screenshot_path,
                                    step_run_id=step_run_id,
                                    mime_type="image/png",
                                )
                            except Exception:
                                pass
                        if trace_enabled and trace_path is not None:
                            try:
                                context_pw.tracing.stop(path=str(trace_path))
                                _record_artifact_safely(
                                    run_id,
                                    "trace",
                                    trace_path,
                                    mime_type="application/zip",
                                )
                            except Exception:
                                pass
                        WorkflowRunRepository.finalize_run(
                            run_id, status="failed", error_summary=str(exc)
                        )
                        context_pw.close()
                        browser.close()
                        WorkflowRunControl.clear(run_id)
                        return
                    execution_index += 1
                    current_id = str(next_id) if next_id is not None else None

                if final_screenshot_enabled and final_screenshot_path is not None:
                    try:
                        _wait_before_screenshot(page)
                        page.screenshot(path=str(final_screenshot_path), full_page=True)
                        _record_artifact_safely(
                            run_id,
                            "final_screenshot",
                            final_screenshot_path,
                            mime_type="image/png",
                        )
                    except Exception:
                        pass
                if trace_enabled and trace_path is not None:
                    try:
                        context_pw.tracing.stop(path=str(trace_path))
                        _record_artifact_safely(
                            run_id,
                            "trace",
                            trace_path,
                            mime_type="application/zip",
                        )
                    except Exception:
                        pass
                context_pw.close()
                browser.close()

            WorkflowRunRepository.finalize_run(run_id, status="passed")
            WorkflowRunControl.clear(run_id)
            return
        except RunCancelledError:
            WorkflowRunRepository.finalize_run(
                run_id, status="cancelled", error_summary="cancelled_by_user"
            )
            WorkflowRunControl.clear(run_id)
            return
        except Exception as exc:
            if WorkflowRunControl.is_cancel_requested(run_id):
                WorkflowRunRepository.finalize_run(
                    run_id, status="cancelled", error_summary="cancelled_by_user"
                )
            else:
                WorkflowRunRepository.finalize_run(run_id, status="failed", error_summary="runner_error")
            WorkflowRunControl.clear(run_id)
            return


def _close_run_browser(context_pw: Any, browser: Any) -> None:
    """Close Playwright resources defensively during cancellation or cleanup."""
    try:
        context_pw.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass
