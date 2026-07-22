import asyncio

from app.services.picker_connection_manager import PickerConnectionManager


class Socket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


class Relay:
    def __init__(self):
        self.published = []

    async def publish(self, kind, parts, message):
        self.published.append((kind, parts, message))


def test_local_socket_is_preferred_over_relay():
    manager = PickerConnectionManager()
    socket = Socket()
    manager.agents[7] = socket  # type: ignore[assignment]
    relay = Relay()
    manager.relay = relay  # type: ignore[assignment]

    assert asyncio.run(manager.send_agent(7, {"type": "command"})) is True
    assert socket.messages == [{"type": "command"}]
    assert relay.published == []


def test_missing_local_socket_is_published_for_another_process():
    manager = PickerConnectionManager()
    relay = Relay()
    manager.relay = relay  # type: ignore[assignment]

    assert asyncio.run(manager.send_editor(7, "client", {"type": "event"})) is True
    assert relay.published == [("editor", (7, "client"), {"type": "event"})]


def test_relay_message_targets_only_matching_local_socket():
    manager = PickerConnectionManager()
    socket = Socket()
    manager.editors[(7, "client")] = socket  # type: ignore[assignment]

    asyncio.run(manager._deliver_relay_message("editor", ["7", "client"], {"type": "event"}))
    asyncio.run(manager._deliver_relay_message("editor", ["8", "client"], {"type": "other"}))

    assert socket.messages == [{"type": "event"}]
