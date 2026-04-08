import sys
import subprocess
import time
import urllib.request
import os

from playwright.sync_api import sync_playwright

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8001
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


if __name__ == '__main__':
    proc = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "app.main:app", "--host", SERVER_HOST, "--port", str(SERVER_PORT)
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        wait_for_server(10)
        with sync_playwright() as p:
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--use-fake-device-for-media-stream',
                '--use-fake-ui-for-media-stream',
            ]
            browser = p.chromium.launch(headless=False, args=launch_args)
            init_script = r"""
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
            if (!navigator.mediaDevices) navigator.mediaDevices = {};
            navigator.mediaDevices.getUserMedia = () => {
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

            page1 = context.new_page()
            page1.on("console", lambda msg: print('PAGE1 console:', msg.text))
            page1.goto(BASE_URL, wait_until="networkidle")
            page1.fill("#name", "Alice")
            page1.fill("#roomCode", "e2e-room")
            page1.click("#joinBtn")
            time.sleep(0.5)
            print('DEBUG: page1 status after join ->', page1.text_content('#status'))

            page2 = context.new_page()
            page2.on("console", lambda msg: print('PAGE2 console:', msg.text))
            page2.goto(BASE_URL, wait_until="networkidle")
            page2.fill("#name", "Bob")
            page2.fill("#roomCode", "e2e-room")
            page2.click("#joinBtn")
            time.sleep(0.5)
            print('DEBUG: page1 status after page2 join ->', page1.text_content('#status'))
            print('DEBUG: page2 status after join ->', page2.text_content('#status'))

            try:
                print('DEBUG: page1 last_ws ->', page1.evaluate("() => window.__last_ws_message"))
            except Exception as e:
                print('DEBUG: page1 last_ws failed', e)
            try:
                print('DEBUG: page2 last_ws ->', page2.evaluate("() => window.__last_ws_message"))
            except Exception as e:
                print('DEBUG: page2 last_ws failed', e)

            # check video tiles counts
            cnt1 = page1.evaluate("() => document.querySelectorAll('.video-tile').length")
            cnt2 = page2.evaluate("() => document.querySelectorAll('.video-tile').length")
            print('DEBUG: tile counts after join', cnt1, cnt2)

            # save traces
            trace_path = f"/tmp/playwright-trace-debug-{int(time.time())}.zip"
            context.tracing.stop(path=trace_path)
            try:
                page1.screenshot(path=f"/tmp/e2e-debug-page1-{int(time.time())}.png")
                page2.screenshot(path=f"/tmp/e2e-debug-page2-{int(time.time())}.png")
            except Exception as e:
                print('Failed to save screenshots', e)
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
