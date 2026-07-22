from datetime import timedelta

import pytest

from app.services.picker_session_service import PickerSessionService


def test_picker_sessions_expire_after_twenty_minutes() -> None:
    assert PickerSessionService().session_ttl == timedelta(minutes=20)


def test_picker_session_state_transitions_and_owner_isolation() -> None:
    service = PickerSessionService()
    session = service.create(7, 12, "node-a", "client-a", None)
    assert session.state == "waiting_for_agent"
    assert service.get_owned(session.id, 8) is None
    service.transition(session, "agent_connected")
    service.transition(session, "browser_starting")
    service.transition(session, "browser_ready")
    service.transition(session, "inspection_active")
    service.transition(session, "element_selected")
    service.transition(session, "browser_ready")
    service.transition(session, "inspection_active")
    service.transition(session, "element_selected")
    service.transition(session, "completed")
    with pytest.raises(ValueError):
        service.transition(session, "browser_ready")


def test_agent_claim_is_one_time_and_expiring() -> None:
    service = PickerSessionService(agent_token_ttl=timedelta(seconds=-1))
    claim = service.issue_agent_token(7)
    assert service.consume_agent_token(claim.token) is None
    live = PickerSessionService().issue_agent_token(7)
    service = PickerSessionService()
    service.agent_claims[live.token] = live
    assert service.consume_agent_token(live.token).user_id == 7
    assert service.consume_agent_token(live.token) is None


def test_expiry_moves_active_sessions_to_expired() -> None:
    service = PickerSessionService(session_ttl=timedelta(seconds=-1))
    session = service.create(1, 2, "node", "client", None)
    assert session.state == "waiting_for_agent"
    # Creation calls expiry before adding the session; explicit expiry handles it.
    assert service.expire() == [session]
    assert session.state == "expired"


def test_pairing_code_approves_once_and_issues_scoped_device_claim() -> None:
    service = PickerSessionService()
    pairing = service.create_pairing("AB12-CD34")
    approved = service.approve_pairing(pairing.code, 9)
    assert approved is not None
    _, claim = approved
    assert claim.user_id == 9
    assert service.consume_device_token(claim.token).user_id == 9
    assert service.approve_pairing(pairing.code, 10) is None
