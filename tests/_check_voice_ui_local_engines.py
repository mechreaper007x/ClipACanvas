"""Voice Studio check: local neural defaults, Kokoro and Piper generation."""
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="clipacanvas-voice-local-")
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
        page.evaluate("""async () => executeChatTool({
            name: 'insert_animation_code',
            args: { code: '<!doctype html><html><body style="margin:0;width:100%;height:100%;background:#f0ece0"><h1 style="position:absolute;left:8%;top:12%;font-family:Georgia,serif;font-size:7vh;color:#1b1a17">INDIA</h1></body></html>', duration: 2 }
        })""")
        page.click("#tabVoice")
        page.wait_for_function("() => document.querySelectorAll('#voiceProvider option').length > 0", timeout=60000)

        options = page.evaluate("""() => Array.from(document.querySelectorAll('#voiceProvider option'))
            .map(o => ({ id: o.value, disabled: o.disabled }))""")
        print("providers:", options)
        assert [item["id"] for item in options][:4] == ["styletts2", "kokoro", "piper", "sapi"], options
        selected = page.evaluate("() => document.getElementById('voiceProvider').value")
        print("default provider:", selected)
        assert selected == "styletts2", selected

        stamp = str(int(time.time()))[-6:]
        kokoro_text = f"Every stone on this road remembers a different century. Take {stamp}."
        piper_text = f"The city wakes before the sun does. Take {stamp}."

        def open_voice_panel():
            if not page.evaluate("() => { const el = document.getElementById('voiceProvider'); return !!el && el.getBoundingClientRect().width > 0; }"):
                page.click("#tabVoice")
                page.wait_for_function("() => document.getElementById('voiceProvider').getBoundingClientRect().width > 0", timeout=15000)

        def advance_playhead():
            page.evaluate("""() => {
                const end = Math.max(0, ...timelineState.clips
                    .filter(clip => clip.type === 'audio')
                    .map(clip => Number(clip.start) + Number(clip.duration)));
                setPlayhead(end + 0.25);
            }""")
            page.wait_for_timeout(200)

        def generate(provider, voice, script):
            open_voice_panel()
            page.select_option("#voiceProvider", provider)
            page.wait_for_function("() => !document.getElementById('voiceGenerate').disabled", timeout=15000)
            page.select_option("#voiceVoice", voice)
            page.fill("#voiceScript", script)
            started = time.perf_counter()
            previous_src = page.evaluate("() => document.getElementById('voiceAudio').src")
            page.click("#voiceGenerate")
            page.wait_for_function(
                "(prev) => { const audio = document.getElementById('voiceAudio'); return audio.src !== prev && audio.src.length > 0 && !document.getElementById('voiceResult').hidden; }",
                arg=previous_src, timeout=180000)
            page.wait_for_timeout(500)
            meta = page.text_content("#voiceResultMeta")
            probe = page.evaluate("""async () => {
                const response = await fetch(document.getElementById('voiceAudio').src);
                return { ok: response.ok, bytes: (await response.arrayBuffer()).byteLength };
            }""")
            elapsed = time.perf_counter() - started
            print(f"{provider}: {meta} | {probe} | {elapsed:.1f}s")
            assert probe["ok"] and probe["bytes"] > 40000, probe
            return meta

        open_voice_panel()
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-local-engines-panel.png"), full_page=True)
        kokoro_meta = generate("kokoro", "af_heart", kokoro_text)
        assert "Kokoro" in kokoro_meta and "Heart" in kokoro_meta, kokoro_meta
        open_voice_panel()
        page.click("#voiceInsert")
        page.wait_for_timeout(400)
        advance_playhead()

        piper_meta = generate("piper", "en_US-lessac-medium", piper_text)
        assert "Piper" in piper_meta and "Lessac" in piper_meta, piper_meta
        open_voice_panel()
        page.click("#voiceInsert")
        page.wait_for_timeout(400)
        advance_playhead()

        hindi_meta = generate("kokoro", "hf_alpha", "भारत एक तस्वीर नहीं है।")
        assert "Kokoro" in hindi_meta, hindi_meta
        open_voice_panel()
        page.click("#voiceInsert")
        page.wait_for_timeout(400)

        page.evaluate("""() => {
            setPlayhead(1.0);
            const audio = timelineState.clips.find(clip => clip.type === 'audio');
            if (audio) projectOps.selectClip(audio.id);
        }""")
        page.wait_for_timeout(900)
        preview = page.evaluate("""() => ({
            monitorScene: Boolean(document.querySelector('#liveFrame')?.dataset.previewClip) || previewCompositeState.active,
            badge: Boolean(document.querySelector('#liveFrame')?.contentDocument?.querySelector('.cc-audio-badge')),
            compositeLayers: previewCompositeState.count
        })""")
        print("monitor after audio selection:", preview)
        assert not preview["badge"], preview
        assert preview["monitorScene"], preview

        state = page.evaluate("""() => timelineState.clips.filter(clip => clip.type === 'audio')
            .map(clip => ({ name: clip.name, lane: clip.audioTrack, duration: clip.duration, start: clip.start }))""")
        print("audio clips:", state)
        assert len(state) == 3 and all(clip["lane"] == "A1" for clip in state), state
        overlap = page.evaluate("""() => {
            const clips = timelineState.clips.filter(clip => clip.type === 'audio' && clip.audioTrack === 'A1')
                .sort((a, b) => a.start - b.start);
            return clips.some((clip, index) => index > 0 && clip.start < clips[index - 1].start + clips[index - 1].duration - 1e-6);
        }""")
        print("A1 overlap:", overlap)
        assert not overlap, state
        assert not errors, errors
        page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-local-engines.png"), full_page=True)
        browser.close()
finally:
    stop_server(server)

print("PASS voice studio local engines")
