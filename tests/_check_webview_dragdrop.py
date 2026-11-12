"""Drive the real desktop WebView2 window through CDP and drag an imported
image from the bin onto the timeline, including the empty area below tracks."""
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
from serve import resolve_ffmpeg_exe

from playwright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()
DEBUG_PORT = 9411
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    image = tmp / "still.png"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
                    "-frames:v", "1", str(image)], capture_output=True, check=True)

    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "desktop_app.py")],
        cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    try:
        version = None
        for _ in range(160):
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1) as resp:
                    version = json.loads(resp.read())
                break
            except Exception:
                time.sleep(0.5)
        assert version, "WebView2 remote debugging endpoint never came up"
        print("webview runtime:", version.get("Browser"))

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
            assert page is not None, "desktop app page not found over CDP"
            page.wait_for_function(
                "() => typeof timelineState !== 'undefined' && typeof placeAssetClipAt === 'function'",
                timeout=45000,
            )
            page.wait_for_timeout(800)
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            print("viewport:", page.evaluate("window.innerWidth + 'x' + window.innerHeight"))

            page.set_input_files("#mediaInput", str(image))
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=30000)
            page.wait_for_timeout(800)
            asset = page.evaluate("({id: timelineState.assets[0].id, url: timelineState.assets[0].url})")
            print("imported asset:", asset)

            page.evaluate("""() => {
                timelineState.clips = [{id: 'box-ref', name: 'REF', code: '', duration: 6,
                    start: 0, track: 3, explicitDuration: true, type: 'code'}];
                timelineState.layers = 4;
                timelineState.activeId = 'box-ref';
                timelineState.playhead = 0;
                saveTimelineState(true);
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(400)
            page.evaluate("""() => {
                const host = document.getElementById('logicTracks');
                host.scrollTop = host.scrollHeight;
            }""")
            page.wait_for_timeout(250)

            def drag(asset_id, target):
                card = page.locator(f'.dock-bin[data-asset-id="{asset_id}"]').bounding_box()
                page.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
                page.mouse.down()
                page.mouse.move(card["x"] + card["width"] / 2 + 30, card["y"] - 20, steps=5)
                page.wait_for_timeout(120)
                page.mouse.move(target["x"], target["y"], steps=16)
                page.wait_for_timeout(150)
                page.mouse.move(target["x"] + 1, target["y"])
                page.wait_for_timeout(250)
                hint = page.locator("#etDropHint").inner_text()
                marker = page.locator("#dropMarkerTime").inner_text()
                print("drag feedback:", hint, "|", marker)
                page.mouse.up()
                page.wait_for_timeout(600)
                return hint, marker

            lane = page.locator('.et-row[data-track="0"] .et-lane').bounding_box()
            target = {"x": lane["x"] + lane["width"] * 0.25, "y": lane["y"] + lane["height"] / 2}
            hint, marker = drag(asset["id"], target)
            assert "DROP AT" in hint and "V1" in hint, hint
            assert marker, "no timestamp near the drop marker"

            clip = page.evaluate("timelineState.clips.find(c => c.type === 'image')")
            print("webview drop clip:", clip)
            assert clip, "drop did not create a clip in WebView2"
            assert clip["track"] == 0, clip
            assert abs(clip["start"] - 1.5) < 0.3, clip
            assert abs(clip["duration"] - 3) < 0.01, clip
            assert clip["assetId"] == asset["id"]
            assert page.evaluate("timelineState.activeId") == clip["id"]
            assert page.locator("#mediaInspector").is_visible(), "inspector did not follow the drop"
            page.screenshot(path=str(OUT / "webview-dragdrop.png"))

            # Empty area below the tracks (fixed-height rows leave unused space).
            page.evaluate("""() => {
                timelineState.clips = [{id: 'box-ref', name: 'REF', code: '', duration: 6,
                    start: 0, track: 1, explicitDuration: true, type: 'code'}];
                timelineState.layers = 2;
                timelineState.activeId = 'box-ref';
                saveTimelineState(true);
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(350)
            wrap = page.evaluate("document.getElementById('etTracksWrap').getBoundingClientRect().toJSON()")
            empty_target = {"x": wrap["x"] + wrap["width"] * 0.55, "y": wrap["y"] + wrap["height"] - 24}
            hint, marker = drag(asset["id"], empty_target)
            assert "DROP AT" in hint, hint
            clips = page.evaluate("timelineState.clips.filter(c => c.type === 'image')")
            print("empty-area clips:", [(c["track"], c["start"]) for c in clips])
            assert len(clips) == 1 and clips[0]["track"] == 0, clips
            assert abs(clips[0]["start"] - 3.3) < 0.4, clips

            page.screenshot(path=str(OUT / "webview-dragdrop-empty.png"))
            assert not errors, errors
            print("WEBVIEW2 BIN -> TIMELINE DROP: OK")
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
