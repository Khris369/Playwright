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
editor_dist_dir = web_dir / "editor-dist"

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router)
app.mount("/ui/static", StaticFiles(directory=str(static_dir)), name="ui-static")
if editor_dist_dir.exists():
    app.mount(
        "/ui/editor/assets",
        StaticFiles(directory=str(editor_dist_dir / "assets")),
        name="editor-assets",
    )


@app.get("/")
def root() -> dict[str, str]:
    return {"message": f"{settings.app_name} API"}


@app.get("/ui")
def ui() -> FileResponse:
    return FileResponse(str(web_dir / "index.html"))


@app.get("/ui/editor")
def ui_editor() -> FileResponse:
    return FileResponse(str(editor_dist_dir / "index.html"))
