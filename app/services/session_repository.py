from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.services.db import get_db_cursor


SESSION_COOKIE_NAME = "workflow_session"
SESSION_TTL_DAYS = 7


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionRepository:
    @staticmethod
    def create(user_id: int) -> tuple[str, datetime]:
        token = secrets.token_urlsafe(32)
        token_hash = hash_session_token(token)
        expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                INSERT INTO user_sessions (user_id, token_hash, expires_at)
                VALUES (%s, %s, %s)
                """,
                (user_id, token_hash, expires_at.replace(tzinfo=None)),
            )
        return token, expires_at

    @staticmethod
    def get_user_for_token(token: str) -> dict | None:
        token_hash = hash_session_token(token)
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT u.id, u.email, u.display_name, u.role, u.status,
                       u.last_login_at, u.created_at, u.updated_at
                FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = %s
                  AND s.revoked_at IS NULL
                  AND s.expires_at > NOW()
                  AND u.status = 'active'
                """,
                (token_hash,),
            )
            user = cursor.fetchone()
            if user is not None:
                cursor.execute(
                    "UPDATE user_sessions SET last_seen_at = NOW() WHERE token_hash = %s",
                    (token_hash,),
                )
            return user

    @staticmethod
    def revoke(token: str) -> None:
        token_hash = hash_session_token(token)
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = NOW()
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_hash,),
            )
