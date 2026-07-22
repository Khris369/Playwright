import asyncio

import pytest
from fastapi import HTTPException

from app.api.routes import editor_picker
from app.schemas.editor_picker import PickerSessionCreate
from app.services.picker_connection_manager import picker_connections
from app.services.picker_session_service import picker_sessions


def _reset_picker_state() -> None:
    picker_sessions.sessions.clear()
    picker_sessions.agent_claims.clear()
    picker_sessions.pairings.clear()
    picker_sessions.device_tokens.clear()
    picker_connections.agents.clear()
    picker_connections.editors.clear()
    picker_connections.agent_info.clear()


def test_picker_session_rejects_unauthorized_workflow(monkeypatch) -> None:
    _reset_picker_state()
    monkeypatch.setattr(editor_picker, "_can_edit", lambda *args: False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(editor_picker.create_session(PickerSessionCreate(workflow_id=1, node_id="n", client_id="x" * 16), {"id": 5, "roles": [], "permissions": []}))
    assert exc.value.status_code == 404


def test_picker_session_is_bound_to_authorized_editor(monkeypatch) -> None:
    _reset_picker_state()
    monkeypatch.setattr(editor_picker, "_can_edit", lambda *args: True)
    response = asyncio.run(editor_picker.create_session(PickerSessionCreate(workflow_id=1, node_id="n", client_id="x" * 16, requested_url="https://example.test"), {"id": 5, "roles": ["admin"], "permissions": []}))
    session = picker_sessions.get_owned(response.session_id, 5)
    assert session is not None
    assert picker_sessions.get_owned(response.session_id, 6) is None


def test_protocol_result_validation_rejects_unsupported_locator() -> None:
    assert not editor_picker._valid_result({"locator": {"strategy": "test_id"}, "validation": {"match_count": 1, "matches_selected_element": True}})
    assert editor_picker._valid_result({"locator": {"strategy": "css", "selector": "#save"}, "validation": {"match_count": 1, "matches_selected_element": True}})


def test_inspection_cancel_keeps_browser_ready_session(monkeypatch) -> None:
    _reset_picker_state()
    monkeypatch.setattr(editor_picker, "_can_edit", lambda *args: True)
    session = picker_sessions.create(5, 1, "node", "x" * 16, None)
    session.state = "browser_ready"
    response = asyncio.run(editor_picker.cancel_inspection(session.id, {"id": 5, "roles": ["admin"], "permissions": []}))
    assert response.status == "browser_ready"
    assert picker_sessions.get_owned(session.id, 5).state == "browser_ready"


def test_accepting_locator_keeps_browser_session_ready(monkeypatch) -> None:
    _reset_picker_state()
    monkeypatch.setattr(editor_picker, "_can_edit", lambda *args: True)
    session = picker_sessions.create(5, 1, "node", "x" * 16, None)
    session.state = "element_selected"
    session.result = {"locator": {"strategy": "css", "selector": "#save"}}

    response = asyncio.run(editor_picker.complete_session(session.id, {"id": 5, "roles": ["admin"], "permissions": []}))

    assert response.status == "browser_ready"
    assert picker_sessions.get_owned(session.id, 5).result is None


def test_discarding_selected_locator_keeps_browser_session_ready(monkeypatch) -> None:
    _reset_picker_state()
    monkeypatch.setattr(editor_picker, "_can_edit", lambda *args: True)
    session = picker_sessions.create(5, 1, "node", "x" * 16, None)
    session.state = "element_selected"

    response = asyncio.run(editor_picker.cancel_inspection(session.id, {"id": 5, "roles": ["admin"], "permissions": []}))

    assert response.status == "browser_ready"


def test_unpair_revokes_device_claims(monkeypatch) -> None:
    _reset_picker_state()
    picker_sessions.approve_pairing(picker_sessions.create_pairing("AB12-CD34").code, 5)
    response = asyncio.run(editor_picker.unpair_device({"id": 5, "roles": ["admin"], "permissions": []}))
    assert response["unpaired"] is True
    assert picker_sessions.device_tokens == {}
