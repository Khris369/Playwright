from __future__ import annotations

from app.schemas.user import UserCreate, UserUpdate
from app.services.db import get_db_cursor
from app.services.passwords import hash_password


SELECT_COLUMNS = """
    id, username, email, display_name, role, status, last_login_at, created_at, updated_at
"""


class UserRepository:
    @staticmethod
    def count_users() -> int:
        with get_db_cursor() as (_, cursor):
            cursor.execute("SELECT COUNT(*) AS count FROM users")
            return int(cursor.fetchone()["count"])

    @staticmethod
    def create(payload: UserCreate) -> dict:
        password_hash = hash_password(payload.password)
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO users (username, email, display_name, password_hash, role, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    payload.username.strip().lower(),
                    payload.email.strip().lower() if payload.email else None,
                    payload.display_name,
                    password_hash,
                    payload.role,
                    payload.status,
                ),
            )
            user_id = int(cursor.lastrowid)
        return UserRepository.get(user_id) or {}

    @staticmethod
    def get(user_id: int) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {SELECT_COLUMNS} FROM users WHERE id = %s",
                (user_id,),
            )
            return cursor.fetchone()

    @staticmethod
    def get_by_username(username: str, include_password_hash: bool = False) -> dict | None:
        columns = SELECT_COLUMNS
        if include_password_hash:
            columns = f"{SELECT_COLUMNS}, password_hash"
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"SELECT {columns} FROM users WHERE username = %s",
                (username.strip().lower(),),
            )
            return cursor.fetchone()

    @staticmethod
    def list_users(limit: int = 100) -> list[dict]:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                f"""
                SELECT {SELECT_COLUMNS}
                FROM users
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return list(cursor.fetchall())

    @staticmethod
    def update(user_id: int, payload: UserUpdate) -> dict | None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE users
                SET username = %s, email = %s, display_name = %s, role = %s, status = %s
                WHERE id = %s
                """,
                (
                    payload.username.strip().lower(),
                    payload.email.strip().lower() if payload.email else None,
                    payload.display_name,
                    payload.role,
                    payload.status,
                    user_id,
                ),
            )
        return UserRepository.get(user_id)

    @staticmethod
    def reset_password(user_id: int, password: str) -> dict | None:
        password_hash = hash_password(password)
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (password_hash, user_id),
            )
        return UserRepository.get(user_id)

    @staticmethod
    def record_login(user_id: int) -> None:
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                "UPDATE users SET last_login_at = NOW() WHERE id = %s",
                (user_id,),
            )
