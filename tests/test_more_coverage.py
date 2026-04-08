from fastapi.testclient import TestClient

import app.main as main_module
from app.room_manager import Room, Participant


def test_index_route():
    client = TestClient(main_module.app)
    r = client.get("/")
    assert r.status_code == 200
    assert "cheter" in r.text or "cheter" in r.text


def test_room_peers_and_participant_list():
    room = Room(code="rtest")
    p1 = Participant(id="p1", name="A", room_code="rtest", role="host", color="#fff", websocket=None)
    p2 = Participant(id="p2", name="B", room_code="rtest", role="guest", color="#000", websocket=None)
    room.participants[p1.id] = p1
    room.participants[p2.id] = p2

    peers = room.peers_of("p1")
    assert len(peers) == 1 and peers[0].id == "p2"

    plist = room.participant_list()
    assert len(plist) == 2


def test_disconnect_sends_peer_left_and_participant_left():
    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/disco") as ws1:
        ws1.send_json({"type": "join", "name": "Alice"})
        _ = ws1.receive_json()
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/disco") as ws2:
            ws2.send_json({"type": "join", "name": "Bob"})
            _ = ws2.receive_json()
            _ = ws2.receive_json()
            _ = ws1.receive_json()

            # close ws2 to trigger removal
            # exiting context will close websocket
            pass

        # after ws2 context closed, ws1 should receive peer-left and participant-left
        found_peer_left = False
        found_participant_left = False
        # collect any queued messages
        try:
            while True:
                msg = ws1.receive_json()
                if msg.get("type") == "peer-left":
                    found_peer_left = True
                if msg.get("type") == "participant-left":
                    found_participant_left = True
                if found_peer_left and found_participant_left:
                    break
        except Exception:
            # no more messages
            pass

        assert found_peer_left and found_participant_left
