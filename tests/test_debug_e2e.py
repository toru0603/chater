from fastapi.testclient import TestClient

import app.main as main_module


def test_debug_e2e_print_branches(monkeypatch):
    # enable DEBUG_E2E just for this test to exercise the debug-print branches
    monkeypatch.setenv("DEBUG_E2E", "1")

    client = TestClient(main_module.app)
    with client.websocket_connect("/ws/dbg") as ws1:
        ws1.send_json({"type": "join", "name": "A"})
        _ = ws1.receive_json()
        _ = ws1.receive_json()

        with client.websocket_connect("/ws/dbg") as ws2:
            ws2.send_json({"type": "join", "name": "B"})
            _ = ws2.receive_json()
            _ = ws2.receive_json()
            _ = ws1.receive_json()

    # test simply ensures branches that print debug messages are executed
