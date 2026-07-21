from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


TERMINAL_STATES = {"completed", "cancelled", "expired", "failed"}
TRANSITIONS = {
    "created": {"waiting_for_agent", "cancelled", "expired", "failed"},
    "waiting_for_agent": {"agent_connected", "cancelled", "expired", "failed"},
    "agent_connected": {"browser_starting", "cancelled", "expired", "failed"},
    "browser_starting": {"browser_ready", "cancelled", "expired", "failed"},
    "browser_ready": {"inspection_active", "cancelled", "expired", "failed"},
    "inspection_active": {"browser_ready", "element_selected", "cancelled", "expired", "failed"},
    "element_selected": {"browser_ready", "completed", "cancelled", "expired", "failed"},
}


@dataclass
class PickerSession:
    id: str
    user_id: int
    workflow_id: int
    node_id: str
    client_id: str
    requested_url: str | None
    expires_at: datetime
    state: str = "created"
    result: dict | None = None


@dataclass
class AgentClaim:
    token: str
    user_id: int
    expires_at: datetime


@dataclass
class PairingRequest:
    code: str
    expires_at: datetime
    user_id: int | None = None
    device_token: str | None = None


@dataclass
class PickerSessionService:
    # A picker session owns a local browser context. Keep it long enough to
    # collect several locators without requiring the user to authenticate again.
    session_ttl: timedelta = timedelta(minutes=20)
    agent_token_ttl: timedelta = timedelta(minutes=15)
    sessions: dict[str, PickerSession] = field(default_factory=dict)
    agent_claims: dict[str, AgentClaim] = field(default_factory=dict)
    pairings: dict[str, PairingRequest] = field(default_factory=dict)
    device_tokens: dict[str, AgentClaim] = field(default_factory=dict)

    def now(self) -> datetime:
        return datetime.now(UTC)

    def issue_agent_token(self, user_id: int) -> AgentClaim:
        self.expire()
        claim = AgentClaim(secrets.token_urlsafe(32), user_id, self.now() + self.agent_token_ttl)
        self.agent_claims[claim.token] = claim
        return claim

    def consume_agent_token(self, token: str) -> AgentClaim | None:
        self.expire()
        return self.agent_claims.pop(token, None)

    def create_pairing(self, code: str) -> PairingRequest:
        self.expire()
        pairing = PairingRequest(code, self.now() + timedelta(minutes=5))
        self.pairings[code] = pairing
        return pairing

    def approve_pairing(self, code: str, user_id: int) -> tuple[PairingRequest, AgentClaim] | None:
        self.expire()
        pairing = self.pairings.get(code)
        if pairing is None or pairing.user_id is not None:
            return None
        pairing.user_id = user_id
        claim = AgentClaim(secrets.token_urlsafe(32), user_id, self.now() + timedelta(days=30))
        pairing.device_token = claim.token
        self.device_tokens[claim.token] = claim
        return pairing, claim

    def consume_device_token(self, token: str) -> AgentClaim | None:
        self.expire()
        claim = self.device_tokens.get(token)
        return claim

    def revoke_device_tokens(self, user_id: int) -> int:
        revoked = 0
        for token, claim in list(self.device_tokens.items()):
            if claim.user_id == user_id:
                del self.device_tokens[token]
                revoked += 1
        return revoked

    def create(self, user_id: int, workflow_id: int, node_id: str, client_id: str, requested_url: str | None) -> PickerSession:
        self.expire()
        session = PickerSession(secrets.token_urlsafe(24), user_id, workflow_id, node_id, client_id, requested_url, self.now() + self.session_ttl)
        self.sessions[session.id] = session
        self.transition(session, "waiting_for_agent")
        return session

    def get_owned(self, session_id: str, user_id: int) -> PickerSession | None:
        self.expire()
        session = self.sessions.get(session_id)
        return session if session and session.user_id == user_id else None

    def transition(self, session: PickerSession, state: str) -> None:
        if state not in TRANSITIONS.get(session.state, set()):
            raise ValueError(f"invalid picker state transition: {session.state} -> {state}")
        session.state = state

    def expire(self) -> list[PickerSession]:
        now = self.now()
        expired: list[PickerSession] = []
        for session in self.sessions.values():
            if session.state not in TERMINAL_STATES and session.expires_at <= now:
                session.state = "expired"
                expired.append(session)
        for token, claim in list(self.agent_claims.items()):
            if claim.expires_at <= now:
                del self.agent_claims[token]
        for token, claim in list(self.device_tokens.items()):
            if claim.expires_at <= now:
                del self.device_tokens[token]
        for code, pairing in list(self.pairings.items()):
            if pairing.expires_at <= now:
                del self.pairings[code]
        return expired


picker_sessions = PickerSessionService()
