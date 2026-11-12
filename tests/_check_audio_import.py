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

# Empty-bin import interaction + audio assets riding the timeline mix.
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()


def make_media(tmp: Path) -> tuple[Path, Path]:
    still = tmp / "still.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00d040:s=320x180:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    tone = tmp / "tone.mp3"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:a", "libmp3lame", "-b:a", "128k", str(tone)],
        capture_output=True, check=True,
    )
    return still, tone


def mean_volume(path: Path, start: float, length: float) -> float:
    probe = subprocess.run(
        [ffmpeg, "-hide_banner", "-ss", str(start), "-t", str(length),
         "-i", str(path), "-map", "0:a?", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", probe.stderr)
    return float(match.group(1)) if match else -999.0


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    still_file, tone_file = make_media(tmp)
    server, thread = start_server()
    base = server_url(server)
    errors = []
    render_payloads = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))

            def remember_render(request):
                if request.url.endswith("/render") and request.method == "POST":
                    try:
                        render_payloads.append(json.loads(request.post_data or "{}"))
                    except ValueError:
                        pass

            page.on("request", remember_render)
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                setResolutionValue('320x180');
                const fps = document.getElementById('frameRate');
                fps.value = '24';
                fps.dispatchEvent(new Event('change', { bubbles: true }));
            }""")

            # The empty project area is a real import target.
            assert "DOUBLE-CLICK TO IMPORT" in page.locator(".bins-empty").inner_text()
            assert "AUDIO" in page.locator(".bins-empty").inner_text()
            with page.expect_file_chooser() as chooser_info:
                page.dblclick(".bins-empty")
            chooser = chooser_info.value
            chooser.set_files([str(still_file), str(tone_file)])
            page.wait_for_function("() => timelineState.assets.length === 2", timeout=60000)
            page.wait_for_timeout(800)

            assets = page.evaluate("timelineState.assets.map(a => ({ id: a.id, name: a.name, kind: a.kind, duration: a.duration, url: a.url }))")
            print("project assets:", json.dumps(assets))
            kinds = {asset["kind"] for asset in assets}
            assert kinds == {"image", "audio"}, assets
            audio_asset = next(asset for asset in assets if asset["kind"] == "audio")
            assert audio_asset["url"].startswith("/media/media-"), audio_asset
            assert 1.5 <= float(audio_asset["duration"]) <= 2.5, audio_asset
            assert page.locator("#binsCount").inner_text() == "2 ASSETS"
            assert page.locator(".dock-bin .bin-kind", has_text="AUD").count() == 1
            assert page.locator(".dock-bin .bin-wave").count() == 1
            assert page.locator(".bins-empty").count() == 0
            assert page.locator(".logic-box.media").count() == 0, "import auto-placed media"

            # Selecting the audio asset opens the audio inspector without a picture.
            page.evaluate(f"selectAsset('{audio_asset['id']}')")
            page.wait_for_timeout(400)
            assert page.locator("#mediaInspector").is_visible()
            assert page.locator("#inspectorTag").inner_text() == "MEDIA"
            assert page.locator("#miKind").inner_text() == "AUDIO"
            assert page.locator("#miPreview audio").count() == 1
            assert page.locator("#miFitField").is_hidden()

            # Insert the audio at 0.4s and drop the starter scene: audio-only render.
            page.evaluate("setPlayhead(0.4)")
            page.click("#miInsert")
            page.wait_for_function("() => timelineState.clips.filter(c => c.type === 'audio').length === 1", timeout=10000)
            page.wait_for_timeout(400)
            audio_clip = page.evaluate("timelineState.clips.find(c => c.type === 'audio')")
            print("audio clip:", audio_clip)
            assert abs(audio_clip["start"] - 0.4) < 0.01, audio_clip
            assert audio_clip["code"] == "", "audio clip stored a fake HTML wrapper"
            assert page.locator("#miSourceInField").is_visible()
            assert page.locator(".logic-box.media.audio").count() == 1

            page.evaluate("""() => {
                const clip = timelineState.clips.find(c => c.type === 'audio');
                clip.duration = 0.8;
                timelineState.clips = [clip];
                timelineState.activeId = clip.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            page.wait_for_timeout(300)
            plan = page.evaluate("() => { const p = buildTimelineRenderPlan(); return p ? { total: p.total, audio: p.audioClips } : null; }")
            print("audio plan:", plan)
            assert plan and len(plan["audio"]) == 1, plan
            assert plan["audio"][0]["start"] == 0.4, plan
            assert abs(plan["audio"][0]["duration"] - 0.8) < 0.01, plan

            page.screenshot(path=str(ROOT / "output" / "playwright" / "audio-project-bin.png"), full_page=True)

            page.evaluate("setFrameRange(0, 1.2)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(400)

            assert render_payloads, "no /render request captured"
            payload = render_payloads[-1]
            sent_audio = payload.get("audioClips") or []
            print("payload audio:", sent_audio)
            assert len(sent_audio) == 1, sent_audio
            assert sent_audio[0]["url"].startswith("/media/media-"), sent_audio
            assert abs(sent_audio[0]["start"] - 0.4) < 0.01, sent_audio

            video_path = tmp / "rendered-audio.mp4"
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
            video_path.write_bytes(base64.b64decode(video_b64))
            print("rendered file:", video_path, video_path.stat().st_size)
            assert video_path.stat().st_size > 2000

            lead_in = mean_volume(video_path, 0.0, 0.25)
            tone_level = mean_volume(video_path, 0.5, 0.5)
            print("mean volume lead-in/tone:", lead_in, tone_level)
            assert lead_in < -40, f"audio should be silent before its 0.4s start, got {lead_in} dB"
            assert tone_level > -35, f"timed audio missing from the export, got {tone_level} dB"

            page.screenshot(path=str(ROOT / "output" / "playwright" / "audio-timeline.png"), full_page=True)
            browser.close()
            assert not errors, errors
            print("AUDIO IMPORT CHECK: OK")
    finally:
        stop_server(server)
