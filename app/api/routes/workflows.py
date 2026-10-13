from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import ValidationError

from app.core.auth import current_user, require_permission, require_workflow_access, require_workflow_owner
from app.schemas.workflow_member import WorkflowMemberResponse, WorkflowMembersUpdate
from app.services.permission_repository import PermissionRepository
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowResponse,
    WorkflowVersionCreate,
    WorkflowVersionResponse,
    WorkflowVersionUpdate,
    WorkflowVersionLockRequest,
)
from app.engine.graph import GraphValidationError
from app.services.workflow_repository import WorkflowRepository
from app.services.workflow_version_repository import WorkflowVersionRepository, VersionConflictError
from app.schemas.workflow_portable import PortableWorkflow
from app.services.workflow_portable import export_workflow, import_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])
MAX_IMPORT_BYTES = 10 * 1024 * 1024


@router.get("/{workflow_id}/export", response_model=PortableWorkflow)
def download_workflow(workflow_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> PortableWorkflow:
    try:
        exported = export_workflow(workflow_id)
    except ValueError as exc:
        messages = {
            "no_versions": "Workflow has no versions to export",
            "too_many_versions": "Workflow has more than 100 versions",
            "export_too_large": "Workflow export exceeds 10 MiB",
        }
        if str(exc) not in messages:
            raise
        raise HTTPException(status_code=422, detail=messages[str(exc)]) from exc
    if exported is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return exported


@router.post("/import", status_code=status.HTTP_201_CREATED)
async def upload_workflow(request: Request, user: dict = Depends(require_permission("workflow.edit"))) -> dict[str, int]:
    chunks = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_IMPORT_BYTES:
            raise HTTPException(status_code=413, detail="Workflow file exceeds 10 MiB")
        chunks.append(chunk)
    try:
        payload = PortableWorkflow.model_validate_json(b"".join(chunks))
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Invalid workflow export file") from exc
    try:
        workflow_id = import_workflow(payload, int(user["id"]))
    except GraphValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_definition", "errors": [i.as_dict() for i in exc.issues]}) from exc
    return {"id": workflow_id}


@router.get("/{workflow_id}/members", response_model=list[WorkflowMemberResponse])
def list_workflow_members(
    workflow_id: int, user: dict = Depends(require_workflow_owner())
) -> list[WorkflowMemberResponse]:
    return [WorkflowMemberResponse(**row) for row in PermissionRepository.list_workflow_members(workflow_id)]


@router.get("/access", response_model=list[dict])
def list_workflow_access(user: dict = Depends(current_user)) -> list[dict]:
    return PermissionRepository.list_workflow_access(int(user["id"]), "admin" in user.get("roles", []))


@router.put("/{workflow_id}/members", response_model=list[WorkflowMemberResponse])
def update_workflow_members(
    workflow_id: int,
    payload: WorkflowMembersUpdate,
    user: dict = Depends(require_workflow_owner()),
) -> list[WorkflowMemberResponse]:
    try:
        rows = PermissionRepository.set_workflow_members(
            workflow_id, [member.model_dump() for member in payload.members]
        )
    except ValueError as exc:
        errors = {
            "workflow_not_found": (404, "Workflow not found"),
            "user_not_found": (422, "One or more users were not found or are inactive"),
            "invalid_permissions": (422, "Permissions must be workflow.view, workflow.edit, or workflow.run"),
        }
        status_code, detail = errors.get(str(exc), (422, "Invalid workflow members"))
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return [WorkflowMemberResponse(**row) for row in rows]


@router.post("", response_model=WorkflowResponse, status_code=status.HTTP_201_CREATED)
def create_workflow(
    payload: WorkflowCreate,
    user: dict = Depends(require_permission("workflow.edit")),
) -> WorkflowResponse:
    row = WorkflowRepository.create_workflow(payload, int(user["id"]) if user else None)
    return WorkflowResponse(**row)


@router.get("", response_model=list[WorkflowResponse])
def list_workflows(active_only: bool = Query(default=False), user: dict = Depends(current_user)) -> list[WorkflowResponse]:
    rows = WorkflowRepository.list_workflows(
        active_only=active_only,
        user_id=int(user["id"]),
        is_admin="admin" in user.get("roles", []),
    )
    return [WorkflowResponse(**row) for row in rows]


@router.get("/{workflow_id}", response_model=WorkflowResponse)
def get_workflow(workflow_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> WorkflowResponse:
    row = WorkflowRepository.get_workflow(workflow_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return WorkflowResponse(**row)


@router.post(
    "/{workflow_id}/versions",
    response_model=WorkflowVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_workflow_version(
    workflow_id: int,
    payload: WorkflowVersionCreate,
    user: dict = Depends(require_workflow_access("workflow.edit")),
) -> WorkflowVersionResponse:
    try:
        row = WorkflowVersionRepository.create(workflow_id, payload, int(user["id"]) if user else None)
    except ValueError as exc:
        if str(exc) == "workflow_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
            ) from exc
        if str(exc) == "base_version_not_found":
            raise HTTPException(status_code=404, detail="Base version not found") from exc
        raise
    except GraphValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_definition", "errors": [i.as_dict() for i in exc.issues]}) from exc
    return WorkflowVersionResponse(**row)


@router.get("/{workflow_id}/versions", response_model=list[WorkflowVersionResponse])
def list_workflow_versions(workflow_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> list[WorkflowVersionResponse]:
    rows = WorkflowVersionRepository.list(workflow_id)
    return [WorkflowVersionResponse(**row) for row in rows]


@router.get("/versions/{version_id}", response_model=WorkflowVersionResponse)
def get_workflow_version(version_id: int, user: dict = Depends(require_workflow_access("workflow.view"))) -> WorkflowVersionResponse:
    row = WorkflowVersionRepository.get(version_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow version not found"
        )
    return WorkflowVersionResponse(**row)


@router.put("/versions/{version_id}", response_model=WorkflowVersionResponse)
def update_workflow_version(
    version_id: int,
    payload: WorkflowVersionUpdate,
    user: dict = Depends(require_workflow_access("workflow.edit")),
) -> WorkflowVersionResponse:
    try:
        row = WorkflowVersionRepository.update(version_id, payload, int(user["id"]) if user else None)
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "current_lock_version": exc.current_lock_version}) from exc
    except GraphValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_definition", "errors": [i.as_dict() for i in exc.issues]}) from exc
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow version not found"
        )
    return WorkflowVersionResponse(**row)


def _set_published(
    version_id: int,
    payload: WorkflowVersionLockRequest,
    published: bool,
    user: dict,
) -> WorkflowVersionResponse:
    try:
        row = WorkflowVersionRepository.set_published(
            version_id,
            payload.expected_lock_version,
            published,
            int(user["id"]) if user else None,
        )
    except VersionConflictError as exc:
        raise HTTPException(status_code=409, detail={"code": exc.code, "current_lock_version": exc.current_lock_version}) from exc
    except GraphValidationError as exc:
        raise HTTPException(status_code=422, detail={"code": "invalid_definition", "errors": [i.as_dict() for i in exc.issues]}) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="Workflow version not found")
    return WorkflowVersionResponse(**row)


@router.post("/versions/{version_id}/publish", response_model=WorkflowVersionResponse)
def publish_workflow_version(
    version_id: int,
    payload: WorkflowVersionLockRequest,
    user: dict = Depends(require_workflow_access("workflow.edit")),
) -> WorkflowVersionResponse:
    return _set_published(version_id, payload, True, user)


@router.post("/versions/{version_id}/unpublish", response_model=WorkflowVersionResponse)
def unpublish_workflow_version(
    version_id: int,
    payload: WorkflowVersionLockRequest,
    user: dict = Depends(require_workflow_access("workflow.edit")),
) -> WorkflowVersionResponse:
    return _set_published(version_id, payload, False, user)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_workflow(workflow_id: int, user: dict = Depends(require_workflow_access("workflow.delete"))) -> None:
    updated = WorkflowRepository.deactivate_workflow(workflow_id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Active workflow not found"
        )
