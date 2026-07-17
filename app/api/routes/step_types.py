from __future__ import annotations

from fastapi import APIRouter, Depends

from app.schemas.step_type import StepTypeResponse
from app.engine.registry import public_step_types
from app.core.auth import current_user

router = APIRouter(prefix="/step-types", tags=["step-types"])


@router.get("", response_model=list[StepTypeResponse])
def list_step_types(user: dict = Depends(current_user)) -> list[StepTypeResponse]:
    rows = public_step_types()
    return [StepTypeResponse(**row) for row in rows]
