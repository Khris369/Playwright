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


def _decode(row: dict | None) -> dict | None:
    if row is None:
        return None
    if isinstance(row.get("definition_json"), str):
        row["definition_json"] = json.loads(row["definition_json"])
    row["is_published"] = bool(row["is_published"])
    row["lock_version"] = int(row.get("lock_version", 0))
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


SELECT_COLUMNS = """id, workflow_id, version_number, is_published, definition_json,
                    lock_version, created_at, updated_at"""


class WorkflowVersionRepository:
    @staticmethod
    def create(workflow_id: int, payload: WorkflowVersionCreate) -> dict:
        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT id FROM workflows WHERE id = %s", (workflow_id,))
            if cursor.fetchone() is None:
                raise ValueError("workflow_not_found")
            definition = payload.definition_json
            if payload.base_version_id is not None:
                cursor.execute(
                    "SELECT workflow_id, definition_json FROM workflow_versions WHERE id = %s",
                    (payload.base_version_id,),
                )
                base = cursor.fetchone()
                if base is None or int(base["workflow_id"]) != workflow_id:
                    raise ValueError("base_version_not_found")
                if definition is None:
                    definition = base["definition_json"]
                    if isinstance(definition, str):
                        definition = json.loads(definition)
            definition = definition or _blank_definition()
            compile_definition(definition)
            cursor.execute(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM workflow_versions WHERE workflow_id = %s FOR UPDATE",
                (workflow_id,),
            )
            version_number = int(cursor.fetchone()["next_version"])
            cursor.execute(
                """INSERT INTO workflow_versions
                   (workflow_id, version_number, is_published, definition_json, lock_version)
                   VALUES (%s, %s, 0, %s, 0)""",
                (workflow_id, version_number, json.dumps(definition)),
            )
            version_id = int(cursor.lastrowid)
            cursor.execute(f"SELECT {SELECT_COLUMNS} FROM workflow_versions WHERE id = %s", (version_id,))
            return _decode(cursor.fetchone())

    @staticmethod
    def list(workflow_id: int) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {SELECT_COLUMNS} FROM workflow_versions WHERE workflow_id = %s ORDER BY version_number DESC",
                (workflow_id,),
            )
            return [_decode(row) for row in cursor.fetchall()]

    @staticmethod
    def get(version_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(f"SELECT {SELECT_COLUMNS} FROM workflow_versions WHERE id = %s", (version_id,))
            return _decode(cursor.fetchone())

    @staticmethod
    def update(version_id: int, payload: WorkflowVersionUpdate) -> dict | None:
        compile_definition(payload.definition_json)
        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT is_published, lock_version FROM workflow_versions WHERE id = %s FOR UPDATE", (version_id,))
            current = cursor.fetchone()
            if current is None:
                return None
            lock = int(current["lock_version"])
            if bool(current["is_published"]):
                raise VersionConflictError("version_published", lock)
            if lock != payload.expected_lock_version:
                raise VersionConflictError("version_conflict", lock)
            cursor.execute(
                "UPDATE workflow_versions SET definition_json = %s, lock_version = lock_version + 1 WHERE id = %s",
                (json.dumps(payload.definition_json), version_id),
            )
            cursor.execute(f"SELECT {SELECT_COLUMNS} FROM workflow_versions WHERE id = %s", (version_id,))
            return _decode(cursor.fetchone())

    @staticmethod
    def set_published(version_id: int, expected_lock_version: int, published: bool) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT is_published, lock_version, definition_json FROM workflow_versions WHERE id = %s FOR UPDATE",
                (version_id,),
            )
            current = cursor.fetchone()
            if current is None:
                return None
            lock = int(current["lock_version"])
            if lock != expected_lock_version:
                raise VersionConflictError("version_conflict", lock)
            definition = current["definition_json"]
            if isinstance(definition, str):
                definition = json.loads(definition)
            if published:
                compile_definition(definition)
            cursor.execute(
                "UPDATE workflow_versions SET is_published = %s, lock_version = lock_version + 1 WHERE id = %s",
                (1 if published else 0, version_id),
            )
            cursor.execute(f"SELECT {SELECT_COLUMNS} FROM workflow_versions WHERE id = %s", (version_id,))
            return _decode(cursor.fetchone())
