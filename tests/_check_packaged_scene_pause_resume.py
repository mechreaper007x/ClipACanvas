"""Packaged exe: a video inside a code scene keeps playing after pause + resume."""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import resolve_ffmpeg_exe

DEBUG_PORT = 9434
EXE = ROOT / "dist" / "ClipACanvas.exe"

assert EXE.exists(), "build dist/ClipACanvas.exe first"
ffmpeg = resolve_ffmpeg_exe()

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    (appdata / "media").mkdir(parents=True)
    media_name = "media-0123456789abcdef0123.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00c040:s=320x180:rate=24",
         "-t", "6", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(appdata / "media" / media_name)],
        capture_output=True, check=True,
    )
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(appdata)
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["APPDATA"] = str(tmp / "appdata-webview")
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    log_path = tmp / "packaged.log"
    log = open(log_path, "wb")
    proc = subprocess.Popen([str(EXE)], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(360):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("packaged app did not expose the CDP port")
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
            page = None
            for _ in range(120):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "packaged page not found"
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.wait_for_function("() => typeof timelineState !== 'undefined'", timeout=60000)
            page.wait_for_selector("#homeNew", timeout=30000)
            page.click("#homeNew")
            page.wait_for_selector("#homeDialogInput", timeout=15000)
            page.fill("#homeDialogInput", "SCENE RESUME SPRINT")
            page.click("#homeDialogConfirm")
            page.wait_for_function("() => !projectHomeVisible && document.querySelectorAll('.et-row').length > 0", timeout=60000)
            page.wait_for_timeout(800)

            page.evaluate("""async (mediaName) => {
              const url = '/media/' + mediaName;
              timelineState.clips = [{
                id: 'box-scene-video', name: 'SCENE 01', type: 'code', track: 0,
                start: 0, duration: 5.8, explicitDuration: true,
                code: '<!doctype html><html><head><style>html,body{margin:0;width:100%;height:100%;background:#000;overflow:hidden}</style></head><body><video class="cc-scene-media" src="' + url + '" muted playsinline autoplay loop style="position:fixed;inset:0;width:100%;height:100%;object-fit:contain"></video></body></html>'
              }];
              timelineState.layers = 1;
              timelineState.activeId = 'box-scene-video';
              timelineState.playhead = 0;
              saveTimelineState(true);
              applyActiveClipToEditor({ preview: true });
              renderLogicBoxes();
              updateStageTimeline();
            }""", media_name)
            page.wait_for_timeout(1200)

            def video_state():
                for frame in page.frames:
                    if frame == page.main_frame:
                        continue
                    try:
                        if frame.locator("video.cc-scene-media").count():
                            return frame.evaluate("""() => {
                                const v = document.querySelector('video.cc-scene-media');
                                return { paused: v.paused, t: v.currentTime, ready: v.readyState };
                            }""")
                    except Exception:
                        continue
                return None

            for _ in range(60):
                initial = video_state()
                if initial and initial["ready"] >= 1:
                    break
                page.wait_for_timeout(500)
            print("scene initial:", initial)
            assert initial and initial["ready"] >= 1, initial
            assert initial["paused"], initial

            page.click("#playToggle")
            page.wait_for_timeout(900)
            playing = video_state()
            print("scene playing:", playing)
            assert playing and not playing["paused"], playing
            assert playing["t"] > 0.3, playing

            page.click("#playToggle")
            page.wait_for_timeout(500)
            paused_a = video_state()
            page.wait_for_timeout(500)
            paused_b = video_state()
            print("scene paused:", paused_a, paused_b)
            assert paused_a and paused_b, (paused_a, paused_b)
            assert paused_a["paused"] and paused_b["paused"], (paused_a, paused_b)
            assert abs(paused_b["t"] - paused_a["t"]) < 0.15, (paused_a, paused_b)

            page.click("#playToggle")
            page.wait_for_timeout(1200)
            resumed = video_state()
            head = page.evaluate("timelineState.playhead")
            print("scene resumed:", resumed, "playhead:", head)
            assert resumed and not resumed["paused"], resumed
            assert resumed["t"] > paused_b["t"] + 0.4, (paused_b, resumed)
            assert head > 1.2, head
            assert not errors, errors
            browser.close()
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()

print("PASS packaged scene pause + resume")
