"""Asset semantics in the real desktop WebView2: local shots, consent gate, notes."""
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

DEBUG_PORT = 9416
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
ffmpeg = resolve_ffmpeg_exe()

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    video = tmp / "cuts.mp4"
    subprocess.run(
        [ffmpeg, "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24:duration=1",
         "-f", "lavfi", "-i", "smptebars=size=320x180:rate=24:duration=1",
         "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=1",
         "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0",
         "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, check=True,
    )
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

            page.set_input_files("#mediaInput", str(video))
            page.wait_for_function(
                "() => timelineState.assets.length === 1"
                " && timelineState.assets[0].analysis?.technical"
                " && (timelineState.assets[0].analysis.shots || []).length >= 3",
                timeout=60000,
            )
            asset = page.evaluate("""() => {
                const a = timelineState.assets[0];
                return {id: a.id, shots: a.analysis.shots};
            }""")
            print("webview shots:", [(shot["start"], shot["end"]) for shot in asset["shots"]])
            assert len(asset["shots"]) >= 3

            page.locator(f'.dock-bin[data-asset-id="{asset["id"]}"]').click()
            page.wait_for_timeout(400)
            assert page.locator("#miShots").is_visible()
            assert page.locator("#miShots img").count() >= 3
            assert "NOT ANALYZED" in page.locator("#miContentStatus").inner_text()
            frame = page.locator("#miShots img").first.get_attribute("src")
            status = page.evaluate("""async (url) => {
                const response = await fetch(url);
                return {ok: response.ok, type: response.headers.get('content-type'), size: (await response.blob()).size};
            }""", frame)
            print("webview keyframe:", status)
            assert status["ok"] and status["type"] == "image/jpeg" and status["size"] > 500

            page.fill("#miUserNote", "WebView shot strip check")
            page.click("#miUserNoteSave")
            page.wait_for_timeout(300)
            assert "USER NOTE" in page.locator("#miSemanticNote").inner_text()

            # No API key: consent UI never opens; the reason is visible.
            page.click("#miAnalyzeToggle")
            page.wait_for_function(
                "() => document.getElementById('miAnalyzeHint').textContent.includes('Gemini API key')",
                timeout=15000,
            )
            assert page.locator("#miConsentRow").is_hidden()

            page.screenshot(path=str(OUT / "webview-asset-semantics.png"))
            page.reload(wait_until="load")
            page.wait_for_timeout(1700)
            page.locator(f'.dock-bin[data-asset-id="{asset["id"]}"]').click()
            page.wait_for_timeout(400)
            restored = page.evaluate("""() => {
                const a = timelineState.assets[0];
                return {
                    shots: (a.analysis?.shots || []).length,
                    frames: document.querySelectorAll('#miShots img').length,
                    note: a.analysis?.user?.description || ''
                };
            }""")
            print("webview restored:", restored)
            assert restored["shots"] >= 3 and restored["frames"] >= 3
            assert "WebView shot strip check" in restored["note"]
            browser.close()
            assert not errors, errors
            print("WEBVIEW2 ASSET SEMANTICS: OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
