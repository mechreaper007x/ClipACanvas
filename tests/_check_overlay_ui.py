"""Overlay attachment UI: code and media clips, attach/detach from inspectors."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import resolve_ffmpeg_exe, server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()
OVERLAY_CODE = '<!doctype html><html><body style="margin:0;background:transparent"><h1 style="color:#c8ff00">TITLE</h1></body></html>'
errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    video = tmp / "base.mp4"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)
            page.set_input_files("#mediaInput", str(video))
            page.wait_for_function("() => timelineState.assets.length === 1 && timelineState.assets[0].analysis?.technical", timeout=45000)
            asset_id = page.evaluate("timelineState.assets[0].id")

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
            assert page.locator("#clipInspector").is_visible()
            assert page.locator("#ciAttachBlock").is_visible()
            assert page.locator("#ciAttachStatus").inner_text() == "NOT ATTACHED"
            assert page.locator("#ciAttachField").is_visible()
            options = page.evaluate("() => [...document.getElementById('ciAttachParent').options].map(o => o.textContent)")
            print("parent options:", options)
            assert len(options) == 1 and options[0].startswith("BASE"), options
            assert page.locator("#ciAttachBtn").is_enabled()
            assert page.locator("#ciDetachBtn").is_hidden()

            page.click("#ciAttachBtn")
            page.wait_for_timeout(500)
            attached = page.evaluate("([o]) => timelineState.clips.find(c => c.id === o).parentClipId", [overlay_id])
            assert attached == parent_id, attached
            assert page.locator("#ciAttachStatus").inner_text() == "ATTACHED"
            assert page.locator("#ciParentField").is_visible()
            assert "BASE" in page.locator("#ciParent").inner_text()
            assert page.locator("#ciAttachField").is_hidden()
            assert page.locator("#ciDetachBtn").is_visible()
            assert "Follows BASE" in page.locator("#ciAttachNote").inner_text()

            # Parent move keeps the linked overlay in sync.
            moved = ops("moveClip", parent_id, {"track": 0, "at": 1})
            assert moved["ok"], moved
            pair = page.evaluate("""([p, o]) => ({
                parent: timelineState.clips.find(c => c.id === p).start,
                overlay: timelineState.clips.find(c => c.id === o).start
            })""", [parent_id, overlay_id])
            print("after move:", pair)
            assert abs(pair["overlay"] - pair["parent"]) < 0.2, pair

            # A second clip cannot use the attached overlay as its parent.
            third = ops("createComposition", {
                "name": "CAPTION", "code": OVERLAY_CODE, "track": 2, "start": 2, "duration": 1,
            })
            assert third["ok"], third
            ops("selectClip", third["clipId"])
            page.wait_for_timeout(400)
            options = page.evaluate("() => [...document.getElementById('ciAttachParent').options].map(o => o.value)")
            print("second options:", options)
            assert overlay_id not in options, options
            assert parent_id in options, options

            # Detach from the overlay's inspector restores the free state.
            ops("selectClip", overlay_id)
            page.wait_for_timeout(400)
            page.click("#ciDetachBtn")
            page.wait_for_timeout(500)
            detached = page.evaluate("([o]) => timelineState.clips.find(c => c.id === o).parentClipId", [overlay_id])
            assert detached == "", detached
            assert page.locator("#ciAttachStatus").inner_text() == "NOT ATTACHED"
            assert page.locator("#ciAttachField").is_visible()
            assert page.locator("#ciDetachBtn").is_hidden()

            OUT = ROOT / "output" / "playwright"
            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUT / "overlay-attach.png"))

            # Reload keeps attachment state set through the UI after re-attaching.
            page.click("#ciAttachBtn")
            page.wait_for_timeout(500)
            page.reload(wait_until="load")
            page.wait_for_timeout(1600)
            ops("selectClip", overlay_id)
            page.wait_for_timeout(400)
            restored = page.evaluate("([o]) => timelineState.clips.find(c => c.id === o).parentClipId", [overlay_id])
            assert restored == parent_id, restored
            assert page.locator("#ciAttachStatus").inner_text() == "ATTACHED"

            # Media clips expose the same attachment controls.
            media_clip = ops("insertAsset", asset_id, {"track": 2, "at": 0.5})
            assert media_clip["ok"], media_clip
            media_id = media_clip["clipId"]
            ops("selectClip", media_id)
            page.wait_for_timeout(500)
            assert page.locator("#mediaInspector").is_visible()
            assert page.locator("#miAttachBlock").is_visible()
            assert page.locator("#miAttachStatus").inner_text() == "NOT ATTACHED"
            media_options = page.evaluate("() => [...document.getElementById('miAttachParent').options].map(o => o.value)")
            assert parent_id in media_options, media_options
            page.select_option("#miAttachParent", parent_id)
            page.click("#miAttachBtn")
            page.wait_for_timeout(500)
            media_parent = page.evaluate("([m]) => timelineState.clips.find(c => c.id === m).parentClipId", [media_id])
            print("media attached:", media_parent)
            assert media_parent == parent_id
            assert page.locator("#miAttachStatus").inner_text() == "ATTACHED"
            assert page.locator("#miDetachBtn").is_visible()
            page.click("#miDetachBtn")
            page.wait_for_timeout(400)
            assert page.evaluate("([m]) => timelineState.clips.find(c => c.id === m).parentClipId", [media_id]) == ""

            browser.close()
            assert not errors, errors
            print("OVERLAY ATTACH UI: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
