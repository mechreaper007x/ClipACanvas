"""End-to-end user journey: import media, create a scene, drag image/video/audio
onto the timeline, play, preview, export one continuous render and reload."""
import base64
import os
import re
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
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)


def probe_pixel(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-ss", str(seconds),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y},scale=2:2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    if len(out) < 3:
        raise AssertionError(f"no frame decoded at {seconds}s from {path.name}")
    return out[0], out[1], out[2]


def max_volume(path: Path, start: float, length: float) -> float:
    proc = subprocess.run(
        [ffmpeg, "-hide_banner", "-ss", str(start), "-t", str(length), "-i", str(path),
         "-vn", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"max_volume:\s*(-?[\d.]+) dB", proc.stderr)
    return float(match.group(1)) if match else -99.0


errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    image = tmp / "still.png"
    video = tmp / "motion.mp4"
    audio = tmp / "tone.mp3"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
                    "-frames:v", "1", str(image)], capture_output=True, check=True)
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
            page.wait_for_timeout(1500)

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

            # 1. Import all three media kinds.
            page.set_input_files("#mediaInput", [str(image), str(video), str(audio)])
            page.wait_for_function("() => timelineState.assets.length === 3", timeout=30000)
            page.wait_for_timeout(700)
            ids = page.evaluate("Object.fromEntries(timelineState.assets.map(a => [a.kind, a.id]))")
            assert set(ids) == {"image", "video", "audio"}, ids

            # 2. Create a scene from the toolbar and edit its code/duration.
            page.click("#boxAdd")
            page.wait_for_function("() => timelineState.clips.length === 1", timeout=10000)
            assert page.locator("#clipInspector").is_visible(), "code clip inspector did not open"
            assert page.locator("#ciName").inner_text() == "SCENE 01"
            page.evaluate("""() => {
                const editor = document.getElementById('codeInput');
                editor.value = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#00c040}</style></head><body></body></html>';
                syncActiveClipFromEditor(true);
                renderLogicBoxes();
                updateStageTimeline();
                previewClipCode(activeClip());
            }""")
            page.locator("#ciDuration").fill("4")
            page.locator("#ciDuration").press("Tab")
            page.wait_for_timeout(300)
            scene = page.evaluate("timelineState.clips.find(c => c.type === 'code')")
            assert abs(scene["duration"] - 4) < 0.01, scene
            assert scene["start"] == 0 and scene["track"] == 0, scene

            # 3. Four tracks, then drag each asset from the bin to its own track.
            for _ in range(3):
                page.click("#layerAdd")
                page.wait_for_timeout(120)
            assert page.evaluate("timelineState.layers") == 4

            def reveal(track):
                page.evaluate("""(track) => {
                    const host = document.getElementById('logicTracks');
                    const row = document.querySelector(`.et-row[data-track="${track}"]`);
                    if (!host || !row) return;
                    const hb = host.getBoundingClientRect();
                    const rb = row.getBoundingClientRect();
                    host.scrollTop = Math.max(0, host.scrollTop + rb.top - hb.top - 6);
                }""", track)
                page.wait_for_timeout(150)

            def drag_asset(kind, track, ratio):
                asset_id = ids[kind]
                card = page.locator(f'.dock-bin[data-asset-id="{asset_id}"]').bounding_box()
                lane = page.locator(f'.et-row[data-track="{track}"] .et-lane').bounding_box()
                x = lane["x"] + lane["width"] * ratio
                y = lane["y"] + lane["height"] / 2
                page.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
                page.mouse.down()
                page.mouse.move(card["x"] + card["width"] / 2 + 30, card["y"] - 20, steps=5)
                page.mouse.move(x, y, steps=16)
                page.mouse.move(x + 1, y)
                page.wait_for_timeout(220)
                hint = page.locator("#etDropHint").inner_text()
                page.mouse.up()
                page.wait_for_timeout(450)
                return hint

            reveal(1)
            assert "V2" in drag_asset("image", 1, 0.2)
            reveal(2)
            assert "V3" in drag_asset("video", 2, 0.5)
            reveal(3)
            assert "V4" in drag_asset("audio", 3, 0.05)

            placed = page.evaluate("timelineState.clips.map(c => ({type:c.type, track:c.track, start:c.start, duration:c.duration}))")
            print("placed clips:", placed)
            assert len(placed) == 4, placed
            image_clip = next(c for c in placed if c["type"] == "image")
            video_clip = next(c for c in placed if c["type"] == "video")
            audio_clip = next(c for c in placed if c["type"] == "audio")
            assert image_clip["track"] == 1 and abs(image_clip["start"] - 0.8) < 0.2, image_clip
            assert video_clip["track"] == 2 and abs(video_clip["start"] - 2.0) < 0.2, video_clip
            assert audio_clip["track"] == 3 and abs(audio_clip["start"] - 0.2) < 0.15, audio_clip
            assert abs(audio_clip["duration"] - 1.0) < 0.05, audio_clip

            # 4. Playback and composite preview at the overlay.
            page.evaluate("setPlayhead(1, { preview: true })")
            page.wait_for_timeout(500)
            assert abs(page.evaluate("timelineState.playhead") - 1) < 0.05
            srcdoc = page.evaluate("document.getElementById('liveFrame').srcdoc")
            assert "00c040" in srcdoc and "/media/" in srcdoc, srcdoc[:300]
            page.click("#playToggle")
            page.wait_for_timeout(700)
            advanced = page.evaluate("timelineState.playhead")
            page.click("#playToggle")
            page.wait_for_timeout(150)
            assert advanced > 1.05, advanced
            print("playback advanced:", advanced)
            page.evaluate("setPlayhead(1, { preview: true })")
            page.wait_for_timeout(300)
            page.screenshot(path=str(OUT / "e2e-workspace.png"))

            # 5. Export one continuous render of the whole composition.
            page.evaluate("setResolutionValue('540x960')")
            page.click("#tabRecipe")
            page.wait_for_timeout(250)
            page.select_option("#frameRate", "30")
            page.evaluate("setFrameRange(0, 4)")
            page.wait_for_timeout(300)
            plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(plan["clips"]) == 4, plan
            assert len(plan["audioClips"]) == 1, plan
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=240000,
            )
            page.wait_for_timeout(300)
            video_path = tmp / "e2e.mp4"
            payload = page.evaluate("""async () => {
                const response = await fetch(resultVideoUrl);
                const buffer = await response.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let text = '';
                const chunk = 0x8000;
                for (let i = 0; i < bytes.length; i += chunk) {
                    text += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                }
                return btoa(text);
            }""")
            video_path.write_bytes(base64.b64decode(payload))
            (OUT / "e2e-render.mp4").write_bytes(video_path.read_bytes())
            render_meta = page.evaluate("window.lastRenderMeta || {}")
            print("render meta:", render_meta)

            scene_only = probe_pixel(video_path, 0.2, 270, 40)
            still_over = probe_pixel(video_path, 1.0, 270, 480)
            scene_under = probe_pixel(video_path, 1.0, 270, 40)
            video_over = probe_pixel(video_path, 2.5, 270, 480)
            scene_under_video = probe_pixel(video_path, 2.5, 270, 40)
            tone = max_volume(video_path, 0.25, 0.9)
            print("pixels scene/still/still-corner/video/video-corner:", scene_only, still_over, scene_under, video_over, scene_under_video)
            print("audio max volume:", tone)
            assert scene_only[1] > 120 and scene_only[0] < 90, scene_only
            assert still_over[0] > 140 and still_over[1] < 100 and still_over[2] > 140, still_over
            assert scene_under[1] > 120 and scene_under[0] < 90, scene_under
            assert video_over[2] > 140 and video_over[0] < 90, video_over
            assert scene_under_video[1] > 120 and scene_under_video[0] < 90, scene_under_video
            assert tone > -30, tone

            # 6. Reload keeps the whole project.
            page.reload(wait_until="load")
            page.wait_for_timeout(1700)
            restored = page.evaluate("timelineState.clips.map(c => ({type:c.type, track:c.track}))")
            assert len(restored) == 4, restored
            assert {c["type"] for c in restored} == {"code", "image", "video", "audio"}, restored
            page.screenshot(path=str(OUT / "e2e-final.png"))

            browser.close()
            assert not errors, errors
            print("END-TO-END JOURNEY: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
