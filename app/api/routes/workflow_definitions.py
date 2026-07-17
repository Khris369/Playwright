from fastapi import APIRouter, Depends

from app.engine.graph import validate_definition
from app.schemas.workflow_definition import WorkflowDefinitionValidate, WorkflowDefinitionValidationResponse
from app.core.auth import require_permission

router = APIRouter(prefix="/workflow-definitions", tags=["workflow-definitions"])


@router.post("/validate", response_model=WorkflowDefinitionValidationResponse)
def validate_workflow_definition(payload: WorkflowDefinitionValidate, user: dict = Depends(require_permission("workflow.view"))) -> dict:
    return validate_definition(payload.definition_json)
