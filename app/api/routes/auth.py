from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.auth import current_user
from app.schemas.user import LoginRequest, UserCreate, UserPasswordChange, UserResponse
from app.services.passwords import verify_password
from app.services.session_repository import SESSION_COOKIE_NAME, SessionRepository
from app.services.user_repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, expires_at) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        expires=expires_at,
        httponly=True,
        samesite="strict",
        secure=False,
        path="/",
    )


@router.get("/me", response_model=UserResponse)
def me(user: dict = Depends(current_user)) -> UserResponse:
    return UserResponse(**user)


@router.post("/login", response_model=UserResponse)
def login(payload: LoginRequest, response: Response) -> UserResponse:
    user = UserRepository.get_by_username(payload.username, include_password_hash=True)
    if user is None or not verify_password(payload.password, user.get("password_hash")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    token, expires_at = SessionRepository.create(int(user["id"]))
    UserRepository.record_login(int(user["id"]))
    _set_session_cookie(response, token, expires_at)
    user.pop("password_hash", None)
    return UserResponse(**user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token:
        SessionRepository.revoke(token)
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: UserPasswordChange,
    user: dict = Depends(current_user),
) -> None:
    if not UserRepository.change_password(
        int(user["id"]), payload.current_password, payload.new_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )


@router.post("/bootstrap-admin", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def bootstrap_admin(payload: UserCreate, response: Response) -> UserResponse:
    if UserRepository.count_users() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bootstrap is only available before the first user is created",
        )
    admin_payload = UserCreate(
        username=payload.username,
        email=payload.email,
        display_name=payload.display_name,
        password=payload.password,
        role="admin",
        status="active",
    )
    user = UserRepository.create(admin_payload)
    token, expires_at = SessionRepository.create(int(user["id"]))
    _set_session_cookie(response, token, expires_at)
    return UserResponse(**user)
