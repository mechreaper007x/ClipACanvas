"""Real WebView2 check: unsaved-work dialog renders inside the desktop app.

Native window.confirm does not render in pywebview/WebView2, so the project
guard must use the in-app #appDialog. Drives the actual desktop window over
CDP. Pass --exe to check dist/ClipACanvas.exe instead of desktop_app.py.
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

PORT = 9417
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)

EXE = ROOT / "dist" / "ClipACanvas.exe"
use_exe = "--exe" in sys.argv


def payload(name, marker):
    return {
        "format": "clipacanvas-project",
        "version": 1,
        "savedAt": "2026-02-01T00:00:00.000Z",
        "projectName": name,
        "timeline": {
            "clips": [{
                "id": "external-clip", "name": "EXTERNAL SCENE",
                "code": f"<div>{marker}</div>", "duration": 1.5, "start": 0,
                "track": 0, "explicitDuration": True, "type": "code",
                "assetId": "", "mediaUrl": "", "mediaName": "", "sourceIn": 0,
                "fit": "contain", "parentClipId": "", "audioTrack": "",
            }],
            "transitions": [], "audioTracks": [], "layers": 1, "playhead": 0, "assets": [],
        },
    }


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        f"--remote-debugging-port={PORT} --remote-allow-origins=*"
    )
    command = [str(EXE)] if use_exe else [sys.executable, str(ROOT / "desktop_app.py")]
    proc = subprocess.Popen(command, cwd=str(ROOT), env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(200):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}")
            page = None
            for _ in range(80):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "desktop page not found"
            page.wait_for_function(
                "() => typeof timelineState !== 'undefined' && typeof applyExternalProject === 'function'",
                timeout=60000,
            )
            wait = lambda expr, timeout=30000: page.wait_for_function(expr, timeout=timeout)

            wait("() => document.getElementById('projectHome').hidden === false")
            page.click("#homeNew")
            wait("() => document.getElementById('homeDialog').hidden === false")
            assert page.input_value("#homeDialogInput").startswith("UNTITLED PROJECT")
            page.fill("#homeDialogInput", "Dialog Test")
            page.click("#homeDialogConfirm")
            wait("() => document.getElementById('projectHome').hidden === true")
            wait("() => document.getElementById('projectName').value === 'DIALOG TEST'")
            page.wait_for_timeout(600)

            page.evaluate("""() => {
                const input = document.getElementById('codeInput');
                input.value = '<div>WEBVIEW UNSAVED</div>';
                syncActiveClipFromEditor(true);
            }""")
            page.evaluate("(payload) => { applyExternalProject(payload, 'external.ccproj.json'); }",
                          payload("External File", "EXTERNAL MARKER"))

            wait("() => { const d = document.getElementById('appDialog');"
                 " return d && !d.hidden && document.getElementById('appDialogTitle').textContent === 'UNSAVED CHANGES'; }")
            assert page.locator("#appDialog").is_visible(), "in-app dialog not visible in WebView2"
            page.screenshot(path=str(OUT / "webview-project-dialog.png"))
            print("dialog visible:", page.locator("#appDialogTitle").inner_text())

            page.click("#appDialogCancel")
            wait("() => document.getElementById('appDialog').hidden === true")
            page.wait_for_timeout(300)
            assert page.evaluate("activeProject && activeProject.id") == "dialog-test", \
                "cancel lost the active project"
            assert "WEBVIEW UNSAVED" in page.evaluate("document.getElementById('codeInput').value")

            page.evaluate("(payload) => { applyExternalProject(payload, 'external.ccproj.json'); }",
                          payload("External File", "EXTERNAL MARKER"))
            wait("() => { const d = document.getElementById('appDialog'); return d && !d.hidden; }")
            page.click("#appDialogAlt")
            wait("() => document.getElementById('projectHome').hidden === true")
            wait("() => document.getElementById('projectName').value === 'EXTERNAL FILE'")
            assert page.evaluate("activeProject && activeProject.id") == "external-file"
            print("WEBVIEW2 PROJECT DIALOG CHECK: OK")
            browser.close()
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        time.sleep(1)
