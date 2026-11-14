"""Local engine probes persist to disk and the Voice panel never starts blank."""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-voice-")

import serve
from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

key = f"VoiceProbeTest|{sys.executable}"
ok, reason, device = serve._local_probe("VoiceProbeTest", sys.executable, "print('device=cpu')")
print("probe:", ok, reason, device)
assert ok and device == "cpu", (ok, reason, device)
cache_path = Path(os.environ["CLIPACANVAS_KEYS_DIR"]) / serve._PROBE_CACHE_FILE
cached = json.loads(cache_path.read_text(encoding="utf-8"))
assert key in cached and cached[key]["ok"] is True, cached

serve._LOCAL_PROBES.clear()
started = time.perf_counter()
ok, reason, device = serve._local_probe("VoiceProbeTest", sys.executable, "raise SystemExit(3)")
elapsed = time.perf_counter() - started
print("disk-cached probe:", ok, device, f"{elapsed * 1000:.0f}ms")
assert ok and device == "cpu", (ok, reason, device)
assert elapsed < 0.5, elapsed

bad_ok, bad_reason, _ = serve._local_probe("VoiceProbeBad", sys.executable, "raise SystemExit(3)")
print("fresh failing probe:", bad_ok, bad_reason[:80])
assert bad_ok is False and bad_reason

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_function("() => typeof voiceStudioState === 'object'", timeout=30000)
        live = page.evaluate("""async () => {
            await ensureVoiceStudio(true);
            return {
                fetched: voiceStudioState.fetched,
                providers: voiceStudioState.providers.map(p => p.id),
                options: [...document.getElementById('voiceProvider').options].map(o => o.textContent),
                selected: document.getElementById('voiceProvider').value,
                cached: JSON.parse(localStorage.getItem('clipacanvas.voiceProviders.v5') || 'null')?.providers?.length || 0
            };
        }""")
        print("live registry:", live)
        assert live["fetched"] and len(live["providers"]) >= 7, live
        assert "zonos" in live["providers"], live
        assert "edge" not in live["providers"], live
        assert live["cached"] >= 7, live

        hydrated = page.evaluate("""() => {
            const fake = {
                id: 'kokoro', label: 'Kokoro (local neural)', kind: 'local', available: true,
                reason: '', requiresKey: '', terms: 'Runs locally.',
                models: [{ id: '82m', label: 'Kokoro 82M' }],
                voices: [{ id: 'af_heart', label: 'Heart', language: 'en-US' }],
                formats: ['wav'], supports: { speed: true, style: false }
            };
            voiceStudioState.providers = [];
            voiceStudioState.loaded = false;
            voiceStudioState.fetched = false;
            localStorage.setItem('clipacanvas.voiceProviders.v5', JSON.stringify({ savedAt: Date.now(), providers: [fake] }));
            hydrateVoiceProviderCache();
            populateVoiceProviders();
            return {
                options: [...document.getElementById('voiceProvider').options].map(o => o.textContent),
                selected: document.getElementById('voiceProvider').value,
                voices: [...document.getElementById('voiceVoice').options].map(o => o.textContent),
                generateDisabled: document.getElementById('voiceGenerate').disabled
            };
        }""")
        print("hydrated:", hydrated)
        assert hydrated["options"] == ["Kokoro (local neural)"], hydrated
        assert hydrated["selected"] == "kokoro", hydrated
        assert hydrated["voices"] and "Heart" in hydrated["voices"][0], hydrated
        assert hydrated["generateDisabled"] is False, hydrated

        loading = page.evaluate("""() => {
            voiceStudioState.providers = [];
            voiceStudioState.loaded = false;
            voiceStudioState.fetched = false;
            renderVoiceProvidersLoading();
            return {
                options: [...document.getElementById('voiceProvider').options].map(o => o.textContent),
                generateDisabled: document.getElementById('voiceGenerate').disabled
            };
        }""")
        print("loading state:", loading)
        assert loading["options"] == ["CHECKING ENGINES…"], loading
        assert loading["generateDisabled"] is True, loading

        page.evaluate("() => ensureVoiceStudio(true)")
        page.wait_for_function("() => voiceStudioState.fetched === true", timeout=60000)
        page.click("#tabVoice")
        page.wait_for_function("() => document.getElementById('voiceProvider').getBoundingClientRect().width > 0", timeout=15000)
        page.wait_for_timeout(400)
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-providers-instant.png"))
        assert not errors, errors
        browser.close()
finally:
    stop_server(server)
print("PASS voice provider cache")
