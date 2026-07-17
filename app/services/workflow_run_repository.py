from __future__ import annotations

import json
from datetime import datetime

from app.services.db import get_db_cursor

# Repository boundary for workflow runs, step attempts, and artifact metadata.
# JSON columns are decoded here so callers receive ordinary Python structures.

class WorkflowRunRepository:
    @staticmethod
    def create_queued_run(
        workflow_id: int, workflow_version_id: int, resolved_definition: dict,
        inputs: dict | None = None
    ) -> int:
        """Insert an immutable run snapshot in the queued state."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflow_runs (
                    workflow_id, workflow_version_id, status, trigger_source, inputs_json,
                    resolved_definition_json
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    workflow_id,
                    workflow_version_id,
                    "queued",
                    "api",
                    json.dumps(inputs or {}),
                    json.dumps(resolved_definition),
                ),
            )
            run_id = int(cursor.lastrowid)
        return run_id

    @staticmethod
    def list_runs(workflow_version_id: int | None = None, limit: int = 20, user_id: int | None = None, is_admin: bool = False) -> list[dict]:
        """Return recent runs, optionally limited to one workflow version."""
        with get_db_cursor() as (_, cursor):
            query = """SELECT id, workflow_id, workflow_version_id, status, trigger_source,
                       inputs_json, resolved_definition_json, started_at, finished_at,
                       error_summary, created_at FROM workflow_runs"""
            conditions: list[str] = []
            params: list[object] = []
            if workflow_version_id is not None:
                conditions.append("workflow_version_id = %s")
                params.append(workflow_version_id)
            if user_id is not None and not is_admin:
                conditions.append("EXISTS (SELECT 1 FROM workflows w LEFT JOIN workflow_members wm ON wm.workflow_id = w.id AND wm.user_id = %s WHERE w.id = workflow_runs.workflow_id AND (w.owner_user_id = %s OR wm.user_id IS NOT NULL))")
                params.extend([user_id, user_id])
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            cursor.execute(query, tuple(params))
            rows = list(cursor.fetchall())
            for row in rows:
                for key in ("inputs_json", "resolved_definition_json"):
                    if isinstance(row.get(key), str):
                        row[key] = json.loads(row[key])
            return rows

    @staticmethod
    def mark_run_running(run_id: int) -> None:
        """Mark a run as running without checking its previous state."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE workflow_runs
                SET status = %s, started_at = NOW()
                WHERE id = %s
                """,
                ("running", run_id),
            )

    @staticmethod
    def try_mark_run_running(run_id: int) -> bool:
        """Atomically claim only a queued run, preventing duplicate workers."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE workflow_runs
                SET status = %s, started_at = NOW()
                WHERE id = %s AND status = %s
                """,
                ("running", run_id, "queued"),
            )
            return cursor.rowcount > 0

    @staticmethod
    def create_step_run(
        workflow_run_id: int,
        step_index: int,
        step_id: str | None,
        step_type: str,
        status: str,
        args_json: dict,
        log_text: str | None = None,
        error_text: str | None = None,
    ) -> int:
        """Record one attempted step, including inputs and result/error text."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflow_step_runs (
                    workflow_run_id, step_index, step_id, step_type, status,
                    args_json, started_at, finished_at, log_text, error_text
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), %s, %s)
                """,
                (
                    workflow_run_id,
                    step_index,
                    step_id,
                    step_type,
                    status,
                    json.dumps(args_json),
                    log_text,
                    error_text,
                ),
            )
            step_run_id = int(cursor.lastrowid)
        return step_run_id

    @staticmethod
    def finalize_run(run_id: int, status: str, error_summary: str | None = None) -> None:
        """Write the terminal status and completion timestamp for a run."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE workflow_runs
                SET status = %s, error_summary = %s, finished_at = NOW()
                WHERE id = %s
                """,
                (status, error_summary, run_id),
            )

    @staticmethod
    def cancel_queued_run(run_id: int, error_summary: str = "cancelled_by_user") -> bool:
        """Cancel only queued work; running work is handled by run control."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE workflow_runs
                SET status = %s, error_summary = %s, finished_at = NOW()
                WHERE id = %s AND status = %s
                """,
                ("cancelled", error_summary, run_id, "queued"),
            )
            return cursor.rowcount > 0

    @staticmethod
    def get_run(run_id: int) -> dict | None:
        """Fetch one run and decode its stored input/definition snapshots."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_id, workflow_version_id, status, trigger_source,
                       inputs_json, resolved_definition_json, started_at, finished_at, error_summary, created_at
                FROM workflow_runs
                WHERE id = %s
                """,
                (run_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row.get("inputs_json"), str):
                row["inputs_json"] = json.loads(row["inputs_json"])
            if isinstance(row.get("resolved_definition_json"), str):
                row["resolved_definition_json"] = json.loads(
                    row["resolved_definition_json"]
                )
            return row

    @staticmethod
    def list_step_runs(run_id: int) -> list[dict]:
        """Return step attempts in execution order for history and diagnostics."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_run_id, step_index, step_id, step_type, status,
                       args_json, started_at, finished_at, duration_ms, log_text, error_text, screenshot_path, created_at
                FROM workflow_step_runs
                WHERE workflow_run_id = %s
                ORDER BY step_index ASC
                """,
                (run_id,),
            )
            rows = list(cursor.fetchall())
            for row in rows:
                if isinstance(row.get("args_json"), str):
                    row["args_json"] = json.loads(row["args_json"])
            return rows

    @staticmethod
    def create_artifact(
        workflow_run_id: int,
        artifact_type: str,
        file_path: str,
        mime_type: str,
        size_bytes: int,
        step_run_id: int | None = None,
    ) -> int:
        """Persist metadata for a file already created by the runner."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflow_run_artifacts (
                    workflow_run_id, step_run_id, artifact_type, file_path,
                    mime_type, size_bytes
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    workflow_run_id,
                    step_run_id,
                    artifact_type,
                    file_path,
                    mime_type,
                    size_bytes,
                ),
            )
            artifact_id = int(cursor.lastrowid)
        return artifact_id

    @staticmethod
    def list_artifacts_for_run(run_id: int) -> list[dict]:
        """List artifact metadata in stable creation order."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_run_id, step_run_id, artifact_type, file_path,
                       mime_type, size_bytes, created_at
                FROM workflow_run_artifacts
                WHERE workflow_run_id = %s
                ORDER BY created_at ASC, id ASC
                """,
                (run_id,),
            )
            return list(cursor.fetchall())

    @staticmethod
    def get_artifact(run_id: int, artifact_id: int) -> dict | None:
        """Fetch an artifact only when it belongs to the requested run."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_run_id, step_run_id, artifact_type, file_path,
                       mime_type, size_bytes, created_at
                FROM workflow_run_artifacts
                WHERE workflow_run_id = %s AND id = %s
                """,
                (run_id, artifact_id),
            )
            return cursor.fetchone()

    @staticmethod
    def list_artifacts_created_before(cutoff: datetime, limit: int = 500) -> list[dict]:
        """Select a bounded cleanup batch of expired artifact metadata."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_run_id, step_run_id, artifact_type, file_path,
                       mime_type, size_bytes, created_at
                FROM workflow_run_artifacts
                WHERE created_at < %s
                ORDER BY created_at ASC, id ASC
                LIMIT %s
                """,
                (cutoff, limit),
            )
            return list(cursor.fetchall())

    @staticmethod
    def delete_artifacts(artifact_ids: list[int]) -> int:
        """Delete a selected artifact batch after files have been handled."""
        if not artifact_ids:
            return 0
        placeholders = ", ".join(["%s"] * len(artifact_ids))
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"DELETE FROM workflow_run_artifacts WHERE id IN ({placeholders})",
                tuple(artifact_ids),
            )
            return int(cursor.rowcount)
