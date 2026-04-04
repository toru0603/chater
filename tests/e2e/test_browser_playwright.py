"""Playwright-based end-to-end tests for cheter frontend.

These tests start a local uvicorn server, launch a headless Chromium via Playwright,
stub navigator.mediaDevices and RTCPeerConnection so real hardware is not required,
and verify join/match/leave flows through the UI and WebSocket signaling.

To run locally:
  pip install playwright pytest
  python -m playwright install chromium
  pytest -q tests/e2e -k test_browser_playwright

Note: these tests are skipped automatically if Playwright is not installed.
"""

import sys
import subprocess
import time
import urllib.request
import pytest

try:
    from playwright.sync_api import sync_playwright
except Exception:
    pytest.skip("playwright not installed, skipping e2e tests", allow_module_level=True)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def wait_for_server(timeout: float = 10.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(BASE_URL + "/", timeout=1) as r:
                if r.getcode() == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("server did not start within timeout")


@pytest.fixture(scope="module")
def server():
    """Run the uvicorn server for the duration of the test module."""
    proc = subprocess.Popen([
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        SERVER_HOST,
        "--port",
        str(SERVER_PORT),
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        wait_for_server(10.0)
        yield proc
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


def test_browser_playwright_match_and_leave(server):
    """Open two browser pages, join the same room, verify match and peer-left behavior."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--use-fake-device-for-media-stream','--use-fake-ui-for-media-stream'])

        # Inject stubs before any page scripts run so the app JS won't require real devices.
        init_script = r"""
        // Minimal RTCPeerConnection stub to avoid real WebRTC negotiations in headless tests.
        window.RTCPeerConnection = class {
          constructor(){
            this.onicecandidate = null;
            this.ontrack = null;
            this.onconnectionstatechange = null;
            this.connectionState = 'new';
            this.remoteDescription = null;
            this.localDescription = null;
          }
          addTrack(track, stream){ return {}; }
          createOffer(){ return Promise.resolve({type:'offer', sdp:'fake'}); }
          setLocalDescription(desc){ this.localDescription = desc; return Promise.resolve(); }
          setRemoteDescription(desc){ this.remoteDescription = desc; return Promise.resolve(); }
          createAnswer(){ return Promise.resolve({type:'answer', sdp:'fake'}); }
          addIceCandidate(){ return Promise.resolve(); }
          close(){ this.connectionState='closed'; if(this.onconnectionstatechange) this.onconnectionstatechange(); }
        };
        """

        context = browser.new_context()
        context.add_init_script(init_script)

        # Page 1: Alice
        page1 = context.new_page()
        page1.goto(BASE_URL, wait_until="networkidle")
        page1.fill("#name", "Alice")
        page1.fill("#roomCode", "e2e-room")
        page1.click("#joinBtn")
        # DEBUG: small pause and print status
        time.sleep(1)
        print('DEBUG: page1 status after join ->', page1.text_content('#status'))

        # Should see the waiting message
        page1.wait_for_function(
            '() => document.getElementById("status").textContent.includes("waiting for a peer")',
            timeout=15000,
        )

        # Page 2: Bob
        page2 = context.new_page()
        page2.goto(BASE_URL, wait_until="networkidle")
        page2.fill("#name", "Bob")
        page2.fill("#roomCode", "e2e-room")
        page2.click("#joinBtn")

        # Both pages should get matched
        page1.wait_for_function(
            '() => document.getElementById("status").textContent.includes("マッチ成功")',
            timeout=15000,
        )
        page2.wait_for_function(
            '() => document.getElementById("status").textContent.includes("マッチ成功")',
            timeout=15000,
        )

        # Bob leaves, Alice should see peer-left
        page2.click("#leaveBtn")
        page1.wait_for_function(
            '() => document.getElementById("status").textContent.includes("相手が退出しました")',
            timeout=15000,
        )

        browser.close()
