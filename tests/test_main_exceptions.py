from fastapi.testclient import TestClient

import app.main as main_module
from app.room_manager import RoomManager, Participant, Room


class DummyWS:
    async def send_json(self, *_args, **_kwargs):
        raise Exception("boom")

    async def close(self, *args, **kwargs):
        pass


def test_peer_send_exception_handling():
    # reset room manager
    main_module.room_manager = RoomManager()

    # insert a fake existing participant whose websocket raises on send
    fake = Participant(id="fakeid", name="Fake", room_code="rtest", role="host", color="#fff", websocket=DummyWS())
    room = main_module.room_manager._rooms.setdefault("rtest", Room(code="rtest"))
    room.participants[fake.id] = fake

    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/rtest") as ws:
        ws.send_json({"type": "join", "name": "Real"})
        joined = ws.receive_json()
        assert joined["type"] == "joined"
        # server will attempt to notify the fake participant and that will raise, but should be handled
        next_msg = ws.receive_json()
        assert next_msg["type"] in ("waiting", "participants", "participant-joined")


def test_audio_string_coercion_unknown():
    main_module.room_manager = RoomManager()
    client = TestClient(main_module.app)

    with client.websocket_connect("/ws/rooma") as ws1:
        ws1.send_json({"type": "join", "name": "A"})
        _ = ws1.receive_json()
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/rooma") as ws2:
            ws2.send_json({"type": "join", "name": "B"})
            _ = ws2.receive_json()
            _ = ws2.receive_json()
            _ = ws1.receive_json()

            # send audio with an unknown string to exercise bool(enabled) fallback
            ws1.send_json({"type": "audio", "enabled": "maybe"})
            # ws2 should receive the audio message (skip any participants/matched)
            while True:
                msg = ws2.receive_json()
                if msg.get("type") in {"participants", "matched"}:
                    continue
                break
            assert msg["type"] == "audio"
            assert msg.get("enabled") is True
