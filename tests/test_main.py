import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.room_manager import RoomManager


@pytest.fixture(autouse=True)
def reset_room_manager():
    # Reset module-level RoomManager to isolate tests
    main_module.room_manager = RoomManager()
    yield


def test_index():
    client = TestClient(main_module.app)
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>cheter</title>" in r.text


def test_websocket_flow():
    client = TestClient(main_module.app)

    with client.websocket_connect("/ws/room123") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        joined = ws1.receive_json()
        assert joined["type"] == "joined"
        waiting = ws1.receive_json()
        assert waiting["type"] == "waiting"

        with client.websocket_connect("/ws/room123") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            joined2 = ws2.receive_json()
            assert joined2["type"] == "joined"

            matched2 = ws2.receive_json()
            assert matched2["type"] == "participants"

            matched1 = ws1.receive_json()
            assert matched1["type"] == "participant-joined"

            # offer signaling forwarded from ws2 -> ws1
            ws2.send_json({"type": "offer", "target": joined["participant_id"], "data": {"sdp": "dummy"}})
            sig = ws1.receive_json()
            assert sig["type"] == "signal"
            assert sig["signal_type"] == "offer"

            # leave: ws2 leaves, ws1 should receive participant-left
            ws2.send_json({"type": "leave"})
            peer_left = ws1.receive_json()
            assert peer_left["type"] == "participant-left"


def test_invalid_join():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/invalid") as ws:
        ws.send_json({"type": "bad"})
        err = ws.receive_json()
        assert err["type"] == "error"
        assert "join message" in err["message"]
        # socket should be closed by server; attempting to receive should raise
        with pytest.raises(Exception):
            ws.receive_json()
