from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.session_repository import SESSION_COOKIE_NAME, SessionRepository


def optional_current_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return SessionRepository.get_user_for_token(token)


def current_user(request: Request) -> dict:
    user = optional_current_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication required"
                if not request.cookies.get(SESSION_COOKIE_NAME)
                else "Invalid or expired session"
            ),
        )
    return user


def current_admin_user(request: Request) -> dict:
    user = current_user(request)
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
