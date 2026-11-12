import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

ffmpeg = resolve_ffmpeg_exe()


def make_still(tmp: Path) -> Path:
    still = tmp / "still.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x20c060:s=320x180:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    return still


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(appdata)
    still_file = make_still(tmp)
    server, thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1480, "height": 960})
            page = context.new_page()
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)

            # Fresh project: restore settles empty and any later edit autosaves.
            autosave = appdata / "projects" / "autosave.ccproj.json"

            page.set_input_files("#mediaInput", [str(still_file)])
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=60000)
            asset_id = page.evaluate("timelineState.assets[0].id")
            page.evaluate(f"selectAsset('{asset_id}')")
            page.click("#miInsert")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=15000)

            page.fill("#projectName", "PERSIST TEST")
            page.dispatch_event("#projectName", "change")
            page.evaluate("setPlayhead(1.0)")

            page.wait_for_function(
                "() => document.getElementById('saveStateText').textContent === 'SAVED'",
                timeout=15000,
            )
            deadline = 15
            saved = None
            for _ in range(deadline * 10):
                try:
                    candidate = json.loads(autosave.read_text(encoding="utf-8"))
                    if candidate.get("projectName") == "PERSIST TEST" and len(candidate["timeline"]["clips"]) == 2:
                        saved = candidate
                        break
                except (OSError, ValueError, KeyError):
                    pass
                page.wait_for_timeout(100)
            assert saved is not None, "autosave did not capture the edit"
            print("autosave project:", saved.get("projectName"), "clips:", len(saved["timeline"]["clips"]),
                  "assets:", len(saved["timeline"]["assets"]))
            assert saved["projectName"] == "PERSIST TEST", saved.get("projectName")
            assert len(saved["timeline"]["clips"]) == 2, len(saved["timeline"]["clips"])
            assert saved["timeline"]["assets"][0]["url"].startswith("/media/")

            # Named library save + reopen through the PROJECT tab list.
            page.evaluate("saveProjectToLibrary()")
            page.wait_for_function(
                "() => document.querySelectorAll('#projectLibraryList .project-row').length === 1",
                timeout=15000,
            )
            page.on("dialog", lambda dialog: dialog.accept())
            page.evaluate("timelineState.clips = timelineState.clips.slice(0, 1); saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();")
            page.wait_for_function("() => timelineState.clips.length === 1", timeout=5000)
            page.click("#projectLibraryList .project-row")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=15000)
            print("library reopen clips:", page.evaluate("timelineState.clips.length"),
                  "name:", page.evaluate("document.getElementById('projectName').value"))

            # Simulate a private-profile relaunch: wipe browser storage and reload.
            page.evaluate("localStorage.clear()")
            page.reload(wait_until="load")
            page.wait_for_function(
                "() => timelineState.clips.length === 2 && timelineState.assets.length === 1",
                timeout=30000,
            )
            restored = page.evaluate("""() => ({
                name: document.getElementById('projectName').value,
                clips: timelineState.clips.length,
                assets: timelineState.assets.map(a => a.url),
                plays: timelineState.playhead
            })""")
            print("restored:", restored)
            assert restored["name"] == "PERSIST TEST", restored
            assert restored["clips"] == 2, restored
            assert restored["assets"][0].startswith("/media/"), restored
            assert abs(restored["plays"] - 1.0) < 0.01, restored

            # A media file gone from disk drops the asset instead of showing a broken card.
            page.screenshot(path=str(ROOT / "output" / "playwright" / "project-persistence.png"), full_page=True)
            browser.close()
    finally:
        stop_server(server)
    print("PASS project persistence")
