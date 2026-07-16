from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from app.engine.graph import compile_definition
from app.schemas.workflow import WorkflowVersionCreate, WorkflowVersionUpdate
from app.services.db import get_db_cursor

# Repository for editable and published workflow definitions. Definitions are
# compiled before persistence, and lock_version protects concurrent editor saves.

@dataclass
class VersionConflictError(RuntimeError):
    code: str
    current_lock_version: int


def _decode(row: dict | None) -> dict | None:
    """Normalize JSON and numeric database fields for API consumers."""
    if row is None:
        return None
    if isinstance(row.get("definition_json"), str):
        row["definition_json"] = json.loads(row["definition_json"])
    row["is_published"] = bool(row["is_published"])
    row["lock_version"] = int(row.get("lock_version", 0))
    return row


def _blank_definition() -> dict[str, Any]:
    """Create the minimal valid graph used when no definition is supplied."""
    return {
        "schema_version": 2,
        "graph": {
            "nodes": [{"id": str(uuid.uuid4()), "kind": "start", "position": {"x": 80, "y": 160}}],
            "edges": [],
            "viewport": {"x": 0, "y": 0, "zoom": 1},
        },
    }


def _select_columns_sql() -> str:
    return ", ".join(
        [
            "id",
            "workflow_id",
            "version_number",
            "is_published",
            "definition_json",
            "created_by_user_id",
            "updated_by_user_id",
            "lock_version",
            "created_at",
            "updated_at",
        ]
    )


def _touch_workflow(cursor, workflow_id: int, user_id: int | None) -> None:
    """Update parent workflow audit metadata in the same transaction."""
    cursor.execute(
        """
        UPDATE workflows
        SET updated_by_user_id = %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (user_id, workflow_id),
    )


class WorkflowVersionRepository:
    @staticmethod
    def create(workflow_id: int, payload: WorkflowVersionCreate, user_id: int | None = None) -> dict:
        """Validate and insert a new version, optionally cloning a base version."""
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

            cursor.execute(
                """
                INSERT INTO workflow_versions (
                    workflow_id,
                    created_by_user_id,
                    updated_by_user_id,
                    version_number,
                    is_published,
                    definition_json,
                    lock_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (workflow_id, user_id, user_id, next_version, 0, json.dumps(definition), 0),
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
        """Return versions newest first for the workflow editor/history view."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions "
                "WHERE workflow_id = %s ORDER BY version_number DESC",
                (workflow_id,),
            )
            return [_decode(row) for row in cursor.fetchall()]

    @staticmethod
    def get(version_id: int) -> dict | None:
        """Fetch one version and normalize its stored definition."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions WHERE id = %s",
                (version_id,),
            )
            return _decode(cursor.fetchone())

    @staticmethod
    def update(version_id: int, payload: WorkflowVersionUpdate, user_id: int | None = None) -> dict | None:
        """Update an unpublished version only when its lock version still matches."""
        compile_definition(payload.definition_json)

        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT workflow_id, is_published, lock_version FROM workflow_versions WHERE id = %s FOR UPDATE",
                (version_id,),
            )
            current = cursor.fetchone()
            if current is None:
                return None

            lock_version = int(current["lock_version"])
            if bool(current["is_published"]):
                raise VersionConflictError("version_published", lock_version)
            if lock_version != payload.expected_lock_version:
                raise VersionConflictError("version_conflict", lock_version)

            cursor.execute(
                """
                UPDATE workflow_versions
                SET definition_json = %s,
                    updated_by_user_id = %s,
                    lock_version = lock_version + 1
                WHERE id = %s
                """,
                (json.dumps(payload.definition_json), user_id, version_id),
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
        """Publish or unpublish a version using optimistic concurrency checks."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT workflow_id, definition_json, lock_version FROM workflow_versions WHERE id = %s FOR UPDATE",
                (version_id,),
            )
            current = cursor.fetchone()
            if current is None:
                return None

            lock_version = int(current["lock_version"])
            if lock_version != expected_lock_version:
                raise VersionConflictError("version_conflict", lock_version)

            definition = current["definition_json"]
            if isinstance(definition, str):
                definition = json.loads(definition)
            if published:
                compile_definition(definition)

            cursor.execute(
                """
                UPDATE workflow_versions
                SET is_published = %s,
                    updated_by_user_id = %s,
                    lock_version = lock_version + 1
                WHERE id = %s
                """,
                (1 if published else 0, user_id, version_id),
            )

            _touch_workflow(cursor, int(current["workflow_id"]), user_id)
            cursor.execute(
                f"SELECT {_select_columns_sql()} FROM workflow_versions WHERE id = %s",
                (version_id,),
            )
            return _decode(cursor.fetchone())
