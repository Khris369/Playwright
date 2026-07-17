from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import current_admin_user, require_permission
from app.schemas.user import (
    RoleAssignmentRequest,
    RoleAssignmentResponse,
    UserCreate,
    UserPasswordReset,
    UserResponse,
    UserUpdate,
)
from app.services.permission_repository import PermissionRepository
from app.services.user_repository import UserRepository

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/directory", response_model=list[dict])
def user_directory(user: dict = Depends(require_permission("workflow.edit"))) -> list[dict]:
    return UserRepository.list_directory()


@router.get("/roles", response_model=list[dict])
def list_roles(_: dict = Depends(current_admin_user)) -> list[dict]:
    return PermissionRepository.list_roles()


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


@router.get("/{user_id}/roles", response_model=RoleAssignmentResponse)
def get_user_roles(
    user_id: int, _: dict = Depends(current_admin_user)
) -> RoleAssignmentResponse:
    row = UserRepository.get(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User not found")
    roles, permissions = PermissionRepository.get_roles_and_permissions(user_id)
    return RoleAssignmentResponse(user_id=user_id, roles=roles, permissions=permissions)


@router.put("/{user_id}/roles", response_model=RoleAssignmentResponse)
def set_user_roles(
    user_id: int,
    payload: RoleAssignmentRequest,
    _: dict = Depends(current_admin_user),
) -> RoleAssignmentResponse:
    try:
        roles, permissions = PermissionRepository.set_user_roles(user_id, payload.roles)
    except ValueError as exc:
        errors = {
            "user_not_found": (404, "User not found"),
            "unknown_role": (422, "Unknown role"),
            "at_least_one_role_required": (422, "At least one role is required"),
            "last_admin_cannot_be_demoted": (409, "The last administrator cannot be demoted"),
        }
        status_code, detail = errors.get(str(exc), (422, "Invalid role assignment"))
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return RoleAssignmentResponse(user_id=user_id, roles=roles, permissions=permissions)
