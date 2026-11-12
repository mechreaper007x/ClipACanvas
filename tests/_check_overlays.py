"""Overlay relationships: attach/detach, parent moves/trims/deletes, agent tools."""
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
    video = tmp / "motion.mp4"
    audio = tmp / "tone.mp3"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=1.2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)

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
            page.set_input_files("#mediaInput", [str(video), str(audio)])
            page.wait_for_function("() => timelineState.assets.length === 2", timeout=30000)
            page.wait_for_timeout(700)
            assets = page.evaluate("Object.fromEntries(timelineState.assets.map(a => [a.kind, a.id]))")

            page.evaluate("""() => {
                timelineState.clips = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                timelineState.selectedAssetId = null;
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")

            def ops(name, *args):
                return page.evaluate("([name, args]) => projectOps[name](...args)", [name, list(args)])

            def tool(name, args):
                return page.evaluate("async ([name, args]) => executeChatTool({name, args})", [name, args])

            parent = ops("insertAsset", assets["video"], {"track": 0, "at": 1})
            assert parent["ok"], parent
            parent_id = parent["clipId"]
            overlay = ops("createComposition", {
                "name": "TITLE", "code": OVERLAY_CODE, "track": 1, "start": 1, "duration": 1.2,
            })
            assert overlay["ok"], overlay
            overlay_id = overlay["clipId"]

            attached = ops("attachOverlay", overlay_id, parent_id)
            assert attached["ok"] and attached["track"] == 1, attached
            state = page.evaluate(
                "([o]) => ({parent: timelineState.clips.find(c=>c.id===o).parentClipId})",
                [overlay_id],
            )
            assert state["parent"] == parent_id, state
            ops("selectClip", overlay_id)
            page.wait_for_timeout(300)
            assert page.locator("#ciParentField").is_visible(), "attach relationship missing from inspector"
            assert "motion" in page.locator("#ciParent").inner_text()
            print("attached:", attached)

            # Parent drag in the timeline shifts the attached overlay.
            lane = page.locator('.et-row[data-track="0"] .et-lane').bounding_box()
            box = page.locator(f'.logic-box[data-id="{parent_id}"]').bounding_box()
            total = page.evaluate("timelineTotalSeconds()")
            dx = lane["width"] * (1 / total)
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 + dx, box["y"] + box["height"] / 2, steps=14)
            page.mouse.up()
            page.wait_for_timeout(500)
            moved = page.evaluate(
                "([p, o]) => ({parent: timelineState.clips.find(c=>c.id===p).start, overlay: timelineState.clips.find(c=>c.id===o).start})",
                [parent_id, overlay_id],
            )
            print("after parent drag:", moved)
            assert moved["parent"] > 1.5, moved
            assert abs(moved["overlay"] - moved["parent"]) < 0.2, moved

            # Trimming the parent in-point shifts the overlay by the same delta.
            before = page.evaluate(
                "([p, o]) => ({p: timelineState.clips.find(c=>c.id===p).start, o: timelineState.clips.find(c=>c.id===o).start})",
                [parent_id, overlay_id],
            )
            trimmed = ops("trimClip", parent_id, {"start": before["p"] + 0.3})
            assert trimmed["ok"], trimmed
            after = page.evaluate(
                "([p, o]) => ({p: timelineState.clips.find(c=>c.id===p).start, o: timelineState.clips.find(c=>c.id===o).start})",
                [parent_id, overlay_id],
            )
            print("trim shift:", before, "->", after)
            assert abs((after["o"] - before["o"]) - 0.3) < 0.05, (before, after)

            # Detach keeps the overlay in place; later parent moves no longer shift it.
            detached = ops("detachOverlay", overlay_id)
            assert detached["ok"], detached
            assert page.evaluate("timelineState.clips.find(c=>c.id=== '" + overlay_id + "').parentClipId") == ""
            overlay_start = page.evaluate(f"timelineState.clips.find(c=>c.id==='{overlay_id}').start")
            ops("moveClip", parent_id, {"track": 0, "at": 2.4})
            assert page.evaluate(f"timelineState.clips.find(c=>c.id==='{overlay_id}').start") == overlay_start

            # Reattach, then deleting the parent detaches the overlay and keeps it.
            assert ops("attachOverlay", overlay_id, parent_id)["ok"]
            deleted = ops("deleteClip", parent_id)
            assert deleted["ok"], deleted
            survivor = page.evaluate(
                "() => ({exists: Boolean(timelineState.clips.find(c=>c.id==='" + overlay_id + "')), parent: timelineState.clips.find(c=>c.id==='" + overlay_id + "')?.parentClipId})"
            )
            assert survivor["exists"] and survivor["parent"] == "", survivor
            print("parent delete keeps detached overlay:", survivor)

            # Validation: self, audio, missing and chains are rejected.
            audio_clip = ops("insertAsset", assets["audio"], {"track": 2, "at": 0})
            assert audio_clip["ok"]
            assert not ops("attachOverlay", overlay_id, overlay_id)["ok"]
            assert not ops("attachOverlay", audio_clip["clipId"], overlay_id)["ok"]
            assert not ops("attachOverlay", overlay_id, "missing")["ok"]
            parent2 = ops("createComposition", {"name": "PARENT2", "code": OVERLAY_CODE, "track": 0, "start": 0, "duration": 1})
            child2 = ops("createComposition", {"name": "CHILD2", "code": OVERLAY_CODE, "track": 1, "start": 0, "duration": 1})
            assert ops("attachOverlay", child2["clipId"], parent2["clipId"])["ok"]
            chained = ops("attachOverlay", parent2["clipId"], child2["clipId"])
            assert not chained["ok"], chained

            # Persistence keeps the relationship.
            assert ops("attachOverlay", overlay_id, parent2["clipId"])["ok"]
            page.reload(wait_until="load")
            page.wait_for_timeout(1800)
            restored = page.evaluate(
                "() => timelineState.clips.find(c=>c.id==='" + overlay_id + "')?.parentClipId"
            )
            assert restored == parent2["clipId"], restored

            # Agent overlay tools operate on the same model.
            created = tool("create_overlay", {
                "code": OVERLAY_CODE, "name": "LOWER THIRD", "parentClipId": parent2["clipId"],
            })
            assert created["ok"], created
            created_id = created["context"]["clip"]["id"]
            assert created["context"]["parent"]["id"] == parent2["clipId"], created
            assert created["context"]["clip"]["parentClipId"] == parent2["clipId"]
            updated = tool("update_overlay", {"clipId": created_id, "name": "CAPTION", "duration": 0.8})
            assert updated["ok"] and updated["changes"]["name"] == "CAPTION", updated
            context = tool("get_clip_context", {"clipId": parent2["clipId"]})
            assert context["ok"] and any(c["id"] == created_id for c in context["children"]), context
            assert tool("detach_overlay", {"clipId": created_id})["ok"]
            assert tool("delete_overlay", {"clipId": created_id})["ok"]
            assert not page.evaluate(f"Boolean(timelineState.clips.find(c=>c.id==='{created_id}'))")

            page.screenshot(path=str(ROOT / "output" / "playwright" / "overlay-attachment.png"))
            browser.close()
            assert not errors, errors
            print("OVERLAY ATTACHMENT CHECK: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
