import pytest
from fastapi.testclient import TestClient

import app.main as main_module
from app.room_manager import RoomManager


@pytest.fixture(autouse=True)
def reset_room_manager():
    main_module.room_manager = RoomManager()
    yield


def test_camera_broadcast():
    client = TestClient(main_module.app)

    with client.websocket_connect("/ws/roomcam") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        joined = ws1.receive_json()
        assert joined["type"] == "joined"
        waiting = ws1.receive_json()
        assert waiting["type"] == "waiting"

        with client.websocket_connect("/ws/roomcam") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            joined2 = ws2.receive_json()
            assert joined2["type"] == "joined"

            participants = ws2.receive_json()
            assert participants["type"] in {"participants", "matched"}

            # consume notification on ws1 about new participant
            joined1 = ws1.receive_json()
            assert joined1["type"] in {"participant-joined", "matched", "participants"}

            # Bob toggles camera off; skip any intermediate matched/participants messages
            ws2.send_json({"type": "camera", "enabled": False})
            while True:
                cam = ws1.receive_json()
                if cam.get("type") in {"participants", "matched"}:
                    continue
                break

            assert cam["type"] == "camera"
            assert cam["from_name"] == "Bob"
            assert cam["enabled"] is False
