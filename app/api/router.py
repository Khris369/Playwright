from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.templates import router as templates_router
from app.api.routes.workflow_runs import router as workflow_runs_router
from app.api.routes.workflows import router as workflows_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(workflows_router)
api_router.include_router(workflow_runs_router)
api_router.include_router(templates_router)
