"""Voiceover Studio: local speech, cache, insertion, A1-A3 mix, export gain."""
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
    tone = tmp / "music.mp3"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=330:duration=3",
                    "-c:a", "libmp3lame", str(tone)], capture_output=True, check=True)

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

            page.click("#tabVoice")
            page.wait_for_function("() => voiceStudioState.loaded", timeout=45000)
            tab_overflow = page.evaluate("() => { const el = document.querySelector('.right-tabs'); return el.scrollWidth - el.clientWidth; }")
            print("right tab overflow @1664:", tab_overflow)
            assert tab_overflow <= 0, tab_overflow
            options = page.evaluate("Array.from(document.querySelectorAll('#voiceProvider option')).map(o => ({id:o.value,disabled:o.disabled,text:o.textContent}))")
            print("providers:", options)
            assert any(item["id"] == "sapi" and not item["disabled"] for item in options), options
            assert any(item["id"] == "gemini" and item["disabled"] for item in options), options
            assert any(item["id"] == "mistral" and item["disabled"] for item in options), options
            assert page.evaluate("document.getElementById('voiceProvider').value") == "sapi"
            assert page.locator("#voiceSpeedField").is_visible()
            assert not page.locator("#voiceStyleField").is_visible()
            print("local consent:", page.locator("#voiceConsent").inner_text()[:80])

            script = "Clip A Canvas narration test. The transition engine renders deterministic frames."
            page.fill("#voiceScript", script)
            page.wait_for_timeout(200)
            page.evaluate("voiceStudioState.busy = false")
            page.click("#voiceGenerate")
            page.wait_for_function(
                "() => { const el = document.getElementById('voiceStatus'); return el && /SPEECH READY|CACHED RESULT READY/.test(el.textContent); }",
                timeout=180000,
            )
            page.wait_for_timeout(500)
            result = page.evaluate("voiceStudioState.result")
            print("generated:", {key: result.get(key) for key in ("provider", "voice", "duration", "sampleRate", "cached", "url")})
            assert result["provider"] == "sapi" and result["url"].startswith("/media/")
            assert 0.5 < result["duration"] < 30
            assert page.locator("#voiceResult").is_visible()
            assert page.evaluate("document.getElementById('voiceAudio').getAttribute('src')") == result["url"]
            assets = page.evaluate("timelineState.assets.map(a => ({kind:a.kind, url:a.url, duration:a.duration}))")
            assert len(assets) == 1 and assets[0]["kind"] == "audio", assets
            assert assets[0]["url"] == result["url"]
            first_url = result["url"]

            # Cached second run: same URL, no duplicate asset.
            page.click("#voiceGenerate")
            page.wait_for_function("() => document.getElementById('voiceStatus').textContent.includes('CACHED')", timeout=60000)
            page.wait_for_timeout(300)
            again = page.evaluate("voiceStudioState.result")
            assert again["cached"] is True and again["url"] == first_url
            assert page.evaluate("timelineState.assets.length") == 1
            print("cache:", again["cached"], again["url"])

            # Insert into A1 at the playhead.
            page.evaluate("setPlayhead(0)")
            page.select_option("#voiceTarget", "A1")
            page.click("#voiceInsert")
            page.wait_for_timeout(700)
            clip = page.evaluate("""() => {
                const c = timelineState.clips.find(item => item.type === 'audio');
                return c ? {id:c.id, start:c.start, duration:c.duration, audioTrack:c.audioTrack, name:c.name, track:c.track} : null;
            }""")
            print("inserted clip:", clip)
            assert clip and clip["audioTrack"] == "A1" and abs(clip["start"]) < 0.05
            assert page.evaluate("document.getElementById('voiceStatus').textContent").startswith("INSERTED A1")
            assert page.locator(".logic-audio-lane").first.inner_text() == "A1"
            plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(plan["audioClips"]) == 1 and abs(plan["audioClips"][0]["volume"] - 1) < 0.001, plan
            print("plan audio:", plan["audioClips"])

            # Export the voiceover and probe real audio.
            page.evaluate("setResolutionValue('320x180')")
            page.click("#tabRecipe")
            page.wait_for_timeout(250)
            page.select_option("#frameRate", "24")
            duration = float(clip["duration"])
            page.evaluate(f"setFrameRange(0, {min(4.0, duration)})")
            page.wait_for_timeout(300)
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)

            def fetch_result(name):
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
                path = tmp / name
                path.write_bytes(base64.b64decode(payload))
                return path

            voice_export = fetch_result("voiceover.mp4")
            (OUT / "voiceover-export.mp4").write_bytes(voice_export.read_bytes())
            page.evaluate("document.getElementById('dl-panel')?.remove()")
            peak_full = max_volume(voice_export, 0.05, min(2.5, duration - 0.1))
            print("voiceover peak:", peak_full)
            assert peak_full > -40, peak_full

            # Lane assignment, mute, solo and volume are real mix controls.
            page.click("#tabInspector")
            page.wait_for_timeout(400)
            assert page.locator("#miAudioTrackField").is_visible()
            assert page.locator("#miAudioMix").is_visible()
            page.select_option("#miAudioTrack", "A2")
            page.wait_for_timeout(500)
            assert page.evaluate(f"timelineState.clips.find(c=>c.id==='{clip['id']}').audioTrack") == "A2"
            page.click('.mi-audio-row[data-audio-track="A2"] .mi-lane-mute')
            page.wait_for_timeout(400)
            assert page.evaluate("timelineState.audioTracks.find(t=>t.id==='A2').mute") is True
            muted_plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(muted_plan["audioClips"]) == 0, muted_plan
            page.click('.mi-audio-row[data-audio-track="A2"] .mi-lane-mute')
            page.wait_for_timeout(300)
            page.evaluate("projectOps.setAudioTrackMix('A2', { volume: 0.5 })")
            page.wait_for_timeout(300)
            half_plan = page.evaluate("buildTimelineRenderPlan()")
            assert abs(half_plan["audioClips"][0]["volume"] - 0.5) < 0.001, half_plan
            page.click("#tabRecipe")
            page.wait_for_timeout(200)
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
            half_export = fetch_result("voiceover-half.mp4")
            (OUT / "voiceover-half.mp4").write_bytes(half_export.read_bytes())
            page.evaluate("document.getElementById('dl-panel')?.remove()")
            peak_half = max_volume(half_export, 0.05, min(2.5, duration - 0.1))
            print("half-volume peak:", peak_half)
            assert peak_half <= peak_full - 4, (peak_full, peak_half)

            # A second clip on A3; soloing A3 silences the A2 voiceover.
            page.set_input_files("#mediaInput", str(tone))
            page.wait_for_function("() => timelineState.assets.length === 2", timeout=30000)
            page.wait_for_timeout(600)
            tone_id = page.evaluate("timelineState.assets.find(a=>a.kind==='audio' && a.url.endsWith('.mp3')).id")
            music = page.evaluate(f"""() => projectOps.insertAsset('{tone_id}', {{track: 0, at: 0, audioTrack: 'A3'}})""")
            assert music["ok"], music
            page.evaluate("projectOps.setAudioTrackMix('A3', { solo: true })")
            page.wait_for_timeout(400)
            solo_plan = page.evaluate("buildTimelineRenderPlan()")
            print("solo plan:", solo_plan["audioClips"])
            assert len(solo_plan["audioClips"]) == 1, solo_plan
            assert page.evaluate("timelineState.audioTracks.find(t=>t.id==='A3').solo") is True

            # Persistence of mix + generated asset + lane.
            page.reload(wait_until="load")
            page.wait_for_timeout(1800)
            restored = page.evaluate("""() => ({
                assets: timelineState.assets.length,
                tracks: timelineState.audioTracks,
                audio: timelineState.clips.filter(c => c.type === 'audio').map(c => ({lane:c.audioTrack, url:c.mediaUrl}))
            })""")
            print("restored:", restored["assets"], restored["tracks"], restored["audio"])
            assert restored["assets"] >= 2
            assert any(track["id"] == "A3" and track["solo"] for track in restored["tracks"])
            assert any(c["url"] == first_url for c in restored["audio"])
            page.click("#tabVoice")
            page.wait_for_timeout(800)
            assert page.evaluate("document.getElementById('voiceScript').value") == script
            assert page.locator("#voiceResult").is_hidden()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.wait_for_timeout(500)
            narrow_overflow = page.evaluate("() => { const el = document.querySelector('.right-tabs'); return el.scrollWidth - el.clientWidth; }")
            print("right tab overflow @1280:", narrow_overflow)
            assert narrow_overflow <= 0, narrow_overflow
            page.screenshot(path=str(OUT / "voice-studio.png"))

            browser.close()
            assert not errors, errors
            print("VOICEOVER STUDIO: OK")
    finally:
        server.shutdown()
