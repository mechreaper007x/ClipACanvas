"""End-to-end film export: image compositing, transitions and timeline audio mix.

Builds a five-image sequence with a dissolve and two audio lanes through the
real editor page, renders it through the real /render backend, then probes
pixels and audio levels of the produced MP4.
"""
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

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

ffmpeg = resolve_ffmpeg_exe()
COLORS = {
    "red": "0xd01818",
    "green": "0x18b848",
    "blue": "0x1848d0",
    "yellow": "0xe0c020",
    "magenta": "0xc020b0",
}


def probe_pixel(path: Path, seconds: float) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return out[0], out[1], out[2]


def mean_volume(path: Path, start: float, duration: float) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
         "-i", str(path), "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr)
    assert match, result.stderr[-800:]
    return float(match.group(1))


def close_to(pixel, rgb, tolerance=70) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(pixel, rgb))


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    media = []
    for index, (name, color) in enumerate(COLORS.items()):
        path = tmp / f"{name}.png"
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={color}:s=640x360:d=1",
             "-frames:v", "1", str(path)],
            capture_output=True, check=True,
        )
        media.append(path)
    music = tmp / "music.mp3"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=8",
         "-af", "volume=0.6", "-b:a", "128k", str(music)],
        capture_output=True, check=True,
    )
    sfx = tmp / "sfx.mp3"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
         "-b:a", "128k", str(sfx)],
        capture_output=True, check=True,
    )
    server, thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            render_payloads = []
            page.on("request", lambda request: render_payloads.append(json.loads(request.post_data or "{}"))
                    if request.url.endswith("/render") and request.method == "POST" else None)
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                setResolutionValue('320x180');
                const fps = document.getElementById('frameRate');
                fps.value = '24';
                fps.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
            page.set_input_files("#mediaInput", [str(path) for path in media] + [str(music), str(sfx)])
            page.wait_for_function("() => timelineState.assets.length === 7", timeout=120000)
            page.wait_for_timeout(800)

            plan = page.evaluate("""() => {
                const images = ['red', 'green', 'blue', 'yellow', 'magenta']
                    .map(name => timelineState.assets.find(asset => asset.name === name));
                timelineState.clips = [];
                timelineState.transitions = [];
                timelineState.layers = 1;
                const clips = images.map((asset, index) =>
                    insertAssetClip(asset, { at: index * 2, duration: 2, track: 0, mode: 'overwrite' }));
                const music = timelineState.assets.find(asset => asset.name === 'music');
                const sfx = timelineState.assets.find(asset => asset.name === 'sfx');
                const musicClip = insertAssetClip(music, { at: 0, duration: 8, audioTrack: 'A2' });
                const sfxClip = insertAssetClip(sfx, { at: 4, duration: 1, audioTrack: 'A3' });
                projectOps.setAudioTrackMix('A2', { volume: 0.25 });
                projectOps.setAudioTrackMix('A3', { volume: 1.0 });
                const transition = projectOps.addTransition({
                    fromClipId: clips[0].id,
                    toClipId: clips[1].id,
                    type: 'dissolve',
                    duration: 1.0,
                    alignment: 'center'
                });
                setFrameRange(0, 10);
                return {
                    clips: timelineState.clips.length,
                    lanes: [musicClip.audioTrack, sfxClip.audioTrack],
                    transition: transition.ok ? transition.transition.type : transition.error
                };
            }""")
            print("plan:", plan)
            assert plan["clips"] == 7, plan
            assert plan["lanes"] == ["A2", "A3"], plan
            assert plan["transition"] == "dissolve", plan

            built = page.evaluate("""() => {
                const p = buildTimelineRenderPlan();
                return {
                    clips: p.clips.length,
                    audio: p.audioClips.map(a => ({ start: a.start, duration: a.duration, volume: a.volume })),
                    transitions: p.transitions.length
                };
            }""")
            print("render plan:", built)
            assert built["clips"] == 7, built
            assert len(built["audio"]) == 2, built
            assert built["transitions"] == 1, built

            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=300000,
            )
            page.wait_for_timeout(500)

            assert render_payloads, "no /render request captured"
            payload = render_payloads[-1]
            assert len(payload.get("clips", [])) == 7, payload.get("clips")
            assert len(payload.get("audioClips", [])) == 2, payload.get("audioClips")
            meta = page.evaluate("window.lastRenderMeta")
            print("render meta:", meta)

            film = tmp / "film.mp4"
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
            print(streams[-600:])
            assert "Audio:" in streams, "exported MP4 has no audio stream"

            checks = [
                (0.5, (208, 24, 24), "red"),
                (3.0, (24, 184, 72), "green"),
                (5.0, (24, 72, 208), "blue"),
                (7.0, (224, 192, 32), "yellow"),
                (9.0, (192, 32, 176), "magenta"),
            ]
            for seconds, rgb, label in checks:
                pixel = probe_pixel(film, seconds)
                print(f"pixel @{seconds}s ({label}):", pixel)
                assert close_to(pixel, rgb), f"{label} image missing at {seconds}s: {pixel}"
            transition_pixel = probe_pixel(film, 2.0)
            print("pixel @2.0s (dissolve):", transition_pixel)
            assert not close_to(transition_pixel, (208, 24, 24), 30) and not close_to(transition_pixel, (24, 184, 72), 30), transition_pixel

            music_only = mean_volume(film, 0.5, 1.0)
            music_sfx = mean_volume(film, 4.2, 0.5)
            print("mean volume music:", music_only, "music+sfx:", music_sfx)
            assert music_only > -45, f"music lane silent: {music_only} dB"
            assert music_sfx > music_only + 3, f"sfx not mixed in: {music_sfx} vs {music_only}"

            film_out = ROOT / "output" / "uitest" / "renders" / "film-export-check.mp4"
            film_out.parent.mkdir(parents=True, exist_ok=True)
            film_out.write_bytes(film.read_bytes())
            print("saved:", film_out)
            browser.close()
    finally:
        stop_server(server)
    print("PASS film export")
