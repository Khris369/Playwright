from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.services.db import get_db_cursor


SESSION_COOKIE_NAME = "workflow_session"
SESSION_TTL_DAYS = 7

# Only a SHA-256 digest is stored in the database; the raw random token is
# returned once to the caller and is used as the browser session cookie.

def hash_session_token(token: str) -> str:
    """Hash a session token for lookup without persisting the bearer secret."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SessionRepository:
    @staticmethod
    def revoke_all_for_user(user_id: int) -> None:
        """Revoke all active sessions after a password change."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                UPDATE user_sessions
                SET revoked_at = NOW()
                WHERE user_id = %s AND revoked_at IS NULL
                """,
                (user_id,),
            )

    @staticmethod
    def cleanup_expired() -> None:
        """Remove expired and revoked sessions."""
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                DELETE FROM user_sessions
                WHERE expires_at <= NOW() OR revoked_at IS NOT NULL
                """
            )

    @staticmethod
    def create(user_id: int) -> tuple[str, datetime]:
        """Create a seven-day cryptographically random session for a user."""
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
        """Resolve an active token and update its last-seen timestamp.

        Revoked, expired, or inactive-user sessions are rejected by the same
        query, keeping authentication state checks at the persistence boundary.
        """
        token_hash = hash_session_token(token)
        with get_db_cursor() as (_, cursor):
            cursor.execute(
                """
                SELECT u.id, u.username, u.email, u.display_name, u.status,
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
        """Revoke a token without deleting its audit record."""
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
