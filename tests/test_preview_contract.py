from app.engine.preview import LOCAL_PREVIEW_CAPABILITIES, possible_steps_to_target
from picker_agent.protocol import parse_command


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
