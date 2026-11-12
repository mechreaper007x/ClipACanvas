"""Overlay attachment UI in the real desktop WebView2."""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

DEBUG_PORT = 9417
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
OVERLAY_CODE = '<!doctype html><html><body style="margin:0;background:transparent"><h1 style="color:#c8ff00">TITLE</h1></body></html>'

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    proc = subprocess.Popen([sys.executable, str(ROOT / "desktop_app.py")],
                            cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(160):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
            page = None
            for _ in range(60):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "desktop page not found"
            page.wait_for_function("() => typeof timelineState !== 'undefined' && typeof projectOps === 'object'", timeout=45000)
            page.wait_for_timeout(800)
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            print("webview:", page.evaluate("navigator.userAgent"))

            page.evaluate("""() => {
                timelineState.clips = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")

            def ops(name, *args):
                return page.evaluate("([name, args]) => projectOps[name](...args)", [name, list(args)])

            parent = ops("createComposition", {
                "name": "BASE", "code": '<html><body style="background:#101010"></body></html>',
                "track": 0, "start": 0, "duration": 3,
            })
            overlay = ops("createComposition", {
                "name": "TITLE", "code": OVERLAY_CODE, "track": 1, "start": 0, "duration": 3,
            })
            assert parent["ok"] and overlay["ok"], (parent, overlay)
            parent_id = parent["clipId"]
            overlay_id = overlay["clipId"]

            ops("selectClip", overlay_id)
            page.wait_for_timeout(400)
            assert page.locator("#ciAttachBlock").is_visible()
            assert page.locator("#ciAttachStatus").inner_text() == "NOT ATTACHED"
            options = page.evaluate("() => [...document.getElementById('ciAttachParent').options].map(o => o.textContent)")
            print("webview options:", options)
            assert len(options) == 1 and options[0].startswith("BASE"), options

            page.click("#ciAttachBtn")
            page.wait_for_timeout(600)
            attached = page.evaluate("([o]) => timelineState.clips.find(c => c.id === o).parentClipId", [overlay_id])
            print("webview attached:", attached)
            assert attached == parent_id
            assert page.locator("#ciAttachStatus").inner_text() == "ATTACHED"
            assert page.locator("#ciDetachBtn").is_visible()

            page.screenshot(path=str(OUT / "webview-overlay-attach.png"))
            page.reload(wait_until="load")
            page.wait_for_timeout(1700)
            ops("selectClip", overlay_id)
            page.wait_for_timeout(400)
            restored = page.evaluate("([o]) => timelineState.clips.find(c => c.id === o).parentClipId", [overlay_id])
            assert restored == parent_id, restored
            assert page.locator("#ciAttachStatus").inner_text() == "ATTACHED"

            page.click("#ciDetachBtn")
            page.wait_for_timeout(500)
            detached = page.evaluate("([o]) => timelineState.clips.find(c => c.id === o).parentClipId", [overlay_id])
            assert detached == ""
            assert page.locator("#ciAttachStatus").inner_text() == "NOT ATTACHED"
            browser.close()
            assert not errors, errors
            print("WEBVIEW2 OVERLAY ATTACH UI: OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
