"""Authorizes and tracks short-lived local editor previews."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.engine.graph import GraphValidationError, compile_definition
from app.engine.preview import LOCAL_PREVIEW_CAPABILITIES, possible_steps_to_target
from app.services.workflow_run_repository import WorkflowRunRepository
from app.services.workflow_version_repository import WorkflowVersionRepository

TERMINAL_PREVIEW_STATUSES = {"passed", "failed", "cancelled", "agent_disconnected"}


def _bounded(value: Any, limit: int = 1000) -> str:
    return str(value).replace("\n", " ").replace("\r", " ")[:limit]


@dataclass
class PreviewSession:
    id: str
    run_id: int
    user_id: int
    client_id: str
    target_node_id: str
    connection: object
    plan: list[dict[str, Any]]
    inputs: dict[str, Any]
    expires_at: datetime
    current_node_id: str | None = None
    current_node_type: str | None = None
    current_url: str | None = None
    event_ids: set[str] = field(default_factory=set)
    inspection_state: str = "running"
    pick_request: dict[str, str] | None = None


class LocalPreviewService:
    def __init__(self) -> None:
        self.sessions: dict[str, PreviewSession] = {}
        self.by_run: dict[int, str] = {}

    def create(self, *, user_id: int, client_id: str, workflow_version_id: int, definition: dict, inputs: dict, target_node_id: str, connection: object, confirm_side_effects: bool) -> PreviewSession:
        version = WorkflowVersionRepository.get(workflow_version_id)
        if version is None:
            raise ValueError("workflow_version_not_found")
        try:
            compiled = compile_definition(definition)
            possible = possible_steps_to_target(compiled, target_node_id)
        except GraphValidationError as exc:
            raise ValueError("invalid_workflow_definition") from exc
        unsupported = [step["type"] for step in possible if not str(step["type"]).startswith("__") and LOCAL_PREVIEW_CAPABILITIES.get(str(step["type"]), None) is None]
        if unsupported:
            raise ValueError("unsupported_nodes:" + ",".join(sorted(set(unsupported))))
        if any(LOCAL_PREVIEW_CAPABILITIES.get(str(step["type"]), None) and LOCAL_PREVIEW_CAPABILITIES[str(step["type"])].side_effect for step in possible) and not confirm_side_effects:
            raise ValueError("side_effect_confirmation_required")
        canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        definition_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        run_id = WorkflowRunRepository.create_local_preview_run(int(version["workflow_id"]), workflow_version_id, user_id, definition, inputs, target_node_id, definition_hash)
        session = PreviewSession(secrets.token_urlsafe(24), run_id, user_id, client_id, target_node_id, connection, possible, inputs, datetime.now(UTC) + timedelta(minutes=25))
        self.sessions[session.id] = session
        self.by_run[run_id] = session.id
        return session

    def begin_pick(self, run_id: int, user_id: int, client_id: str, node_id: str, field_path: str) -> tuple[PreviewSession, str]:
        session = self.get_owned(run_id, user_id)
        if session is None or session.client_id != client_id or session.inspection_state != "inspection_ready" or session.pick_request:
            raise ValueError("preview_inspection_unavailable")
        request_id = secrets.token_urlsafe(18)
        session.pick_request = {"id": request_id, "node_id": node_id, "field_path": field_path}
        session.inspection_state = "picking"
        return session, request_id

    def cancel_pick(self, run_id: int, user_id: int, request_id: str) -> PreviewSession | None:
        session = self.get_owned(run_id, user_id)
        if session is None or not session.pick_request or session.pick_request["id"] != request_id:
            return None
        return session

    def inspection_event(self, session_id: str, run_id: int, event_type: str, payload: dict[str, Any], message_id: str) -> PreviewSession | None:
        session = self.sessions.get(session_id)
        if session is None or session.run_id != run_id or message_id in session.event_ids:
            return None
        # Inspection messages are valid only while the retained-browser
        # lifecycle is active.  In particular, an old ready/result event must
        # never revive a preview that the backend has expired or closed.
        if event_type == "preview.inspection.closed":
            if session.inspection_state not in {"running", "inspection_ready", "picking", "closing"}:
                return None
        elif session.inspection_state in {"closed", "closing"} or datetime.now(UTC) > session.expires_at:
            return None
        if event_type == "preview.inspection.ready":
            run = WorkflowRunRepository.get_run(run_id)
            if session.inspection_state != "running" or run is None or run.get("status") != "passed":
                return None
        elif event_type == "preview.inspection.pick.started":
            if session.inspection_state != "picking" or not session.pick_request or session.pick_request["id"] != payload.get("pick_request_id"):
                return None
        elif event_type in {"preview.inspection.pick.result", "preview.inspection.pick.cancelled", "preview.inspection.unavailable"}:
            if session.inspection_state != "picking" or not session.pick_request or session.pick_request["id"] != payload.get("pick_request_id"):
                return None
        session.event_ids.add(message_id)
        if event_type == "preview.inspection.ready":
            session.inspection_state = "inspection_ready"
            session.expires_at = datetime.now(UTC) + timedelta(minutes=20)
        elif event_type == "preview.inspection.pick.started":
            session.inspection_state = "picking"
        elif event_type in {"preview.inspection.pick.result", "preview.inspection.pick.cancelled", "preview.inspection.unavailable"}:
            session.inspection_state, session.pick_request = "inspection_ready", None
        elif event_type == "preview.inspection.closed":
            session.inspection_state, session.pick_request = "closed", None
            self.sessions.pop(session.id, None)
            self.by_run.pop(run_id, None)
        return session

    def expire(self) -> list[PreviewSession]:
        now = datetime.now(UTC)
        expired = [session for session in self.sessions.values() if session.inspection_state in {"inspection_ready", "picking"} and session.expires_at <= now]
        for session in expired:
            session.inspection_state, session.pick_request = "closing", None
        return expired

    def get_owned(self, run_id: int, user_id: int) -> PreviewSession | None:
        session_id = self.by_run.get(run_id)
        session = self.sessions.get(session_id or "")
        return session if session and session.user_id == user_id else None

    def event(self, session_id: str, run_id: int, event_type: str, payload: dict[str, Any], message_id: str) -> PreviewSession | None:
        session = self.sessions.get(session_id)
        if session is None or session.run_id != run_id or message_id in session.event_ids or datetime.now(UTC) > session.expires_at:
            return None
        session.event_ids.add(message_id)
        run = WorkflowRunRepository.get_run(run_id)
        if run is None or run.get("status") in TERMINAL_PREVIEW_STATUSES:
            return None
        if event_type == "preview.accepted":
            WorkflowRunRepository.try_mark_run_running(run_id)
        elif event_type == "preview.step.started":
            session.current_node_id = _bounded(payload.get("node_id"), 120)
            session.current_node_type = _bounded(payload.get("node_type"), 80)
            session.current_url = _bounded(payload.get("url"), 2048) or session.current_url
        elif event_type in {"preview.step.completed", "preview.step.failed"}:
            index = payload.get("step_index")
            if not isinstance(index, int) or not 0 <= index < 10_000:
                return None
            status = "passed" if event_type.endswith("completed") else "failed"
            WorkflowRunRepository.create_step_run(run_id, index, session.current_node_id, session.current_node_type or "unknown", status, {}, _bounded(payload.get("log"), 2000) if status == "passed" else None, _bounded(payload.get("error"), 2000) if status == "failed" else None)
            session.current_url = _bounded(payload.get("url"), 2048) or session.current_url
        elif event_type == "preview.passed":
            WorkflowRunRepository.finalize_preview(run_id, "passed")
        elif event_type == "preview.target_not_reached":
            WorkflowRunRepository.finalize_preview(run_id, "failed", "target_not_reached", "Selected target was not visited by the runtime path")
        elif event_type == "preview.cancelled":
            WorkflowRunRepository.finalize_preview(run_id, "cancelled", "user_cancelled", "Preview cancelled")
        elif event_type in {"preview.rejected", "preview.failed"}:
            WorkflowRunRepository.finalize_preview(run_id, "failed", _bounded(payload.get("code") or "step_failed", 50), _bounded(payload.get("message") or "Preview failed", 1000))
        return session

    def disconnect(self, user_id: int, connection: object) -> list[PreviewSession]:
        affected = [s for s in self.sessions.values() if s.user_id == user_id and s.connection is connection]
        for session in affected:
            WorkflowRunRepository.finalize_preview(session.run_id, "agent_disconnected", "agent_disconnected", "Local preview agent disconnected")
        return affected

    def close(self, run_id: int, user_id: int) -> PreviewSession | None:
        session = self.get_owned(run_id, user_id)
        if session is not None:
            self.sessions.pop(session.id, None)
            self.by_run.pop(run_id, None)
        return session


local_previews = LocalPreviewService()
