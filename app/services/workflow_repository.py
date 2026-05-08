from __future__ import annotations

import json

from app.schemas.workflow import WorkflowCreate, WorkflowVersionCreate
from app.services.db import get_db_cursor


class WorkflowRepository:
    @staticmethod
    def create_workflow(payload: WorkflowCreate) -> dict:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO workflows (name, description, status)
                VALUES (%s, %s, %s)
                """,
                (payload.name, payload.description, payload.status),
            )
            workflow_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT id, name, description, status, created_at, updated_at
                FROM workflows
                WHERE id = %s
                """,
                (workflow_id,),
            )
            return cursor.fetchone()

    @staticmethod
    def list_workflows() -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, name, description, status, created_at, updated_at
                FROM workflows
                ORDER BY created_at DESC
                """
            )
            return list(cursor.fetchall())

    @staticmethod
    def get_workflow(workflow_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, name, description, status, created_at, updated_at
                FROM workflows
                WHERE id = %s
                """,
                (workflow_id,),
            )
            return cursor.fetchone()

    @staticmethod
    def create_workflow_version(
        workflow_id: int, payload: WorkflowVersionCreate
    ) -> dict:
        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT id FROM workflows WHERE id = %s", (workflow_id,))
            if cursor.fetchone() is None:
                raise ValueError("workflow_not_found")

            cursor.execute(
                """
                INSERT INTO workflow_versions (
                    workflow_id, version_number, is_published, definition_json
                )
                VALUES (%s, %s, %s, %s)
                """,
                (
                    str(workflow_id),
                    payload.version_number,
                    1 if payload.is_published else 0,
                    json.dumps(payload.definition_json),
                ),
            )
            version_id = cursor.lastrowid
            cursor.execute(
                """
                SELECT id, workflow_id, version_number, is_published, definition_json, created_at
                FROM workflow_versions
                WHERE id = %s
                """,
                (version_id,),
            )
            row = cursor.fetchone()
            if isinstance(row.get("definition_json"), str):
                row["definition_json"] = json.loads(row["definition_json"])
            row["is_published"] = bool(row["is_published"])
            return row

    @staticmethod
    def list_workflow_versions(workflow_id: int) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_id, version_number, is_published, definition_json, created_at
                FROM workflow_versions
                WHERE workflow_id = %s
                ORDER BY version_number DESC
                """,
                (workflow_id,),
            )
            rows = list(cursor.fetchall())
            for row in rows:
                if isinstance(row.get("definition_json"), str):
                    row["definition_json"] = json.loads(row["definition_json"])
                row["is_published"] = bool(row["is_published"])
            return rows

    @staticmethod
    def get_workflow_version(version_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, workflow_id, version_number, is_published, definition_json, created_at
                FROM workflow_versions
                WHERE id = %s
                """,
                (version_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row.get("definition_json"), str):
                row["definition_json"] = json.loads(row["definition_json"])
            row["is_published"] = bool(row["is_published"])
            return row
