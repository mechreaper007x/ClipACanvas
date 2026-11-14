"""Desktop Home opens the newest autosave, not the stale library copy."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

DEBUG_PORT = 9421
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)


def scene_clip(name, start):
    return {
        "id": f"clip-{name.lower().replace(' ', '-')}",
        "name": name, "code": "<!doctype html><html><body></body></html>",
        "duration": 4, "start": start, "track": 0, "explicitDuration": True,
        "type": "code", "assetId": "", "mediaUrl": "", "mediaName": "",
        "sourceIn": 0, "fit": "contain", "parentClipId": "", "audioTrack": ""
    }


def project_doc(name, clips, saved_at, project_id):
    return {
        "format": "clipacanvas-project", "version": 1, "savedAt": saved_at,
        "projectName": name, "projectId": project_id,
        "timeline": {"clips": clips, "transitions": [], "audioTracks": [], "layers": 1,
                     "playhead": 0, "assets": []}
    }


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
    tmp = Path(tmp_name)
    projects = tmp / "appdata" / "projects"
    projects.mkdir(parents=True)
    (projects / "untitled-project.ccproj.json").write_text(json.dumps(
        project_doc("UNTITLED PROJECT", [scene_clip("SCENE 01", 0)],
                    "2026-01-01T00:00:00.000Z", "untitled-project")), encoding="utf-8")
    (projects / "untitled-project.autosave.ccproj.json").write_text(json.dumps(
        project_doc("UNTITLED PROJECT", [scene_clip(f"SCENE 0{i}", (i - 1) * 4) for i in range(1, 6)],
                    "2026-01-02T00:00:00.000Z", "untitled-project")), encoding="utf-8")
    (projects / "index.json").write_text(json.dumps([{
        "id": "untitled-project", "name": "UNTITLED PROJECT",
        "file": "untitled-project.ccproj.json",
        "savedAt": "2026-01-01T00:00:00.000Z",
        "createdAt": "2026-01-01T00:00:00.000Z"
    }]), encoding="utf-8")
    (projects / "session.json").write_text(json.dumps({
        "projectId": "untitled-project", "name": "UNTITLED PROJECT",
        "savedAt": "2026-01-02T00:00:00.000Z"
    }), encoding="utf-8")

    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    # The running packaged app holds the default WebView2 data folder; give the
    # test instance its own so a second WebView2 can attach the CDP port.
    env["APPDATA"] = str(tmp / "appdata-home")
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    log_path = tmp / "desktop.log"
    log = open(log_path, "wb")
    proc = subprocess.Popen([sys.executable, str(ROOT / "desktop_app.py")],
                            cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
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
            page.wait_for_function("() => typeof timelineState !== 'undefined'", timeout=45000)
            page.wait_for_selector(".home-card", timeout=30000)
            card = page.locator('.home-card[data-project-id="untitled-project"]')
            badge = card.locator(".home-badge.recover").inner_text()
            print("home badge:", badge)
            card.click()
            page.wait_for_function("() => timelineState.clips.length === 5", timeout=30000)
            result = page.evaluate("""() => ({
                clips: timelineState.clips.map(clip => clip.name),
                status: document.getElementById('statusBar').textContent,
                homeHidden: document.getElementById('projectHome').hidden
            })""")
            print("opened:", result)
            assert result["clips"] == ["SCENE 01", "SCENE 02", "SCENE 03", "SCENE 04", "SCENE 05"], result
            assert "AUTOSAVE RESTORED" in result["status"], result
            assert result["homeHidden"], result
            page.screenshot(path=str(OUT / "project-home-recovery.png"))
            browser.close()
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()
        if proc.returncode not in (0, None) and not (OUT / "project-home-recovery.png").exists():
            print("desktop log:", log_path.read_text(encoding="utf-8", errors="replace")[-2000:])

print("WEBVIEW2 HOME RECOVERY: OK")
