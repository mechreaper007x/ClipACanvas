"""Undo/redo snapshot history for timeline edits."""
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

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    still = tmp / "still.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x20c060:s=320x180:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    server, thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)
            page.set_input_files("#mediaInput", [str(still)])
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=60000)
            asset_id = page.evaluate("timelineState.assets[0].id")
            page.evaluate(f"selectAsset('{asset_id}')")
            page.click("#miInsert")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=15000)
            assert page.evaluate("document.getElementById('boxUndo').disabled") is False

            page.keyboard.press("Control+z")
            page.wait_for_function("() => timelineState.clips.length === 1", timeout=5000)
            print("after undo clips:", page.evaluate("timelineState.clips.length"),
                  "undo disabled:", page.evaluate("document.getElementById('boxUndo').disabled"),
                  "redo disabled:", page.evaluate("document.getElementById('boxRedo').disabled"))
            assert page.evaluate("document.getElementById('boxRedo').disabled") is False

            page.keyboard.press("Control+Shift+z")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=5000)
            print("after redo clips:", page.evaluate("timelineState.clips.length"))

            # Toolbar buttons work too.
            page.click("#boxUndo")
            page.wait_for_function("() => timelineState.clips.length === 1", timeout=5000)
            page.click("#boxRedo")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=5000)

            # Playhead moves are not undo steps.
            history_before = page.evaluate("timelineHistoryPast.length")
            page.evaluate("setPlayhead(2.0)")
            page.wait_for_timeout(400)
            assert page.evaluate("timelineHistoryPast.length") == history_before

            # Undo inside a text input stays native, not timeline undo.
            page.fill("#projectName", "HISTORY TEST")
            page.keyboard.press("Control+z")
            page.wait_for_timeout(300)
            assert page.evaluate("timelineState.clips.length") == 2

            page.screenshot(path=str(ROOT / "output" / "playwright" / "timeline-history.png"), full_page=True)
            browser.close()
    finally:
        stop_server(server)
    print("PASS timeline history")
