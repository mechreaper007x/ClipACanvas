"""Voice Studio live check: StyleTTS2 local runtime generate -> insert on A1."""
import sys
import time
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

        options = page.evaluate("""() => Array.from(document.querySelectorAll('#voiceProvider option'))
            .map(o => ({ id: o.value, disabled: o.disabled }))""")
        print("providers:", options)
        style = next((item for item in options if item["id"] == "styletts2"), None)
        assert style and not style["disabled"], options

        page.select_option("#voiceProvider", "styletts2")
        page.wait_for_function("() => document.getElementById('voiceBadge').textContent.includes('LOCAL')", timeout=15000)
        badge = page.text_content("#voiceBadge")
        consent = page.text_content("#voiceConsent")
        print("badge:", badge)
        print("consent:", consent)
        assert "READY" in badge, badge

        script = "Every stone on this road remembers a different century."
        page.fill("#voiceScript", script)
        page.select_option("#voiceTarget", "A1")
        started = time.perf_counter()
        page.click("#voiceGenerate")
        page.wait_for_function("() => !document.getElementById('voiceResult').hidden", timeout=240000)
        elapsed = time.perf_counter() - started
        page.wait_for_timeout(700)
        meta = page.text_content("#voiceResultMeta")
        status = page.text_content("#voiceStatus")
        audio_src = page.evaluate("() => document.getElementById('voiceAudio').src")
        probe = page.evaluate("""async () => {
            const url = document.getElementById('voiceAudio').src;
            const response = await fetch(url);
            return { ok: response.ok, bytes: (await response.arrayBuffer()).byteLength };
        }""")
        print("status:", status)
        print("meta:", meta)
        print("audio:", audio_src, probe)
        print("generate seconds:", round(elapsed, 1))
        assert probe["ok"] and probe["bytes"] > 50000, probe
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-styletts2.png"), full_page=True)

        page.click("#voiceInsert")
        page.wait_for_timeout(500)
        state = page.evaluate("""() => timelineState.clips.filter(clip => clip.type === 'audio')
            .map(clip => ({ name: clip.name, lane: clip.audioTrack, start: clip.start, duration: clip.duration }))""")
        print("audio clips:", state)
        assert state and state[0]["lane"] == "A1", state
        assert state[0]["duration"] > 2, state
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-styletts2-timeline.png"), full_page=True)
        assert not errors, errors
        browser.close()
finally:
    stop_server(server)

print("PASS voice studio styletts2")
