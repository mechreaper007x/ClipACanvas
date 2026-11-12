"""Frame stepping, typed A1-A3 lanes and project file round trips."""
import json
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
    video = tmp / "motion.mp4"
    audio = tmp / "music.mp3"
    image = tmp / "still.png"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=320x180:d=1",
                    "-frames:v", "1", str(image)], capture_output=True, check=True)

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
            page.set_input_files("#mediaInput", [str(video), str(image), str(audio)])
            page.wait_for_function(
                "() => timelineState.assets.length === 3 && timelineState.assets.every(a => a.analysis?.technical)",
                timeout=45000,
            )
            asset_ids = page.evaluate("() => Object.fromEntries(timelineState.assets.map(a => [a.kind, a.id]))")

            page.evaluate("""() => {
                timelineState.clips = [];
                timelineState.transitions = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                timelineState.selectedAssetId = null;
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")

            def ops(name, *args):
                return page.evaluate("([name, args]) => projectOps[name](...args)", [name, list(args)])

            video_clip = ops("insertAsset", asset_ids["video"], {"track": 0, "at": 0})
            image_clip = ops("insertAsset", asset_ids["image"], {"track": 1, "at": 1})
            audio_clip = ops("insertAsset", asset_ids["audio"], {"track": 0, "at": 0.5, "audioTrack": "A2"})
            assert video_clip["ok"] and image_clip["ok"] and audio_clip["ok"], (video_clip, image_clip, audio_clip)
            audio_id = audio_clip["clipId"]
            page.wait_for_timeout(500)

            # Typed lanes: audio is rendered under A1-A3, never on V rows.
            assert page.locator(".et-row.audio-row").count() == 3
            assert page.locator(f'.et-lane[data-audio-track="A2"] .logic-box[data-id="{audio_id}"]').count() == 1
            assert page.locator(f'.et-lane[data-track="0"] .logic-box[data-id="{audio_id}"]').count() == 0
            a2_label = page.locator('.et-row[data-audio-row="A2"] .et-label').inner_text()
            print("A2 label:", a2_label.replace("\n", " "))
            assert "MUSIC" in a2_label

            # Drag the audio clip from A2 to A3.
            box = page.locator(f'.et-lane[data-audio-track="A2"] .logic-box[data-id="{audio_id}"]').bounding_box()
            a3_lane = page.locator('.et-row[data-audio-row="A3"] .et-lane')
            a3_lane.scroll_into_view_if_needed()
            a3 = a3_lane.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 + 4, a3["y"] + a3["height"] / 2, steps=14)
            page.mouse.up()
            page.wait_for_timeout(500)
            lane = page.evaluate("([a]) => timelineState.clips.find(c => c.id === a).audioTrack", [audio_id])
            print("after lane drag:", lane)
            assert lane == "A3", lane
            assert page.locator(f'.et-lane[data-audio-track="A3"] .logic-box[data-id="{audio_id}"]').count() == 1

            # Inspector lane select moves it to A1.
            ops("selectClip", audio_id)
            page.wait_for_timeout(400)
            assert page.evaluate("document.getElementById('miAudioTrack').value") == "A3"
            page.select_option("#miAudioTrack", "A1")
            page.wait_for_timeout(400)
            assert page.evaluate("([a]) => timelineState.clips.find(c => c.id === a).audioTrack", [audio_id]) == "A1"
            assert page.locator(f'.et-lane[data-audio-track="A1"] .logic-box[data-id="{audio_id}"]').count() == 1

            # Deleting audio must not ripple video clips.
            video_start = page.evaluate("timelineState.clips.find(c => c.type === 'video').start")
            page.click("#boxDel")
            page.wait_for_timeout(400)
            assert page.evaluate("timelineState.clips.filter(c => c.type === 'audio').length") == 0
            assert page.evaluate("timelineState.clips.find(c => c.type === 'video').start") == video_start

            # Bin drag onto A2 creates an audio clip in that lane.
            def drag_card(asset_id, target_lane):
                card = page.locator(f'.dock-bin[data-asset-id="{asset_id}"]').bounding_box()
                lane_box = target_lane.bounding_box()
                x = lane_box["x"] + lane_box["width"] * 0.25
                y = lane_box["y"] + lane_box["height"] / 2
                page.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
                page.mouse.down()
                page.mouse.move(card["x"] + card["width"] / 2 + 26, card["y"] - 18, steps=4)
                page.mouse.move(x, y, steps=14)
                page.mouse.move(x + 1, y)
                page.wait_for_timeout(200)
                page.mouse.up()
                page.wait_for_timeout(500)

            audio_before = page.evaluate("timelineState.clips.filter(c => c.type === 'audio').length")
            drag_card(asset_ids["audio"], page.locator('.et-row[data-audio-row="A2"] .et-lane'))
            audio_after = page.evaluate("timelineState.clips.filter(c => c.type === 'audio').length")
            dropped = page.evaluate("timelineState.clips.filter(c => c.type === 'audio').map(c => c.audioTrack)")
            print("bin drop lanes:", dropped)
            assert audio_after == audio_before + 1 and "A2" in dropped, (audio_before, audio_after, dropped)

            # Non-audio assets are refused by audio lanes.
            video_before = page.evaluate("timelineState.clips.filter(c => c.type === 'video').length")
            drag_card(asset_ids["video"], page.locator('.et-row[data-audio-row="A3"] .et-lane'))
            assert page.evaluate("timelineState.clips.filter(c => c.type === 'video').length") == video_before
            assert "audio clips only" in page.locator("#statusBar").inner_text().lower()

            # Frame stepping at the project frame rate.
            page.evaluate("setPlayhead(0); document.activeElement?.blur()")
            page.wait_for_timeout(200)
            page.keyboard.press("ArrowRight")
            step = page.evaluate("timelineState.playhead")
            print("one frame:", step)
            assert abs(step - 1 / 60) < 1e-4, step
            assert page.locator("#monitorTime").inner_text().endswith(":01")
            for _ in range(59):
                page.keyboard.press("ArrowRight")
            assert abs(page.evaluate("timelineState.playhead") - 1.0) < 1e-5
            assert page.locator("#monitorTime").inner_text() == "00:00:01:00"
            page.keyboard.press("Shift+ArrowRight")
            assert abs(page.evaluate("timelineState.playhead") - 2.0) < 1e-5
            page.evaluate("document.getElementById('frameRate').value = '30'")
            page.keyboard.press("ArrowRight")
            assert abs(page.evaluate("timelineState.playhead") - (2 + 1 / 30)) < 1e-4
            assert page.locator("#monitorTime").inner_text().endswith(":01")
            page.evaluate("document.getElementById('frameRate').value = '60'")

            # Project file payload and download.
            payload = page.evaluate("buildProjectFilePayload()")
            assert payload["format"] == "clipacanvas-project" and payload["version"] == 1
            assert payload["timeline"]["audioTracks"][0]["id"] == "A1"
            assert len(payload["timeline"]["clips"]) >= 3
            assert len(payload["timeline"]["assets"]) == 3
            saved_clips = len(payload["timeline"]["clips"])
            with page.expect_download() as download_info:
                page.click("#projectSave")
            download = download_info.value
            print("download:", download.suggested_filename)
            assert download.suggested_filename.endswith(".ccproj.json")
            downloaded = json.loads(Path(download.path()).read_text(encoding="utf-8"))
            assert downloaded["format"] == "clipacanvas-project"
            assert len(downloaded["timeline"]["clips"]) == saved_clips

            # Applying a payload restores the full timeline and lanes.
            page.evaluate("""() => {
                timelineState.clips = [];
                timelineState.transitions = [];
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")
            assert page.evaluate("timelineState.clips.length") == 0
            page.once("dialog", lambda dialog: dialog.accept())
            page.evaluate("(payload) => applyProjectPayload(payload)", downloaded)
            page.wait_for_timeout(700)
            restored = page.evaluate("""() => ({
                clips: timelineState.clips.length,
                lanes: timelineState.clips.filter(c => c.type === 'audio').map(c => c.audioTrack),
                assets: timelineState.assets.length,
                rows: document.querySelectorAll('.et-row.audio-row').length
            })""")
            print("restored:", restored)
            assert restored["clips"] == saved_clips and restored["assets"] == 3 and restored["rows"] == 3
            assert "A2" in restored["lanes"]

            # Open through the file picker round trip.
            page.evaluate("""() => {
                timelineState.clips = [];
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")
            project_file = tmp / "roundtrip.ccproj.json"
            project_file.write_text(json.dumps(downloaded), encoding="utf-8")
            page.once("dialog", lambda dialog: dialog.accept())
            page.set_input_files("#projectFileInput", str(project_file))
            page.wait_for_timeout(900)
            assert page.evaluate("timelineState.clips.length") == saved_clips
            assert page.evaluate("timelineState.assets.length") == 3

            OUT = ROOT / "output" / "playwright"
            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUT / "typed-lanes-project.png"))
            browser.close()
            assert not errors, errors
            print("FRAME + TYPED LANES + PROJECT FILE: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
