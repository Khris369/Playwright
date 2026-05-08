from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.settings import get_settings

settings = get_settings()
web_dir = Path(__file__).resolve().parent / "web"
static_dir = web_dir / "static"

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router)
app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="ui-static")


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API"}


@app.get("/ui")
def ui() -> FileResponse:
    return FileResponse(str(web_dir / "index.html"))


@app.get("/ui/editor")
def ui_editor() -> FileResponse:
    return FileResponse(str(web_dir / "editor.html"))
