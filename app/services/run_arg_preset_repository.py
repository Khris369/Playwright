from __future__ import annotations

import json

from app.schemas.run_arg_preset import RunArgPresetCreate, RunArgPresetUpdate
from app.services.db import get_db_cursor


class RunArgPresetRepository:
    @staticmethod
    def create_preset(payload: RunArgPresetCreate, owner_user_id: int) -> dict:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO run_arg_presets (owner_user_id, name, workflow_id, workflow_version_id, inputs_json, isActive)
                VALUES (%s, %s, %s, %s, %s, 1)
                """,
                (
                    owner_user_id,
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
        workflow_id: int | None = None, workflow_version_id: int | None = None,
        owner_user_id: int | None = None, is_admin: bool = False,
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
            if owner_user_id is not None and not is_admin:
                conditions.append("(owner_user_id = %s OR EXISTS (SELECT 1 FROM workflows w LEFT JOIN workflow_members wm ON wm.workflow_id = w.id AND wm.user_id = %s WHERE w.id = run_arg_presets.workflow_id AND (w.owner_user_id = %s OR wm.user_id IS NOT NULL)))")
                params.extend([owner_user_id, owner_user_id, owner_user_id])
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
    def update_preset(preset_id: int, payload: RunArgPresetUpdate, owner_user_id: int | None = None, is_admin: bool = False) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT id FROM run_arg_presets WHERE id = %s AND isActive = 1 AND (%s = 1 OR owner_user_id = %s)",
                (preset_id, 1 if is_admin else 0, owner_user_id),
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
    def delete_preset(preset_id: int, owner_user_id: int | None = None, is_admin: bool = False) -> bool:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "UPDATE run_arg_presets SET isActive = 0 WHERE id = %s AND isActive = 1 AND (%s = 1 OR owner_user_id = %s)",
                (preset_id, 1 if is_admin else 0, owner_user_id),
            )
            return cursor.rowcount > 0
