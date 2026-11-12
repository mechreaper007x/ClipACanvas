"""Transitions in the real desktop WebView2: dialog, preview engine, export."""
import base64
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
DEBUG_PORT = 9414
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
RED = '<!doctype html><html><body style="margin:0;background:#ff0000"></body></html>'
BLUE = '<!doctype html><html><body style="margin:0;background:#0000ff"></body></html>'


def probe_pixel(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-ss", str(seconds),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y},scale=2:2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    if len(out) < 3:
        raise AssertionError("no frame decoded")
    return out[0], out[1], out[2]


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
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

            ids = page.evaluate("""([red, blue]) => {
                timelineState.clips = [];
                timelineState.transitions = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                saveTimelineState(true);
                const a = projectOps.createComposition({name: 'RED', code: red, start: 0, duration: 2, track: 0});
                const b = projectOps.createComposition({name: 'BLUE', code: blue, start: 2, duration: 2, track: 0});
                projectOps.selectClip(a.clipId);
                return { a: a.clipId, b: b.clipId };
            }""", [RED, BLUE])

            # Add through the real dialog in the desktop shell.
            page.click("#transitionAdd")
            page.wait_for_timeout(300)
            assert page.locator("#transitionModal").is_visible()
            page.select_option("#trType", "zoom-blur")
            assert page.locator("#trIntensityField").is_visible()
            page.fill("#trDuration", "1")
            page.click("#trApply")
            page.wait_for_timeout(600)
            summary = page.evaluate("transitionSummaryForChat()")
            assert len(summary) == 1 and summary[0]["type"] == "zoom-blur", summary
            assert page.locator(".logic-transition").count() == 1
            assert abs(page.evaluate("timelineState.playhead") - 2.0) < 0.08
            print("webview transition:", summary[0]["type"], summary[0]["durationSeconds"])

            composite = page.evaluate("previewCompositeState")
            assert composite["active"] and composite["count"] == 2, composite
            frame = None
            for candidate in page.frames:
                try:
                    if candidate.evaluate("() => Boolean(window.__ccSetCompositeTime)"):
                        frame = candidate
                        break
                except Exception:
                    continue
            assert frame is not None, "composite engine missing in WebView2"
            layers = frame.evaluate("""() => Array.from(document.querySelectorAll('.cc-layer')).map(el => ({
                opacity: el.style.opacity, z: el.style.zIndex, vis: el.style.visibility
            }))""")
            print("webview layers:", layers)
            opacities = [layer["opacity"] for layer in layers]
            assert any(value and abs(float(value) - 0.5) < 0.02 for value in opacities), layers
            assert all(layer["vis"] == "visible" for layer in layers), layers
            page.screenshot(path=str(OUT / "webview-transition-dialog.png"))

            # Export a short window through the desktop UI.
            page.evaluate("setResolutionValue('320x180')")
            page.click("#tabRecipe")
            page.wait_for_timeout(250)
            page.select_option("#frameRate", "24")
            page.evaluate("setFrameRange(1.4, 2.6)")
            page.wait_for_timeout(250)
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
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
            video_path = tmp / "webview-transition.mp4"
            video_path.write_bytes(base64.b64decode(payload))
            (OUT / "webview-transition.mp4").write_bytes(video_path.read_bytes())
            start_px = probe_pixel(video_path, 0.02, 160, 90)
            mid_px = probe_pixel(video_path, 0.6, 160, 90)
            end_px = probe_pixel(video_path, 1.18, 160, 90)
            print("webview export pixels start/mid/end:", start_px, mid_px, end_px)
            assert start_px[0] > start_px[2] + 40, start_px
            assert end_px[2] > end_px[0] + 40, end_px
            assert mid_px[0] > 40 and mid_px[2] > 40, mid_px

            page.reload(wait_until="load")
            page.wait_for_timeout(1600)
            restored = page.evaluate("transitionSummaryForChat()")
            assert len(restored) == 1 and restored[0]["type"] == "zoom-blur", restored
            page.screenshot(path=str(OUT / "webview-transition-restored.png"))
            browser.close()
            assert not errors, errors
            print("WEBVIEW2 TRANSITIONS: OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
