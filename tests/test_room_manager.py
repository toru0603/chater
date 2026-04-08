import asyncio
import pytest

from app.room_manager import RoomManager, RoomFullError, MAX_PARTICIPANTS


class DummyWebSocket:
    """Lightweight stand-in for FastAPI WebSocket in RoomManager tests."""
    pass


def test_add_get_remove_peer():
    manager = RoomManager()
    ws1 = DummyWebSocket()
    ws2 = DummyWebSocket()

    # Add first participant
    p1, peer1 = asyncio.run(manager.add_participant("room1", "Alice", ws1))
    assert peer1 is None
    assert p1.role == "host"
    assert p1.name == "Alice"
    assert p1.room_code == "room1"

    # Add second participant and verify matching
    p2, peer2 = asyncio.run(manager.add_participant("room1", "Bob", ws2))
    assert peer2 is not None
    assert peer2.id == p1.id
    assert p2.role == "guest"

    # get_peer should return the other participant
    peer_of_p1 = asyncio.run(manager.get_peer(p1.id))
    assert peer_of_p1 is not None and peer_of_p1.id == p2.id

    # Remove first participant
    peer_after_remove, empty = asyncio.run(manager.remove_participant(p1.id))
    assert peer_after_remove is not None and peer_after_remove.id == p2.id
    assert empty is False

    # Remove second participant (room should become empty)
    peer_after_remove2, empty2 = asyncio.run(manager.remove_participant(p2.id))
    assert peer_after_remove2 is None
    assert empty2 is True

    # Removing nonexistent participant returns (None, False)
    none_peer, none_empty = asyncio.run(manager.remove_participant("nonexistent"))
    assert none_peer is None
    assert none_empty is False


def test_room_full_error():
    manager = RoomManager()
    # create dummy websockets equal to MAX_PARTICIPANTS + 1
    ws_list = [DummyWebSocket() for _ in range(MAX_PARTICIPANTS + 1)]

    # fill the room to capacity
    for i in range(MAX_PARTICIPANTS):
        asyncio.run(manager.add_participant("room2", f"P{i}", ws_list[i]))

    # adding one more should raise RoomFullError
    with pytest.raises(RoomFullError):
        asyncio.run(manager.add_participant("room2", "overflow", ws_list[MAX_PARTICIPANTS]))


def test_get_peer_none_when_not_found():
    manager = RoomManager()
    assert asyncio.run(manager.get_peer("nope")) is None
