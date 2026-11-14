"""Voice Studio live check: Gemini TTS generate -> result -> insert on A1."""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)
        page.click("#tabVoice")
        page.wait_for_function("() => document.querySelectorAll('#voiceProvider option').length > 0", timeout=30000)
        providers = page.evaluate("() => Array.from(document.querySelectorAll('#voiceProvider option')).map(o => o.value)")
        print("providers:", providers)
        assert "gemini" in providers, providers

        page.select_option("#voiceProvider", "gemini")
        page.wait_for_function("() => document.querySelectorAll('#voiceVoice option').length > 10", timeout=15000)
        page.select_option("#voiceModel", "gemini-3.8-flash-tts")
        page.select_option("#voiceVoice", "Kore")
        page.fill("#voiceScript", "India is not one image. It is a thousand beginnings, moving at once.")
        page.fill("#voiceStyle", "warm, composed, cinematic")
        page.select_option("#voiceTarget", "A1")
        print("consent:", page.text_content("#voiceConsent"))

        page.click("#voiceGenerate")
        page.wait_for_function("() => !document.getElementById('voiceResult').hidden", timeout=180000)
        page.wait_for_timeout(700)
        meta = page.text_content("#voiceResultMeta")
        status = page.text_content("#voiceStatus")
        audio_src = page.evaluate("() => document.getElementById('voiceAudio').src")
        print("status:", status)
        print("meta:", meta)
        print("audio:", audio_src)
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-gemini.png"), full_page=True)

        page.click("#voiceInsert")
        page.wait_for_timeout(500)
        state = page.evaluate("""() => timelineState.clips.filter(clip => clip.type === 'audio')
            .map(clip => ({ name: clip.name, lane: clip.audioTrack, start: clip.start, duration: clip.duration }))""")
        print("audio clips:", state)
        assert state and state[0]["lane"] == "A1", state
        assert state[0]["duration"] > 3, state
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-gemini-timeline.png"), full_page=True)
        assert not errors, errors
        browser.close()
finally:
    stop_server(server)

print("PASS voice studio gemini")
