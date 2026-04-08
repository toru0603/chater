import asyncio

import pytest

from app.room_manager import RoomFullError, RoomManager


class DummyWebSocket:
    """Lightweight stand-in for FastAPI WebSocket in RoomManager tests."""

    pass


def test_add_get_remove_peer():
    manager = RoomManager()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()

    # Add first participant
    p1, existing1 = asyncio.run(manager.add_participant("room1", "Alice", ws1))
    assert existing1 == []
    assert p1.role == "host"
    assert p1.name == "Alice"
    assert p1.room_code == "room1"

    # Add second participant and verify matching
    p2, existing2 = asyncio.run(manager.add_participant("room1", "Bob", ws2))
    assert existing2 is not None
    assert len(existing2) == 1 and existing2[0].id == p1.id
    assert p2.role == "guest"

    # get_room_participants should return both participants
    participants = asyncio.run(manager.get_room_participants("room1"))
    assert len(participants) == 2
    peer_of_p1 = next((p for p in participants if p.id != p1.id), None)
    assert peer_of_p1 is not None and peer_of_p1.id == p2.id

    # Remove first participant
    removed, remaining, empty = asyncio.run(manager.remove_participant(p1.id))
    assert removed is not None and removed.id == p1.id
    assert len(remaining) == 1 and remaining[0].id == p2.id
    assert empty is False

    # Remove second participant (room should become empty)
    removed2, remaining2, empty2 = asyncio.run(manager.remove_participant(p2.id))
    assert removed2 is not None and removed2.id == p2.id
    assert remaining2 == []

    assert empty2 is True

    # Removing nonexistent participant returns (None, [], False)
    none_removed, none_remaining, none_empty = asyncio.run(
        manager.remove_participant("nonexistent")
    )
    assert none_removed is None
    assert none_remaining == []
    assert none_empty is False


def test_room_full_error():
    manager = RoomManager()
    ws_extra = DummyWebSocket()

    # Fill the room up to the configured MAX_PARTICIPANTS and ensure overflow raises
    from app.room_manager import MAX_PARTICIPANTS

    for i in range(MAX_PARTICIPANTS):
        asyncio.run(manager.add_participant("room2", str(i), DummyWebSocket()))

    with pytest.raises(RoomFullError):
        asyncio.run(manager.add_participant("room2", "overflow", ws_extra))


def test_get_participant_none_when_not_found():
    manager = RoomManager()
    assert asyncio.run(manager.get_participant("nope")) is None
