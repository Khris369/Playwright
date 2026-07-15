from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import current_admin_user
from app.schemas.user import UserCreate, UserPasswordReset, UserResponse, UserUpdate
from app.services.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserResponse])
def list_users(
    limit: int = Query(default=100, ge=1, le=500),
    _: dict = Depends(current_admin_user),
) -> list[UserResponse]:
    return [UserResponse(**row) for row in UserRepository.list_users(limit=limit)]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: dict = Depends(current_admin_user),
) -> UserResponse:
    try:
        return UserResponse(**UserRepository.create(payload))
    except ValueError as exc:
        if str(exc) in {"password_too_short", "password_too_long"}:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise


@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    _: dict = Depends(current_admin_user),
) -> UserResponse:
    row = UserRepository.update(user_id, payload)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**row)


@router.post("/{user_id}/reset-password", response_model=UserResponse)
def reset_user_password(
    user_id: int,
    payload: UserPasswordReset,
    _: dict = Depends(current_admin_user),
) -> UserResponse:
    try:
        row = UserRepository.reset_password(user_id, payload.password)
    except ValueError as exc:
        if str(exc) in {"password_too_short", "password_too_long"}:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        raise
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(**row)
