import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.room_manager import RoomManager


@pytest.fixture(autouse=True)
def reset_room_manager():
    main_module.room_manager = RoomManager()
    yield


def test_join_wait_and_match():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/room1") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        joined = ws1.receive_json()
        assert joined["type"] == "joined"
        waiting = ws1.receive_json()
        assert waiting["type"] == "waiting"

        with client.websocket_connect("/ws/room1") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            _ = ws2.receive_json()
            assert joined2["type"] == "joined"

            # ws2 should receive participants/matched about existing participants
            matched2 = ws2.receive_json()
            assert matched2["type"] in ("participants", "matched")

            # ws1 should receive notification about new participant
            matched1 = ws1.receive_json()
            assert matched1["type"] in ("participant-joined", "participants", "matched")

            # send chat and ensure broadcast; skip intermediate matched/participants
            ws1.send_json({"type": "chat", "text": "hello"})
            while True:
                chat_msg = ws2.receive_json()
                if chat_msg.get("type") in {"participants", "matched"}:
                    continue
                break
            assert chat_msg["type"] == "chat"
            assert chat_msg["text"] == "hello"


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


def test_offer_forwarding_and_peer_left():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/room_offer") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        joined1 = ws1.receive_json()
        # waiting or participants
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/room_offer") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            _ = ws2.receive_json()
            # ws2 receives participants/matched
            _ = ws2.receive_json()
            # ws1 receives notification about new participant
            _ = ws1.receive_json()

            # send offer from ws2 to ws1 using explicit target id
            ws2.send_json({"type": "offer", "target": joined1.get("participant_id"), "data": {"sdp": "dummy"}})

            # ws1 should receive a 'signal' message (skip matched/participants)
            while True:
                sig = ws1.receive_json()
                if sig.get("type") in {"participants", "matched"}:
                    continue
                break

            assert sig["type"] == "signal"
            assert sig["signal_type"] == "offer"

            # ws2 leaves, ws1 should receive peer-left/participant-left
            ws2.send_json({"type": "leave"})
            while True:
                peer_left = ws1.receive_json()
                if peer_left.get("type") in {"participants", "matched"}:
                    continue
                break
            assert peer_left["type"] in ("peer-left", "participant-left")

