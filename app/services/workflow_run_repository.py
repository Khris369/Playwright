from __future__ import annotations

import json

from app.services.db import get_db_cursor


class WorkflowRunRepository:
    @staticmethod
    def create_queued_run(
        workflow_id: int, workflow_version_id: int, inputs: dict | None = None
    ) -> int:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflow_runs (
                    workflow_id, workflow_version_id, status, trigger_source, inputs_json
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    workflow_id,
                    workflow_version_id,
                    "queued",
                    "api",
                    json.dumps(inputs or {}),
                ),
            )
            run_id = int(cursor.lastrowid)
        return run_id

    @staticmethod
    def mark_run_running(run_id: int) -> None:
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
    def get_run(run_id: int) -> dict | None:
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
