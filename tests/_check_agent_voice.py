"""Agent voice pipeline: local TTS to A1, captions on an overlay track, mixed export."""
import base64
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

ffmpeg = resolve_ffmpeg_exe()
SCENE = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#f0ece0;overflow:hidden}
h1{position:absolute;left:8%;top:12%;font-family:Georgia,serif;font-size:7vh;color:#1b1a17;margin:0}
</style></head><body><h1>INDIA</h1></body></html>"""
VOICE_TEXT = "India is not one image. It is a thousand beginnings, moving at once."


def probe_pixel_at(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(path), "-frames:v", "1",
         "-vf", f"crop=6:6:{x}:{y},scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return out[0], out[1], out[2]


def mean_volume(path: Path, start: float, duration: float) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}", "-i", str(path),
         "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr)
    assert match, result.stderr[-800:]
    return float(match.group(1))


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    image = tmp / "still.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x1b4a2a:s=640x360:d=1",
         "-frames:v", "1", str(image)],
        capture_output=True, check=True,
    )
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
            page.evaluate("""() => {
                setResolutionValue('640x360');
                const fps = document.getElementById('frameRate');
                fps.value = '24'; fps.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
            page.set_input_files("#mediaInput", [str(image)])
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=60000)
            page.evaluate(
                """async (code) => {
                    await executeChatTool({ name: 'insert_animation_code', args: { code, duration: 6 } });
                }""",
                SCENE,
            )

            voice = page.evaluate(
                """async (text) => executeChatTool({
                    name: 'generate_voiceover',
                    args: { text, provider: 'sapi', lane: 'A1', start: 0, captions: true }
                })""",
                VOICE_TEXT,
            )
            print("voice:", {key: voice.get(key) for key in ("ok", "error", "lane", "duration", "captions", "provider", "voiceLabel")})
            assert voice.get("ok"), voice
            assert voice["duration"] and voice["duration"] > 1.5, voice
            assert voice["captions"] >= 1, voice
            assert voice["lane"] == "A1", voice

            state = page.evaluate("""() => ({
                clips: timelineState.clips.map(clip => ({ name: clip.name, type: clip.type, start: clip.start, duration: clip.duration, track: clip.track, audioTrack: clip.audioTrack || '' })),
                audioAssets: timelineState.assets.filter(asset => asset.kind === 'audio').length
            })""")
            print("clips:", state["clips"])
            audio = [clip for clip in state["clips"] if clip["type"] == "audio"]
            captions = [clip for clip in state["clips"] if clip["name"].startswith("CAPTION")]
            assert len(audio) == 1 and audio[0]["audioTrack"] == "A1", state["clips"]
            assert len(captions) >= 1, state["clips"]
            assert all(clip["track"] >= 1 for clip in captions), state["clips"]
            assert state["audioAssets"] == 1, state

            verified = page.evaluate("() => executeChatTool({ name: 'verify_timeline', args: {} })")
            print("verify:", verified.get("passed"), verified.get("problems"))
            assert verified.get("passed"), verified

            placed = page.evaluate("() => executeChatTool({ name: 'place_media', args: { query: 'still', track: 1, at: 3 } })")
            print("place_media:", {key: placed.get(key) for key in ("ok", "error", "kind", "track", "start")})
            assert placed.get("ok"), placed
            assert placed["kind"] == "image" and placed["track"] == 1, placed

            page.evaluate("() => setFrameRange(0, 6)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=300000,
            )
            page.wait_for_timeout(500)

            film = tmp / "voice-film.mp4"
            video_b64 = page.evaluate("""async () => {
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
            film.write_bytes(base64.b64decode(video_b64))
            print("film:", film.stat().st_size, "bytes")

            streams = subprocess.run([ffmpeg, "-hide_banner", "-i", str(film)],
                                     capture_output=True, text=True).stderr
            assert "Audio:" in streams, "voiceover missing from the export"

            level = mean_volume(film, 0.4, 1.2)
            print("narration mean volume:", level, "dB")
            assert level > -45, f"narration lane silent: {level} dB"

            caption_pixel = probe_pixel_at(film, 1.0, 320, 330)
            scene_pixel = probe_pixel_at(film, 1.0, 320, 60)
            print("caption pixel:", caption_pixel, "scene pixel:", scene_pixel)
            assert scene_pixel[0] > 200, scene_pixel
            assert sum(caption_pixel) < sum(scene_pixel) - 90, caption_pixel

            still_pixel = probe_pixel_at(film, 3.5, 320, 180)
            print("image layer pixel:", still_pixel)
            assert still_pixel[1] > still_pixel[0] and still_pixel[1] > still_pixel[2], still_pixel
            assert not errors, errors
            browser.close()
    finally:
        stop_server(server)

print("PASS agent voice")
