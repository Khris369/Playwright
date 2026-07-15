from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.settings import get_settings
from app.services.session_repository import SESSION_COOKIE_NAME, SessionRepository

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


def _page_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    return SessionRepository.get_user_for_token(token) if token else None


@app.get("/ui", response_model=None)
def ui(request: Request) -> FileResponse | RedirectResponse:
    if _page_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    return FileResponse(str(web_dir / "index.html"))


@app.get("/login", response_model=None)
def login_page() -> FileResponse:
    return FileResponse(str(web_dir / "login.html"))


@app.get("/ui/users", response_model=None)
def users_page(request: Request) -> FileResponse | RedirectResponse:
    user = _page_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    if user.get("role") != "admin":
        return RedirectResponse("/ui", status_code=303)
    return FileResponse(str(web_dir / "users.html"))


@app.get("/ui/editor", response_model=None)
def ui_editor(request: Request) -> FileResponse | RedirectResponse:
    if _page_user(request) is None:
        return RedirectResponse("/login", status_code=303)
    return FileResponse(str(editor_dist_dir / "index.html"))
