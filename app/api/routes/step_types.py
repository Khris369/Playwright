from __future__ import annotations

from fastapi import APIRouter, Query

from app.schemas.step_type import StepTypeResponse
from app.services.step_type_repository import StepTypeRepository

router = APIRouter(prefix="/step-types", tags=["step-types"])


@router.get("", response_model=list[StepTypeResponse])
def list_step_types(active_only: bool = Query(default=True)) -> list[StepTypeResponse]:
    rows = StepTypeRepository.list_step_types(active_only=active_only)
    return [StepTypeResponse(**row) for row in rows]
