"""Typed audio lanes, frame stepping and project payloads in WebView2."""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright
from serve import resolve_ffmpeg_exe

DEBUG_PORT = 9418
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
ffmpeg = resolve_ffmpeg_exe()

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    video = tmp / "motion.mp4"
    audio = tmp / "music.mp3"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
                    "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    proc = subprocess.Popen([sys.executable, str(ROOT / "desktop_app.py")],
                            cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
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
            page.wait_for_function("() => typeof timelineState !== 'undefined' && typeof projectOps === 'object'", timeout=45000)
            page.wait_for_timeout(800)
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            print("webview:", page.evaluate("navigator.userAgent"))

            page.set_input_files("#mediaInput", [str(video), str(audio)])
            page.wait_for_function(
                "() => timelineState.assets.length === 2 && timelineState.assets.every(a => a.analysis?.technical)",
                timeout=60000,
            )
            asset_ids = page.evaluate("() => Object.fromEntries(timelineState.assets.map(a => [a.kind, a.id]))")
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

            video_clip = ops("insertAsset", asset_ids["video"], {"track": 0, "at": 0})
            audio_clip = ops("insertAsset", asset_ids["audio"], {"track": 0, "at": 0.5, "audioTrack": "A2"})
            assert video_clip["ok"] and audio_clip["ok"], (video_clip, audio_clip)
            audio_id = audio_clip["clipId"]
            page.wait_for_timeout(500)

            assert page.locator(".et-row.audio-row").count() == 3
            assert page.locator(f'.et-lane[data-audio-track="A2"] .logic-box[data-id="{audio_id}"]').count() == 1
            assert page.locator(f'.et-lane[data-track="0"] .logic-box[data-id="{audio_id}"]').count() == 0

            box = page.locator(f'.et-lane[data-audio-track="A2"] .logic-box[data-id="{audio_id}"]').bounding_box()
            a1 = page.locator('.et-row[data-audio-row="A1"] .et-lane').bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 + 4, a1["y"] + a1["height"] / 2, steps=12)
            page.mouse.up()
            page.wait_for_timeout(500)
            lane = page.evaluate("([a]) => timelineState.clips.find(c => c.id === a).audioTrack", [audio_id])
            print("webview lane:", lane)
            assert lane == "A1"
            assert page.locator(f'.et-lane[data-audio-track="A1"] .logic-box[data-id="{audio_id}"]').count() == 1

            page.evaluate("setPlayhead(0); document.activeElement?.blur()")
            page.wait_for_timeout(200)
            page.keyboard.press("ArrowRight")
            step = page.evaluate("timelineState.playhead")
            print("webview frame:", step)
            assert abs(step - 1 / 60) < 1e-4
            assert page.locator("#monitorTime").inner_text().endswith(":01")

            # Desktop project-file bridge is exposed; payload applies in-page.
            bridge = page.evaluate("() => ({save: typeof window.pywebview?.api?.save_project_file, open: typeof window.pywebview?.api?.open_project_file})")
            print("webview bridge:", bridge)
            assert bridge["save"] == "function" and bridge["open"] == "function"
            payload = page.evaluate("buildProjectFilePayload()")
            saved_clips = len(payload["timeline"]["clips"])
            page.once("dialog", lambda dialog: dialog.accept())
            page.evaluate("""() => {
                timelineState.clips = [];
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")
            page.evaluate("(payload) => applyProjectPayload(payload)", payload)
            page.wait_for_timeout(700)
            restored = page.evaluate("""() => ({
                clips: timelineState.clips.length,
                lanes: timelineState.clips.filter(c => c.type === 'audio').map(c => c.audioTrack),
                rows: document.querySelectorAll('.et-row.audio-row').length
            })""")
            print("webview restored:", restored)
            assert restored["clips"] == saved_clips and restored["rows"] == 3
            assert "A1" in restored["lanes"]

            page.screenshot(path=str(OUT / "webview-typed-lanes.png"))
            browser.close()
            assert not errors, errors
            print("WEBVIEW2 FRAME + LANES + PROJECT: OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
