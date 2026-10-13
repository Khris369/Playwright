from __future__ import annotations

import json

from app.engine.graph import compile_definition
from app.schemas.workflow_portable import PortableWorkflow
from app.services.db import get_db_cursor


def export_workflow(workflow_id: int) -> PortableWorkflow | None:
    with get_db_cursor() as (_, cursor):
        cursor.execute("SELECT name, description FROM workflows WHERE id = %s", (workflow_id,))
        workflow = cursor.fetchone()
        if workflow is None:
            return None
        cursor.execute(
            "SELECT definition_json FROM workflow_versions WHERE workflow_id = %s ORDER BY version_number",
            (workflow_id,),
        )
        versions = [
            {"definition_json": json.loads(row["definition_json"])
             if isinstance(row["definition_json"], str) else row["definition_json"]}
            for row in cursor.fetchall()
        ]
    if not versions:
        raise ValueError("no_versions")
    if len(versions) > 100:
        raise ValueError("too_many_versions")
    exported = PortableWorkflow(
        format="workflow-builder", format_version=1,
        name=workflow["name"], description=workflow["description"], versions=versions,
    )
    if len(exported.model_dump_json().encode("utf-8")) > 10 * 1024 * 1024:
        raise ValueError("export_too_large")
    return exported


def import_workflow(payload: PortableWorkflow, user_id: int) -> int:
    # Validate the complete file before creating any database rows.
    for version in payload.versions:
        compile_definition(version.definition_json)

    with get_db_cursor() as (_, cursor):
        cursor.execute(
            """INSERT INTO workflows (owner_user_id, created_by_user_id, updated_by_user_id,
               name, description, status) VALUES (%s, %s, %s, %s, %s, 'active')""",
            (user_id, user_id, user_id, payload.name, payload.description),
        )
        workflow_id = int(cursor.lastrowid)
        for number, version in enumerate(payload.versions, 1):
            cursor.execute(
                """INSERT INTO workflow_versions (workflow_id, created_by_user_id,
                   updated_by_user_id, version_number, is_published, definition_json, lock_version)
                   VALUES (%s, %s, %s, %s, 0, %s, 0)""",
                (workflow_id, user_id, user_id, number, json.dumps(version.definition_json)),
            )
        return workflow_id
