from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.engine.graph import compile_definition
from app.schemas.workflow import WorkflowVersionCreate, WorkflowVersionUpdate
from app.services.db import get_db_cursor


@dataclass
class VersionConflictError(RuntimeError):
    code: str
    current_lock_version: int


def _workflow_version_columns() -> set[str]:
    return get_table_columns("workflow_versions")


def _workflow_columns() -> set[str]:
    return get_table_columns("workflows")


def _supports_version_locking() -> bool:
    return "lock_version" in _workflow_version_columns()


def _decode(row: dict | None) -> dict | None:
    if row is None:
        return None
    if isinstance(row.get("definition_json"), str):
        row["definition_json"] = json.loads(row["definition_json"])
    row["is_published"] = bool(row.get("is_published", 0))
    row["lock_version"] = int(row.get("lock_version", 0) or 0)
    return row


def _blank_definition() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "graph": {
            "nodes": [{"id": str(uuid.uuid4()), "kind": "start", "position": {"x": 80, "y": 160}}],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


def _select_columns_sql() -> str:
    columns = _workflow_version_columns()
    parts = [
        "id",
        "workflow_id",
        "version_number",
        "is_published",
        "definition_json",
    ]

    for optional_column in ("created_by_user_id", "updated_by_user_id"):
        if optional_column in columns:
            parts.append(optional_column)
        else:
            parts.append(f"NULL AS {optional_column}")

    if "lock_version" in columns:
        parts.append("lock_version")
    else:
        parts.append("0 AS lock_version")

    parts.extend(["created_at", "updated_at"])
    return ", ".join(parts)


def _touch_workflow(cursor, workflow_id: int, user_id: int | None) -> None:
    workflow_columns = _workflow_columns()
    set_parts = ["updated_at = CURRENT_TIMESTAMP"]
    values: list[object] = []
    if "updated_by_user_id" in workflow_columns:
        set_parts.insert(0, "updated_by_user_id = %s")
        values.append(user_id)
    values.append(workflow_id)
    cursor.execute(
        f"UPDATE workflows SET {', '.join(set_parts)} WHERE id = %s",
        tuple(values),
    )


class WorkflowVersionRepository:
    @staticmethod
    def create(workflow_id: int, payload: WorkflowVersionCreate, user_id: int | None = None) -> dict:
        definition = payload.definition_json or _blank_definition()
        compile_definition(definition)

        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT id FROM workflows WHERE id = %s", (workflow_id,))
            if cursor.fetchone() is None:
                raise ValueError("workflow_not_found")

            if payload.base_version_id is not None:
                cursor.execute(
                    "SELECT definition_json FROM workflow_versions WHERE id = %s",
                    (payload.base_version_id,),
                )
                base_row = cursor.fetchone()
                if base_row is None:
                    raise ValueError("base_version_not_found")
                if payload.definition_json is None:
                    definition = base_row["definition_json"]
                    if isinstance(definition, str):
                        definition = json.loads(definition)
                    compile_definition(definition)

            cursor.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version "
                "FROM workflow_versions WHERE workflow_id = %s",
                (workflow_id,),
            )
            next_version = int(cursor.fetchone()["next_version"])

            version_columns = _workflow_version_columns()
            insert_columns = ["workflow_id", "version_number", "is_published", "definition_json"]
            insert_values: list[object] = [workflow_id, next_version, 0, json.dumps(definition)]

            if "created_by_user_id" in version_columns:
                insert_columns.insert(2, "created_by_user_id")
                insert_values.insert(2, user_id)
            if "updated_by_user_id" in version_columns:
                insert_columns.insert(3 if "created_by_user_id" in version_columns else 2, "updated_by_user_id")
                insert_values.insert(3 if "created_by_user_id" in version_columns else 2, user_id)
            if "lock_version" in version_columns:
                insert_columns.append("lock_version")
                insert_values.append(0)

            placeholders = ", ".join(["%s"] * len(insert_columns))
            cursor.execute(
                f"INSERT INTO workflow_versions ({', '.join(insert_columns)}) VALUES ({placeholders})",
                tuple(insert_values),
            )

            version_id = int(cursor.lastrowid)
            _touch_workflow(cursor, workflow_id, user_id)
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions WHERE id = %s",
                (version_id,),
            )
            return _decode(cursor.fetchone())

    @staticmethod
    def list(workflow_id: int) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions "
                "WHERE workflow_id = %s ORDER BY version_number DESC",
                (workflow_id,),
            )
            return [_decode(row) for row in cursor.fetchall()]

    @staticmethod
    def get(version_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions WHERE id = %s",
                (version_id,),
            )
            return _decode(cursor.fetchone())

    @staticmethod
    def update(version_id: int, payload: WorkflowVersionUpdate, user_id: int | None = None) -> dict | None:
        compile_definition(payload.definition_json)

        with get_db_cursor() as (_, cursor):
            lock_sql = " FOR UPDATE" if _supports_version_locking() else ""
            cursor.execute(
                "SELECT workflow_id, is_published, "
                + ("lock_version " if _supports_version_locking() else "0 AS lock_version ")
                + f"FROM workflow_versions WHERE id = %s{lock_sql}",
                (version_id,),
            )
            current = cursor.fetchone()
            if current is None:
                return None

            lock_version = int(current.get("lock_version", 0) or 0)
            if bool(current["is_published"]):
                raise VersionConflictError("version_published", lock_version)
            if _supports_version_locking() and lock_version != payload.expected_lock_version:
                raise VersionConflictError("version_conflict", lock_version)

            set_parts = ["definition_json = %s"]
            values: list[object] = [json.dumps(payload.definition_json)]
            if "updated_by_user_id" in _workflow_version_columns():
                set_parts.append("updated_by_user_id = %s")
                values.append(user_id)
            if _supports_version_locking():
                set_parts.append("lock_version = lock_version + 1")

            values.append(version_id)
            cursor.execute(
                f"UPDATE workflow_versions SET {', '.join(set_parts)} WHERE id = %s",
                tuple(values),
            )

            _touch_workflow(cursor, int(current["workflow_id"]), user_id)
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions WHERE id = %s",
                (version_id,),
            )
            return _decode(cursor.fetchone())

    @staticmethod
    def set_published(
        version_id: int,
        expected_lock_version: int,
        published: bool,
        user_id: int | None = None,
    ) -> dict | None:
        with get_db_cursor() as (_, cursor):
            lock_sql = " FOR UPDATE" if _supports_version_locking() else ""
            cursor.execute(
                "SELECT workflow_id, definition_json, "
                + ("lock_version " if _supports_version_locking() else "0 AS lock_version ")
                + f"FROM workflow_versions WHERE id = %s{lock_sql}",
                (version_id,),
            )
            current = cursor.fetchone()
            if current is None:
                return None

            lock_version = int(current.get("lock_version", 0) or 0)
            if _supports_version_locking() and lock_version != expected_lock_version:
                raise VersionConflictError("version_conflict", lock_version)

            definition = current["definition_json"]
            if isinstance(definition, str):
                definition = json.loads(definition)
            if published:
                compile_definition(definition)

            set_parts = ["is_published = %s"]
            values: list[object] = [1 if published else 0]
            if "updated_by_user_id" in _workflow_version_columns():
                set_parts.append("updated_by_user_id = %s")
                values.append(user_id)
            if _supports_version_locking():
                set_parts.append("lock_version = lock_version + 1")

            values.append(version_id)
            cursor.execute(
                f"UPDATE workflow_versions SET {', '.join(set_parts)} WHERE id = %s",
                tuple(values),
            )

            _touch_workflow(cursor, int(current["workflow_id"]), user_id)
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions WHERE id = %s",
                (version_id,),
            )
            return _decode(cursor.fetchone())
