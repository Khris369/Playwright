from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.services.session_repository import SESSION_COOKIE_NAME, SessionRepository
from app.services.permission_repository import PermissionRepository


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
    roles, permissions = PermissionRepository.get_roles_and_permissions(int(user["id"]))
    user["roles"] = roles
    user["permissions"] = permissions
    return user


def require_permission(permission: str):
    def dependency(request: Request) -> dict:
        user = current_user(request)
        if "admin" in user.get("roles", []) or permission in user.get("permissions", []):
            return user
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")

    return dependency


def require_workflow_access(permission: str):
    def dependency(request: Request) -> dict:
        user = current_user(request)
        if "admin" in user.get("roles", []):
            return user

        if permission in user.get("permissions", []):
            return user

        params = request.path_params
        resource = None
        resource_id = None
        for key, resource_type in (("workflow_id", "workflow"), ("version_id", "version"), ("run_id", "run"), ("preset_id", "preset")):
            if key in params:
                resource = resource_type
                resource_id = int(params[key])
                break
        if resource is None or resource_id is None:
            return user
        workflow_id = PermissionRepository.resource_workflow_id(resource, resource_id)
        if workflow_id is None or not PermissionRepository.can_access_workflow(int(user["id"]), workflow_id, permission):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
        return user

    return dependency


def require_workflow_owner():
    def dependency(request: Request) -> dict:
        user = require_permission("workflow.edit")(request)
        if "admin" in user.get("roles", []):
            return user
        workflow_id = int(request.path_params["workflow_id"])
        if not PermissionRepository.is_workflow_owner(int(user["id"]), workflow_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
        return user

    return dependency


def current_admin_user(request: Request) -> dict:
    user = current_user(request)
    if "admin" not in user.get("roles", []):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
