from __future__ import annotations

from app.schemas.workflow import WorkflowCreate, WorkflowVersionCreate, WorkflowVersionUpdate
from app.services.db import get_db_cursor


def _workflow_columns() -> set[str]:
    return get_table_columns("workflows")


def _can_join_users_for_workflows() -> bool:
    workflow_columns = _workflow_columns()
    user_columns = get_table_columns("users")
    return "updated_by_user_id" in workflow_columns and "display_name" in user_columns


def _workflow_select_sql() -> str:
    columns = _workflow_columns()
    select_parts = ["w.id"]

    for optional_column in ("owner_user_id", "created_by_user_id", "updated_by_user_id"):
        if optional_column in columns:
            select_parts.append(f"w.{optional_column}")
        else:
            select_parts.append(f"NULL AS {optional_column}")

    if _can_join_users_for_workflows():
        select_parts.append("u.display_name AS updated_by_display_name")
    else:
        select_parts.append("NULL AS updated_by_display_name")

    select_parts.extend(
        [
            "w.name",
            "w.description",
            "w.status",
            "w.created_at",
            "w.updated_at",
        ]
    )

    query = f"SELECT {', '.join(select_parts)} FROM workflows w"
    if _can_join_users_for_workflows():
        query += " LEFT JOIN users u ON u.id = w.updated_by_user_id"
    return query


class WorkflowRepository:
    @staticmethod
    def create_workflow(payload: WorkflowCreate, user_id: int | None = None) -> dict:
        workflow_columns = _workflow_columns()
        insert_columns: list[str] = ["name", "description", "status"]
        insert_values: list[object] = [payload.name, payload.description, payload.status]

        for optional_column in ("owner_user_id", "created_by_user_id", "updated_by_user_id"):
            if optional_column in workflow_columns:
                insert_columns.insert(len(insert_columns) - 3, optional_column)
                insert_values.insert(len(insert_values) - 3, user_id)

        placeholders = ", ".join(["%s"] * len(insert_columns))
        column_sql = ", ".join(insert_columns)

        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"INSERT INTO workflows ({column_sql}) VALUES ({placeholders})",
                tuple(insert_values),
            )
            workflow_id = int(cursor.lastrowid)

            cursor.execute(f"{_workflow_select_sql()} WHERE w.id = %s", (workflow_id,))
            row = cursor.fetchone()
            if row is None:
                raise ValueError("workflow_not_found")
            return row

    @staticmethod
    def list_workflows(active_only: bool = False) -> list[dict]:
        query = _workflow_select_sql()
        params: list[object] = []
        if active_only:
            query += " WHERE w.status = %s"
            params.append("active")
        query += " ORDER BY w.updated_at DESC, w.created_at DESC"

        with get_db_cursor() as (_, cursor):
            cursor.execute(query, tuple(params))
            return list(cursor.fetchall())

    @staticmethod
    def get_workflow(workflow_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(f"{_workflow_select_sql()} WHERE w.id = %s", (workflow_id,))
            return cursor.fetchone()

    @staticmethod
    def create_workflow_version(
        workflow_id: int, payload: WorkflowVersionCreate, user_id: int | None = None
    ) -> dict:
        from app.services.workflow_version_repository import WorkflowVersionRepository

        return WorkflowVersionRepository.create(workflow_id, payload, user_id)

    @staticmethod
    def list_workflow_versions(workflow_id: int) -> list[dict]:
        from app.services.workflow_version_repository import WorkflowVersionRepository

        return WorkflowVersionRepository.list(workflow_id)

    @staticmethod
    def get_workflow_version(version_id: int) -> dict | None:
        from app.services.workflow_version_repository import WorkflowVersionRepository

        return WorkflowVersionRepository.get(version_id)

    @staticmethod
    def update_workflow_version(
        version_id: int, payload: WorkflowVersionUpdate, user_id: int | None = None
    ) -> dict | None:
        from app.services.workflow_version_repository import WorkflowVersionRepository

        return WorkflowVersionRepository.update(version_id, payload, user_id)

    @staticmethod
    def deactivate_workflow(workflow_id: int) -> bool:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "UPDATE workflows SET status = %s WHERE id = %s AND status = %s",
                ("inactive", workflow_id, "active"),
            )
            return cursor.rowcount > 0
