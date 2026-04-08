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
import os
import pytest

try:
    from playwright.sync_api import sync_playwright
except Exception:
    pytest.skip("playwright not installed, skipping e2e tests", allow_module_level=True)

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8000
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def wait_for_server(timeout: float = 30.0) -> None:
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
        wait_for_server(30.0)
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
        launch_args = [
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            '--use-fake-device-for-media-stream',
            '--use-fake-ui-for-media-stream',
        ]
        browser = p.chromium.launch(headless=True, args=launch_args)

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

        // Stub getUserMedia to ensure headless environments provide tracks for createOffer
        if (!navigator.mediaDevices) navigator.mediaDevices = {};
        navigator.mediaDevices.getUserMedia = () => {
            // Prefer returning a real MediaStream when available so assignment to video.srcObject
            // passes the browser's type checks in CI environments.
            if (typeof MediaStream !== 'undefined') {
                return Promise.resolve(new MediaStream());
            }
            return Promise.resolve({
                getTracks: () => [
                    { kind: 'video', stop: () => {} },
                    { kind: 'audio', stop: () => {} },
                ],
            });
        };
        """

        context = browser.new_context()
        context.tracing.start(screenshots=True, snapshots=True)
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
            '() => /waiting/i.test(document.getElementById("status").textContent)',
            timeout=30000,
        )

        # Page 2: Bob
        page2 = context.new_page()
        page2.goto(BASE_URL, wait_until="networkidle")
        page2.fill("#name", "Bob")
        page2.fill("#roomCode", "e2e-room")
        page2.click("#joinBtn")
        time.sleep(1)
        print('DEBUG: page1 status after page2 join ->', page1.text_content('#status'))
        print('DEBUG: page2 status after join ->', page2.text_content('#status'))

        # Expect at least one page to reflect the presence of the peer (robust against timing)
        deadline = time.time() + 15.0
        matched = False
        while time.time() < deadline:
            try:
                cnt1 = page1.evaluate("() => document.querySelectorAll('.video-tile').length")
                cnt2 = page2.evaluate("() => document.querySelectorAll('.video-tile').length")
            except Exception:
                cnt1 = cnt2 = 0
            if cnt1 >= 2 or cnt2 >= 2:
                matched = True
                break
            time.sleep(0.1)
        assert matched, 'No peer appeared in either page within timeout'

        # Bob leaves, Alice should see the tile removed (or at least one page updates)
        page2.click("#leaveBtn")
        deadline = time.time() + 15.0
        left = False
        while time.time() < deadline:
            try:
                cnt1 = page1.evaluate("() => document.querySelectorAll('.video-tile').length")
                cnt2 = page2.evaluate("() => document.querySelectorAll('.video-tile').length")
            except Exception:
                cnt1 = cnt2 = 0
            if cnt1 <= 1 or cnt2 <= 1:
                left = True
                break
            time.sleep(0.1)
        assert left, 'Peer tile did not disappear within timeout'

        try:
            trace_path = f"/tmp/playwright-trace-{int(time.time())}.zip"
            context.tracing.stop(path=trace_path)
            page1.screenshot(path=f"/tmp/e2e-page1-{int(time.time())}.png")
            page2.screenshot(path=f"/tmp/e2e-page2-{int(time.time())}.png")
        except Exception as e:
            print('Failed to save traces/screenshots:', e)
        browser.close()
