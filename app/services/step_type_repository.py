from __future__ import annotations

from app.services.db import get_db_cursor


class StepTypeRepository:
    @staticmethod
    def list_step_types(active_only: bool = True) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            if active_only:
                cursor.execute(
                    """
                    SELECT id, `key`, name, description, is_active, sort_order, created_at, updated_at
                    FROM step_types
                    WHERE is_active = 1
                    ORDER BY sort_order ASC, id ASC
                    """
                )
            else:
                cursor.execute(
                    """
                    SELECT id, `key`, name, description, is_active, sort_order, created_at, updated_at
                    FROM step_types
                    ORDER BY sort_order ASC, id ASC
                    """
                )
            rows = list(cursor.fetchall())
            for row in rows:
                row["is_active"] = bool(row.get("is_active"))
            return rows
