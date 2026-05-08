from __future__ import annotations

from fastapi import FastAPI

from app.api.router import api_router
from app.core.settings import get_settings

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router)


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API"}
