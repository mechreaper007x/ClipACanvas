"""Voiceover Studio in the real desktop WebView2: local speech, insert into A1."""
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

DEBUG_PORT = 9415
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)

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

            page.click("#tabVoice")
            page.wait_for_function("() => voiceStudioState.loaded", timeout=45000)
            assert page.evaluate("document.getElementById('voiceProvider').value") == "sapi"
            assert page.locator("#voiceSpeedField").is_visible()
            assert page.locator("#voiceStyleField").is_hidden()
            page.fill("#voiceScript", "WebView two voiceover check.")
            page.click("#voiceGenerate")
            page.wait_for_function(
                "() => { const el = document.getElementById('voiceStatus'); return el && /SPEECH READY|CACHED RESULT READY/.test(el.textContent); }",
                timeout=180000,
            )
            page.wait_for_timeout(400)
            result = page.evaluate("voiceStudioState.result")
            print("webview generated:", result["provider"], result["duration"], result["url"])
            assert result["url"].startswith("/media/")

            page.evaluate("setPlayhead(0)")
            page.select_option("#voiceTarget", "A1")
            page.click("#voiceInsert")
            page.wait_for_timeout(800)
            clip = page.evaluate("""() => {
                const c = timelineState.clips.find(item => item.type === 'audio');
                return c ? {start:c.start, audioTrack:c.audioTrack, url:c.mediaUrl} : null;
            }""")
            print("webview clip:", clip)
            assert clip and clip["audioTrack"] == "A1" and clip["url"] == result["url"]
            assert page.locator(".logic-audio-lane").first.inner_text() == "A1"
            assert page.locator("#miAudioMix").is_visible()
            page.click('.mi-audio-row[data-audio-track="A1"] .mi-lane-mute')
            page.wait_for_timeout(400)
            assert page.evaluate("timelineState.audioTracks[0].mute") is True
            plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(plan["audioClips"]) == 0
            page.click('.mi-audio-row[data-audio-track="A1"] .mi-lane-mute')
            page.wait_for_timeout(300)

            page.screenshot(path=str(OUT / "webview-voice-studio.png"))
            page.reload(wait_until="load")
            page.wait_for_timeout(1700)
            restored = page.evaluate("""() => ({
                assets: timelineState.assets.filter(a => a.kind === 'audio').length,
                audio: timelineState.clips.filter(c => c.type === 'audio').map(c => c.audioTrack)
            })""")
            print("webview restored:", restored)
            assert restored["assets"] >= 1 and "A1" in restored["audio"]
            browser.close()
            assert not errors, errors
            print("WEBVIEW2 VOICEOVER: OK")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
