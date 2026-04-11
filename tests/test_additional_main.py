import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.room_manager import RoomManager


@pytest.fixture(autouse=True)
def reset_room_manager():
    main_module.room_manager = RoomManager()
    yield


def _recv_skip(ws):
    # Skip any intermediate participants/matched messages
    while True:
        msg = ws.receive_json()
        if msg.get("type") in {"participants", "matched"}:
            continue
        return msg


def test_offer_fallback_to_peer_when_get_peer_raises():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/room1") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        _ = ws1.receive_json()
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/room1") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            _ = ws2.receive_json()
            _ = ws2.receive_json()
            _ = ws1.receive_json()

            # make get_peer raise to force fallback scanning path
            async def _raising_get_peer(pid):
                raise Exception("no peer")

            main_module.room_manager.get_peer = _raising_get_peer

            # send offer without explicit target - should fallback to the single peer
            ws2.send_json({"type": "offer", "data": {"sdp": "dummy"}})

            sig = _recv_skip(ws1)
            assert sig["type"] == "signal"
            assert sig.get("signal_type") == "offer"


def test_audio_string_payload_true():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/room2") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        _ = ws1.receive_json()
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/room2") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            _ = ws2.receive_json()
            _ = ws2.receive_json()
            _ = ws1.receive_json()

            # send audio with string "true"
            ws2.send_json({"type": "audio", "enabled": "true"})
            aud = _recv_skip(ws1)
            assert aud["type"] == "audio"
            assert aud["enabled"] is True
            assert aud["from_name"] == "Bob"


def test_chat_empty_ignored_and_next_chat_delivered():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/room3") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        _ = ws1.receive_json()
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/room3") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            _ = ws2.receive_json()
            _ = ws2.receive_json()
            _ = ws1.receive_json()

            ws1.send_json({"type": "chat", "text": ""})
            ws2.send_json({"type": "chat", "text": "hello"})

            chat = _recv_skip(ws1)
            assert chat["type"] == "chat"
            assert chat["text"] == "hello"
