"""The program monitor must play timeline audio lanes, not only the export."""
import base64
import io
import math
import sys
import tempfile
import wave
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server


def make_wav(seconds=3.0, rate=22050, freq=440.0):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        frames = bytearray()
        for index in range(int(seconds * rate)):
            sample = int(12000 * math.sin(2 * math.pi * freq * index / rate))
            frames += sample.to_bytes(2, "little", signed=True)
        handle.writeframes(bytes(frames))
    return buffer.getvalue()


WAV_B64 = base64.b64encode(make_wav()).decode("ascii")
SCENE = """<!doctype html><html><head><style>
html,body{margin:0;background:#111}body:after{content:"";position:absolute;inset:0;background:radial-gradient(#333,#111)}
</style></head><body></body></html>"""

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)
        page.evaluate("() => { setResolutionValue('640x360'); setFrameRange(0, 3); }")
        page.evaluate(
            """async (code) => {
                await executeChatTool({ name: 'insert_animation_code', args: { code, duration: 3 } });
            }""",
            SCENE,
        )
        inserted = page.evaluate(
            """async (b64) => {
                const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
                const file = new File([bytes], 'tone.wav', { type: 'audio/wav' });
                const assets = await importMediaFiles([file]);
                const asset = assets.find(a => a.kind === 'audio');
                if (!asset) return { ok: false, error: 'no audio asset' };
                const placed = projectOps.insertAsset(asset.id, { at: 0, audioTrack: 'A1' });
                return { ok: placed.ok, assetId: asset.id, clipId: placed.clipId, duration: placed.clip && placed.clip.duration };
            }""",
            WAV_B64,
        )
        print("inserted:", inserted)
        assert inserted["ok"], inserted
        assert inserted["duration"] >= 2.5, inserted

        page.evaluate("() => { setPlayhead(0, { preview: true }); togglePlayback(); }")
        page.wait_for_timeout(800)
        playing = page.evaluate(
            """() => {
                const entries = Array.from(previewAudioTransport.elements.values());
                return {
                    count: entries.length,
                    paused: entries.map(entry => entry.el.paused),
                    times: entries.map(entry => Number(entry.el.currentTime || 0)),
                    playhead: timelineState.playhead
                };
            }"""
        )
        print("transport:", playing)
        assert playing["count"] >= 1, playing
        assert any(not paused for paused in playing["paused"]), playing
        assert max(playing["times"]) > 0.25, playing

        page.evaluate("() => { if (playbackState.playing) togglePlayback(); }")
        page.wait_for_timeout(200)
        stopped = page.evaluate("() => previewAudioTransport.elements.size")
        assert stopped == 0, stopped

        page.evaluate("() => projectOps.setAudioTrackMix('A1', { mute: true })")
        page.evaluate("() => { setPlayhead(0, { preview: true }); togglePlayback(); }")
        page.wait_for_timeout(500)
        muted = page.evaluate("() => previewAudioTransport.elements.size")
        page.evaluate("() => { if (playbackState.playing) togglePlayback(); projectOps.setAudioTrackMix('A1', { mute: false }); }")
        print("muted lane elements:", muted)
        assert muted == 0, muted
        assert not errors, errors
        browser.close()
finally:
    stop_server(server)

print("PASS preview audio transport")
