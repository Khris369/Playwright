from __future__ import annotations

from app.services.db import get_db_cursor


class PermissionRepository:
    @staticmethod
    def is_workflow_owner(user_id: int, workflow_id: int) -> bool:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "SELECT 1 FROM workflows WHERE id = %s AND owner_user_id = %s",
                (workflow_id, user_id),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def list_workflow_members(workflow_id: int) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT wm.user_id, u.username, u.display_name, wm.access_level
                FROM workflow_members wm
                JOIN users u ON u.id = wm.user_id
                WHERE wm.workflow_id = %s
                ORDER BY u.display_name, u.username
                """,
                (workflow_id,),
            )
            return list(cursor.fetchall())

    @staticmethod
    def set_workflow_members(workflow_id: int, members: list[dict]) -> list[dict]:
        allowed = {"viewer", "editor", "runner"}
        normalized: dict[int, str] = {}
        for member in members:
            access_level = str(member["access_level"]).strip().lower()
            if access_level not in allowed:
                raise ValueError("invalid_access_level")
            normalized[int(member["user_id"])] = access_level
        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT id FROM workflows WHERE id = %s", (workflow_id,))
            if cursor.fetchone() is None:
                raise ValueError("workflow_not_found")
            if normalized:
                placeholders = ",".join(["%s"] * len(normalized))
                cursor.execute(
                    f"SELECT id FROM users WHERE id IN ({placeholders}) AND status = 'active'",
                    tuple(normalized),
                )
                valid_users = {int(row["id"]) for row in cursor.fetchall()}
                if valid_users != set(normalized):
                    raise ValueError("user_not_found")
            cursor.execute("DELETE FROM workflow_members WHERE workflow_id = %s", (workflow_id,))
            if normalized:
                cursor.executemany(
                    "INSERT INTO workflow_members (workflow_id, user_id, access_level) VALUES (%s, %s, %s)",
                    [(workflow_id, user_id, access) for user_id, access in normalized.items()],
                )
        return PermissionRepository.list_workflow_members(workflow_id)

    @staticmethod
    def is_admin(user_id: int) -> bool:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT 1 FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE ur.user_id = %s AND r.name = 'admin'
                LIMIT 1
                """,
                (user_id,),
            )
            return cursor.fetchone() is not None

    @staticmethod
    def can_access_workflow(user_id: int, workflow_id: int, permission: str) -> bool:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT w.owner_user_id, wm.access_level
                FROM workflows w
                LEFT JOIN workflow_members wm
                  ON wm.workflow_id = w.id AND wm.user_id = %s
                WHERE w.id = %s
                """,
                (user_id, workflow_id),
            )
            row = cursor.fetchone()
        if row is None:
            return False
        if int(row.get("owner_user_id") or 0) == user_id:
            return True
        access = str(row.get("access_level") or "").lower()
        if permission == "workflow.view":
            return access in {"viewer", "editor", "runner", "admin"}
        if permission == "workflow.edit":
            return access in {"editor", "admin"}
        if permission == "workflow.run":
            return access in {"runner", "editor", "admin"}
        return False

    @staticmethod
    def resource_workflow_id(resource_type: str, resource_id: int) -> int | None:
        queries = {
            "workflow": "SELECT id AS workflow_id FROM workflows WHERE id = %s",
            "version": "SELECT workflow_id FROM workflow_versions WHERE id = %s",
            "run": "SELECT workflow_id FROM workflow_runs WHERE id = %s",
            "preset": "SELECT workflow_id FROM run_arg_presets WHERE id = %s AND isActive = 1",
        }
        query = queries[resource_type]
        with get_db_cursor() as (_, cursor):
            cursor.execute(query, (resource_id,))
            row = cursor.fetchone()
        return int(row["workflow_id"]) if row and row.get("workflow_id") is not None else None

    @staticmethod
    def list_roles() -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT r.id, r.name, r.description, p.permission_key
                FROM roles r
                LEFT JOIN role_permissions rp ON rp.role_id = r.id
                LEFT JOIN permissions p ON p.id = rp.permission_id
                ORDER BY r.name, p.permission_key
                """
            )
            grouped: dict[int, dict] = {}
            for row in cursor.fetchall():
                role = grouped.setdefault(
                    int(row["id"]),
                    {"id": int(row["id"]), "name": row["name"], "description": row["description"], "permissions": []},
                )
                if row.get("permission_key"):
                    role["permissions"].append(row["permission_key"])
            return list(grouped.values())

    @staticmethod
    def set_user_roles(user_id: int, role_names: list[str]) -> tuple[list[str], list[str]]:
        requested = sorted({name.strip().lower() for name in role_names})
        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
            if cursor.fetchone() is None:
                raise ValueError("user_not_found")

            cursor.execute("SELECT id, name FROM roles")
            roles = {str(row["name"]): int(row["id"]) for row in cursor.fetchall()}
            unknown = sorted(set(requested) - set(roles))
            if unknown:
                raise ValueError("unknown_role")
            if not requested:
                raise ValueError("at_least_one_role_required")

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                WHERE r.name = 'admin' AND ur.user_id <> %s
                """,
                (user_id,),
            )
            other_admins = int(cursor.fetchone()["count"])
            if "admin" not in requested and other_admins == 0:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM user_roles ur JOIN roles r ON r.id = ur.role_id
                    WHERE ur.user_id = %s AND r.name = 'admin'
                    """,
                    (user_id,),
                )
                if int(cursor.fetchone()["count"]) > 0:
                    raise ValueError("last_admin_cannot_be_demoted")

            cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
            cursor.executemany(
                "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
                [(user_id, roles[name]) for name in requested],
            )
        return PermissionRepository.get_roles_and_permissions(user_id)

    @staticmethod
    def get_roles_and_permissions(user_id: int) -> tuple[list[str], list[str]]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT r.name, p.permission_key
                FROM user_roles ur
                JOIN roles r ON r.id = ur.role_id
                LEFT JOIN role_permissions rp ON rp.role_id = r.id
                LEFT JOIN permissions p ON p.id = rp.permission_id
                WHERE ur.user_id = %s
                ORDER BY r.name, p.permission_key
                """,
                (user_id,),
            )
            rows = cursor.fetchall()
        roles = sorted({str(row["name"]) for row in rows})
        permissions = sorted({str(row["permission_key"]) for row in rows if row.get("permission_key")})
        return roles, permissions
