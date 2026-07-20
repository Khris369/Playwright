from __future__ import annotations

from pathlib import Path
import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.core.settings import get_settings
from app.services.session_repository import SESSION_COOKIE_NAME, SessionRepository
from app.services.permission_repository import PermissionRepository
from app.services.picker_connection_manager import picker_connections
from app.services.picker_session_service import picker_sessions

settings = get_settings()
web_dir = Path(__file__).resolve().parent / "web"
static_dir = web_dir / "static"
editor_dist_dir = web_dir / "editor-dist"

app = FastAPI(title=settings.app_name, debug=settings.debug)
app.include_router(api_router)
_picker_expiry_task: asyncio.Task | None = None


async def _expire_picker_sessions() -> None:
    while True:
        await asyncio.sleep(5)
        for session in picker_sessions.expire():
            await picker_connections.send_agent(session.user_id, {"version": 1, "type": "session.close", "session_id": session.id, "payload": {}})
            await picker_connections.send_editor(session.user_id, session.client_id, {"version": 1, "type": "picker.session.updated", "session_id": session.id, "payload": {"status": "expired", "expires_at": session.expires_at.isoformat()}})


@app.on_event("startup")
async def start_picker_expiry_task() -> None:
    global _picker_expiry_task
    await picker_connections.start_relay(settings.picker_redis_url)
    _picker_expiry_task = asyncio.create_task(_expire_picker_sessions())


@app.on_event("shutdown")
async def stop_picker_expiry_task() -> None:
    if _picker_expiry_task:
        _picker_expiry_task.cancel()
    await picker_connections.stop_relay()
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
    return FileResponse(str(web_dir / "users.html"))


@app.get("/ui/editor", response_model=None)
def ui_editor(request: Request) -> FileResponse | RedirectResponse:
    user = _page_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    roles, permissions = PermissionRepository.get_roles_and_permissions(int(user["id"]))
    if "admin" not in roles and "workflow.edit" not in permissions:
        return RedirectResponse("/ui", status_code=303)
    return FileResponse(str(editor_dist_dir / "index.html"))
