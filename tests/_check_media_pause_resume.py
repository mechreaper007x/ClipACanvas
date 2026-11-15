"""Program Monitor: a video keeps playing after pause and resume."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    video = tmp / "pause-resume.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00c040:s=320x180:rate=24",
         "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, check=True,
    )
    server, _thread = start_server()
    base = server_url(server)
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)

            page.set_input_files("#mediaInput", str(video))
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=60000)
            page.wait_for_timeout(500)
            page.evaluate("""() => {
                setResolutionValue('540x960');
                timelineState.clips = [];
                timelineState.layers = 1;
                const asset = timelineState.assets[0];
                insertAssetClip(asset, { track: 0, at: 0, duration: 5.8, mode: 'overwrite' });
                setPlayhead(0);
            }""")
            page.wait_for_timeout(900)

            def video_state():
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        if frame.locator("video.cc-media").count():
                            return frame.evaluate("""() => {
                                const v = document.querySelector('video.cc-media');
                                return { paused: v.paused, t: v.currentTime, ready: v.readyState };
                            }""")
                    except Exception:
                        continue
                return None

            initial = video_state()
            print("initial:", initial)
            assert initial and initial["ready"] >= 1, initial

            page.click("#playToggle")
            page.wait_for_timeout(900)
            playing = video_state()
            print("playing:", playing)
            assert playing and not playing["paused"], playing
            assert playing["t"] > 0.35, playing

            page.click("#playToggle")
            page.wait_for_timeout(500)
            paused_a = video_state()
            page.wait_for_timeout(500)
            paused_b = video_state()
            print("paused:", paused_a, paused_b)
            assert paused_a and paused_b, (paused_a, paused_b)
            assert paused_a["paused"] and paused_b["paused"], (paused_a, paused_b)
            assert abs(paused_b["t"] - paused_a["t"]) < 0.15, (paused_a, paused_b)
            assert not page.evaluate("playbackState.playing")

            page.click("#playToggle")
            page.wait_for_timeout(1200)
            resumed = video_state()
            head = page.evaluate("timelineState.playhead")
            print("resumed:", resumed, "playhead:", head)
            assert resumed and not resumed["paused"], resumed
            assert resumed["t"] > paused_b["t"] + 0.4, (paused_b, resumed)
            assert head > 1.2, head

            page.evaluate("stopPlayback(false)")

            # The same check for a video embedded inside a code scene (the
            # user's Scene 01): the scene clock pauses and must resume it.
            page.evaluate("""() => {
                const asset = timelineState.assets[0];
                timelineState.clips = [{
                    id: 'box-video-scene', name: 'SCENE 01', type: 'code', track: 0,
                    start: 0, duration: 5.8, explicitDuration: true,
                    code: '<!doctype html><html><head><style>html,body{margin:0;width:100%;height:100%;background:#000;overflow:hidden}</style></head><body><video class="cc-scene-media" src="' + asset.url + '" muted playsinline autoplay loop style="position:fixed;inset:0;width:100%;height:100%;object-fit:contain"></video></body></html>'
                }];
                timelineState.layers = 1;
                timelineState.activeId = 'box-video-scene';
                timelineState.playhead = 0;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: true });
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(900)

            def scene_video_state():
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        if frame.locator("video").count():
                            return frame.evaluate("""() => {
                                const v = document.querySelector('video');
                                return { paused: v.paused, t: v.currentTime, ready: v.readyState };
                            }""")
                    except Exception:
                        continue
                return None

            scene_initial = scene_video_state()
            print("scene initial:", scene_initial)
            assert scene_initial and scene_initial["ready"] >= 1, scene_initial
            page.click("#playToggle")
            page.wait_for_timeout(800)
            scene_playing = scene_video_state()
            print("scene playing:", scene_playing)
            assert scene_playing and not scene_playing["paused"], scene_playing

            page.click("#playToggle")
            page.wait_for_timeout(500)
            scene_paused_a = scene_video_state()
            page.wait_for_timeout(500)
            scene_paused_b = scene_video_state()
            print("scene paused:", scene_paused_a, scene_paused_b)
            assert scene_paused_a and scene_paused_b, (scene_paused_a, scene_paused_b)
            assert scene_paused_a["paused"] and scene_paused_b["paused"], (scene_paused_a, scene_paused_b)
            assert abs(scene_paused_b["t"] - scene_paused_a["t"]) < 0.15, (scene_paused_a, scene_paused_b)

            page.click("#playToggle")
            page.wait_for_timeout(1200)
            scene_resumed = scene_video_state()
            print("scene resumed:", scene_resumed)
            assert scene_resumed and not scene_resumed["paused"], scene_resumed
            assert scene_resumed["t"] > scene_paused_b["t"] + 0.4, (scene_paused_b, scene_resumed)

            page.evaluate("stopPlayback(false)")
            browser.close()
            assert not errors, errors
            print("PAUSE + RESUME CHECK: OK")
    finally:
        stop_server(server)
