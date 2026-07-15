from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.schemas.template import (
    WorkflowTemplateCreate,
    WorkflowTemplateImportRequest,
    WorkflowTemplateImportResponse,
    WorkflowTemplateResponse,
)
from app.services.template_repository import TemplateRepository

router = APIRouter(prefix="/workflow-templates", tags=["workflow-templates"])


@router.post(
    "/seed-defaults",
    response_model=list[WorkflowTemplateResponse],
    status_code=status.HTTP_200_OK,
)
def seed_default_templates() -> list[WorkflowTemplateResponse]:
    TemplateRepository.ensure_default_template()
    rows = TemplateRepository.list_templates()
    return [WorkflowTemplateResponse(**row) for row in rows]


@router.post(
    "", response_model=WorkflowTemplateResponse, status_code=status.HTTP_201_CREATED
)
def create_template(payload: WorkflowTemplateCreate) -> WorkflowTemplateResponse:
    row = TemplateRepository.create_template(payload)
    return WorkflowTemplateResponse(**row)


@router.get("", response_model=list[WorkflowTemplateResponse])
def list_templates() -> list[WorkflowTemplateResponse]:
    rows = TemplateRepository.list_templates()
    return [WorkflowTemplateResponse(**row) for row in rows]


@router.post(
    "/{template_id}/import",
    response_model=WorkflowTemplateImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_template(
    template_id: int, payload: WorkflowTemplateImportRequest
) -> WorkflowTemplateImportResponse:
    try:
        result = TemplateRepository.import_template_to_workflow(
            template_id=template_id,
            workflow_name=payload.workflow_name,
            workflow_description=payload.workflow_description,
            workflow_status=payload.workflow_status,
            version_number=payload.version_number,
            is_published=payload.is_published,
        )
    except ValueError as exc:
        if str(exc) == "template_not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Template not found"
            ) from exc
        raise
    return WorkflowTemplateImportResponse(**result)
