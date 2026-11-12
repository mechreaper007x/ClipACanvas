"""Structured project operations: validation, mutation, persistence and UI sync."""
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
errors = []

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    image = tmp / "still.png"
    video = tmp / "motion.mp4"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
                    "-frames:v", "1", str(image)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=1.2:r=24",
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

            page.set_input_files("#mediaInput", [str(image), str(video)])
            page.wait_for_function("() => timelineState.assets.length === 2", timeout=30000)
            page.wait_for_timeout(600)
            ids = page.evaluate(
                "Object.fromEntries(timelineState.assets.map(a => [a.kind, a.id]))"
            )
            img_id, vid_id = ids["image"], ids["video"]

            page.evaluate("""() => {
                timelineState.clips = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                timelineState.selectedAssetId = null;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: false });
                renderLogicBoxes();
                renderProjectBin();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(300)
            assert page.evaluate("typeof window.projectOps === 'object'"), "projectOps is not exposed"

            def ops(name, *args):
                return page.evaluate(
                    "([name, args]) => projectOps[name](...args)",
                    [name, list(args)],
                )

            def clips():
                return page.evaluate("timelineState.clips.map(c => ({id:c.id,name:c.name,type:c.type,start:c.start,duration:c.duration,track:c.track,sourceIn:c.sourceIn,code:c.code}))")

            # 1. Explicit-track composition creation.
            created = ops("createComposition", {
                "name": "OPS SCENE",
                "code": "<!doctype html><html><body style=\"margin:0;background:#00c040\"></body></html>",
                "track": 1,
                "start": 1,
                "duration": 2,
            })
            assert created["ok"], created
            scene = next(c for c in clips() if c["id"] == created["clipId"])
            assert scene["track"] == 1 and abs(scene["start"] - 1) < 0.01 and abs(scene["duration"] - 2) < 0.01, scene
            assert page.evaluate("timelineState.activeId") == scene["id"]
            assert "OPS SCENE" in page.locator("#codeClipName").inner_text()
            scene_id = scene["id"]

            # 2. Track creation and asset insertion at explicit positions.
            track = ops("createTrack")
            assert track["ok"] and track["layers"] == 3, track
            image_clip = ops("insertAsset", img_id, {"track": 0, "at": 0})
            video_clip = ops("insertAsset", vid_id, {"track": 0, "at": 4})
            assert image_clip["ok"] and video_clip["ok"], (image_clip, video_clip)
            assert page.locator("#mediaInspector").is_visible(), "inspector did not follow insertAsset"
            assert page.locator("#miName").inner_text() == "motion"
            by_id = {c["id"]: c for c in clips()}
            assert by_id[image_clip["clipId"]]["type"] == "image"
            assert abs(by_id[image_clip["clipId"]]["duration"] - 3) < 0.01
            assert abs(by_id[video_clip["clipId"]]["duration"] - 1.2) < 0.05

            # 3. Moves: to a free spot, then rejected on an occupied range.
            moved = ops("moveClip", image_clip["clipId"], {"track": 2, "at": 4})
            assert moved["ok"], moved
            rejected = ops("moveClip", image_clip["clipId"], {"track": 1, "at": 2})
            assert not rejected["ok"] and "occupied" in rejected["error"].lower(), rejected
            unchanged = next(c for c in clips() if c["id"] == image_clip["clipId"])
            assert unchanged["track"] == 2 and abs(unchanged["start"] - 4) < 0.01, unchanged
            free = ops("moveClip", image_clip["clipId"], {"track": 1, "at": 4})
            assert free["ok"], free

            # 4. Trimming: image edges keep sourceIn; video in-point follows.
            trimmed = ops("trimClip", image_clip["clipId"], {"start": 5, "end": 7})
            assert trimmed["ok"], trimmed
            still = next(c for c in clips() if c["id"] == image_clip["clipId"])
            assert abs(still["duration"] - 2) < 0.01 and abs(still["sourceIn"]) < 0.01, still
            trim_video = ops("trimClip", video_clip["clipId"], {"start": 4.5})
            assert trim_video["ok"], trim_video
            motion = next(c for c in clips() if c["id"] == video_clip["clipId"])
            assert abs(motion["start"] - 4.5) < 0.01 and abs(motion["duration"] - 0.7) < 0.05, motion
            assert abs(motion["sourceIn"] - 0.5) < 0.1, motion
            bad_trim = ops("trimClip", scene_id, {"start": 1, "end": 1.2})
            assert not bad_trim["ok"], bad_trim

            # 5. Split and duplicate.
            split = ops("splitClip", scene_id, 2)
            assert split["ok"], split
            right = next(c for c in clips() if c["id"] == split["clipId"])
            assert abs(right["start"] - 2) < 0.01 and abs(right["duration"] - 1) < 0.01, right
            assert page.evaluate("timelineState.activeId") == right["id"]
            dup = ops("duplicateClip", image_clip["clipId"])
            assert dup["ok"], dup
            copy = next(c for c in clips() if c["id"] == dup["clipId"])
            assert copy["type"] == "image" and copy["track"] == still["track"], copy
            assert copy["start"] >= still["start"] + still["duration"] - 0.01, copy

            # 6. Seek, delete ripple, invalid references.
            seek = ops("seek", 2.5)
            assert seek["ok"] and abs(page.evaluate("timelineState.playhead") - 2.5) < 0.01
            assert "2.50s" in page.locator("#timelineTime").inner_text()
            before = len(clips())
            deleted = ops("deleteClip", dup["clipId"])
            assert deleted["ok"], deleted
            assert len(clips()) == before - 1
            assert not ops("deleteClip", "missing-clip")["ok"]
            assert not ops("splitClip", scene_id, 99)["ok"]
            assert not ops("insertAsset", "missing-asset", {})["ok"]

            # 7. Timeline DOM and render plan follow the model.
            assert page.locator(".logic-box").count() == len(clips())
            plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(plan["clips"]) == len(clips()), (len(plan["clips"]), len(clips()))
            assert any("00c040" in clip.get("code", "") for clip in plan["clips"]), "scene code missing from the render plan"

            snapshot = ops("snapshot")
            assert snapshot["name"] and snapshot["duration"] >= 5, snapshot
            assert len(snapshot["clips"]) == len(clips()) and len(snapshot["assets"]) == 2
            assert all("codeLength" in clip for clip in snapshot["clips"])

            # 8. Operations persist through a reload.
            saved = page.evaluate("JSON.parse(localStorage.getItem('clipacanvas.timeline.v1'))")
            assert any(c.get("id") == right["id"] for c in saved["clips"]), "split clip not persisted"
            page.reload(wait_until="load")
            page.wait_for_timeout(1600)
            restored = clips()
            assert len(restored) == len(saved["clips"]), (len(restored), len(saved["clips"]))
            assert any(c["id"] == right["id"] and "00c040" in (c["code"] or "") for c in restored)
            assert any(c["id"] == image_clip["clipId"] for c in restored)

            browser.close()
            assert not errors, errors
            print("PROJECT OPERATIONS CHECK: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
