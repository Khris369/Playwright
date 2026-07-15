from fastapi import APIRouter

from app.engine.graph import validate_definition
from app.schemas.workflow_definition import WorkflowDefinitionValidate, WorkflowDefinitionValidationResponse

router = APIRouter(prefix="/workflow-definitions", tags=["workflow-definitions"])


@router.post("/validate", response_model=WorkflowDefinitionValidationResponse)
def validate_workflow_definition(payload: WorkflowDefinitionValidate) -> dict:
    return validate_definition(payload.definition_json)
