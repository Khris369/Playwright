from __future__ import annotations

import json

from app.schemas.run_arg_preset import RunArgPresetCreate, RunArgPresetUpdate
from app.services.db import get_db_cursor


class RunArgPresetRepository:
    @staticmethod
    def create_preset(payload: RunArgPresetCreate) -> dict:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO run_arg_presets (name, workflow_id, workflow_version_id, inputs_json, isActive)
                VALUES (%s, %s, %s, %s, 1)
                """,
                (
                    payload.name,
                    payload.workflow_id,
                    payload.workflow_version_id,
                    json.dumps(payload.inputs_json),
                ),
            )
            preset_id = int(cursor.lastrowid)
            cursor.execute(
                """
                SELECT id, name, workflow_id, workflow_version_id, inputs_json, created_at, updated_at
                FROM run_arg_presets
                WHERE id = %s AND isActive = 1
                """,
                (preset_id,),
            )
            row = cursor.fetchone()
            if isinstance(row.get("inputs_json"), str):
                row["inputs_json"] = json.loads(row["inputs_json"])
            return row

    @staticmethod
    def list_presets(
        workflow_id: int | None = None, workflow_version_id: int | None = None
    ) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            query = """
                SELECT id, name, workflow_id, workflow_version_id, inputs_json, created_at, updated_at
                FROM run_arg_presets
            """
            conditions: list[str] = ["isActive = 1"]
            params: list[int] = []
            if workflow_id is not None:
                conditions.append("workflow_id = %s")
                params.append(workflow_id)
            if workflow_version_id is not None:
                conditions.append("workflow_version_id = %s")
                params.append(workflow_version_id)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY updated_at DESC, id DESC"

            cursor.execute(query, tuple(params))
            rows = list(cursor.fetchall())
            for row in rows:
                if isinstance(row.get("inputs_json"), str):
                    row["inputs_json"] = json.loads(row["inputs_json"])
            return rows

    @staticmethod
    def get_preset(preset_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT id, name, workflow_id, workflow_version_id, inputs_json, created_at, updated_at
                FROM run_arg_presets
                WHERE id = %s AND isActive = 1
                """,
                (preset_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row.get("inputs_json"), str):
                row["inputs_json"] = json.loads(row["inputs_json"])
            return row

    @staticmethod
    def update_preset(preset_id: int, payload: RunArgPresetUpdate) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT id FROM run_arg_presets WHERE id = %s AND isActive = 1",
                (preset_id,),
            )
            if cursor.fetchone() is None:
                return None

            cursor.execute(
                """
                UPDATE run_arg_presets
                SET name = %s, workflow_id = %s, workflow_version_id = %s, inputs_json = %s
                WHERE id = %s AND isActive = 1
                """,
                (
                    payload.name,
                    payload.workflow_id,
                    payload.workflow_version_id,
                    json.dumps(payload.inputs_json),
                    preset_id,
                ),
            )
            cursor.execute(
                """
                SELECT id, name, workflow_id, workflow_version_id, inputs_json, created_at, updated_at
                FROM run_arg_presets
                WHERE id = %s AND isActive = 1
                """,
                (preset_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            if isinstance(row.get("inputs_json"), str):
                row["inputs_json"] = json.loads(row["inputs_json"])
            return row

    @staticmethod
    def delete_preset(preset_id: int) -> bool:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "UPDATE run_arg_presets SET isActive = 0 WHERE id = %s AND isActive = 1",
                (preset_id,),
            )
            return cursor.rowcount > 0
