from app.engine.preview import LOCAL_PREVIEW_CAPABILITIES, possible_steps_to_target
from app.services.local_preview_service import LocalPreviewService, PreviewSession
from picker_agent.protocol import parse_command
from picker_agent.selection import SelectionCoordinator
import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch


def test_preview_plan_keeps_alternate_branch_for_target_not_reached() -> None:
    steps = [
        {"id": "start", "type": "__if__", "branches": {"true": "target", "false": "other"}, "args": {}},
        {"id": "target", "type": "wait_timeout", "next": None, "args": {}},
        {"id": "other", "type": "wait_timeout", "next": None, "args": {}},
    ]
    assert {step["id"] for step in possible_steps_to_target(steps, "target")} == {"start", "target", "other"}


def test_preview_plan_excludes_nodes_after_successful_target() -> None:
    steps = [
        {"id": "before", "type": "wait_timeout", "next": "target", "args": {}},
        {"id": "target", "type": "wait_timeout", "next": "unsupported", "args": {}},
        {"id": "unsupported", "type": "ticket_submit", "next": None, "args": {}},
    ]
    assert [step["id"] for step in possible_steps_to_target(steps, "target")] == ["before", "target"]


def test_preview_protocol_accepts_start_and_stop_commands() -> None:
    assert parse_command({"version": 1, "type": "preview.start", "session_id": "preview", "payload": {}}).type == "preview.start"
    assert parse_command({"version": 1, "type": "preview.stop", "session_id": "preview", "payload": {}}).type == "preview.stop"


def test_only_ticket_submission_remains_explicitly_unsupported() -> None:
    assert "ticket_create_new_ticket" in LOCAL_PREVIEW_CAPABILITIES
    assert "ticket_fill_fields" in LOCAL_PREVIEW_CAPABILITIES
    assert "ticket_submit" not in LOCAL_PREVIEW_CAPABILITIES


def test_selection_coordinator_blocks_other_picker_mode_until_release() -> None:
    async def exercise() -> None:
        coordinator = SelectionCoordinator()
        assert await coordinator.acquire("picker:normal") is True
        assert await coordinator.acquire("preview:retained") is False
        coordinator.release("picker:normal")
        assert await coordinator.acquire("preview:retained") is True
    asyncio.run(exercise())


def test_inspection_events_cannot_revive_expired_or_closing_preview() -> None:
    service = LocalPreviewService()
    session = PreviewSession("preview", 42, 7, "editor", "target", object(), [], {}, datetime.now(UTC) - timedelta(seconds=1), inspection_state="closing")
    service.sessions[session.id] = session
    service.by_run[session.run_id] = session.id

    assert service.inspection_event(session.id, session.run_id, "preview.inspection.ready", {}, "late-ready") is None
    assert session.inspection_state == "closing"


def test_inspection_ready_requires_a_passed_preview_run() -> None:
    service = LocalPreviewService()
    session = PreviewSession("preview", 42, 7, "editor", "target", object(), [], {}, datetime.now(UTC) + timedelta(minutes=1))
    service.sessions[session.id] = session
    service.by_run[session.run_id] = session.id

    with patch("app.services.local_preview_service.WorkflowRunRepository.get_run", return_value={"status": "running"}):
        assert service.inspection_event(session.id, session.run_id, "preview.inspection.ready", {}, "premature-ready") is None
    assert session.inspection_state == "running"
