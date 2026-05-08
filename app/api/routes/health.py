from __future__ import annotations

from fastapi import APIRouter

from app.database import db_settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    settings = db_settings()
    return {
        "status": "ok",
        "database": {
            "driver": settings["driver"],
            "host": settings["host"],
            "port": settings["port"],
            "database": settings["database"],
        },
    }
