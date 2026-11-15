"""Scene-embedded video must export the frame for the requested time, not a stale or black one."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

APP_DATA = Path(tempfile.mkdtemp(prefix="cc-video-render-"))
os.environ["APPDATA"] = str(APP_DATA)

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

import playwright_render
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

ffmpeg = resolve_ffmpeg_exe()
media_dir = APP_DATA / "ClipACanvas" / "media"
media_dir.mkdir(parents=True, exist_ok=True)
video_name = "media-0123456789abcdef0123.mp4"
video_path = media_dir / video_name
subprocess.run(
    [
        ffmpeg, "-y",
        "-f", "lavfi", "-i", "color=c=0xff0000:s=320x240:d=1:r=24",
        "-f", "lavfi", "-i", "color=c=0x00ff00:s=320x240:d=1:r=24",
        "-f", "lavfi", "-i", "color=c=0x0000ff:s=320x240:d=1:r=24",
        "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[v]",
        "-map", "[v]", "-pix_fmt", "yuv420p", str(video_path),
    ],
    capture_output=True, check=True,
)
print("fixture:", video_path, video_path.stat().st_size)

SCENE = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#000;overflow:hidden}
.cc-scene-media{position:fixed;inset:0;width:100%;height:100%;object-fit:cover}
</style></head><body>
<video class="cc-scene-media" src="URL_PLACEHOLDER" data-cc-fill="1" muted playsinline></video>
</body></html>"""

OVERLAY = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden}
.badge{position:absolute;right:0;top:0;width:40%;height:100%;background:#ffff00}
</style></head><body><div class="badge"></div></body></html>"""


def probe(path: Path, seconds: float, x: int, y: int):
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(seconds), "-i", str(path),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return out[0], out[1], out[2]


def near(pixel, target, tolerance=55):
    return all(abs(pixel[i] - target[i]) <= tolerance for i in range(3))


server, thread = start_server()
base = server_url(server)
try:
    url = f"{base}/media/{video_name}"
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "video-scene.mp4"
        result = playwright_render.render_payload({
            "width": 320,
            "height": 240,
            "frameRate": 24,
            "maxDuration": 3,
            "minDuration": 3,
            "renderStart": 0,
            "renderEnd": 3,
            "codec": "h264",
            "bitrate": "2M",
            "clips": [
                {"id": "video-scene", "code": SCENE.replace("URL_PLACEHOLDER", url), "duration": 3, "start": 0, "track": 0},
                {"id": "overlay", "code": OVERLAY, "duration": 3, "start": 0, "track": 1},
            ],
        }, output, ffmpeg_exe=ffmpeg)
        print("render:", result)
        samples = [
            (0.55, (255, 0, 0), "red"),
            (1.55, (0, 255, 0), "green"),
            (2.55, (0, 0, 255), "blue"),
            (0.95, (255, 0, 0), "red-again"),
            (1.05, (0, 255, 0), "green-after-cut"),
        ]
        for seconds, target, label in samples:
            pixel = probe(output, seconds, 40, 120)
            print(f"{label} @{seconds}s:", pixel)
            assert near(pixel, target), f"{label} frame wrong: {pixel}"
            badge = probe(output, seconds, 290, 120)
            assert near(badge, (255, 255, 0), 60), f"overlay missing at {seconds}s: {badge}"
        # No all-black frame anywhere in the first 3 seconds.
        for seconds in (0.05, 0.5, 1.0, 1.5, 2.0, 2.5, 2.95):
            pixel = probe(output, seconds, 40, 120)
            assert sum(pixel) > 120, f"black frame at {seconds}s: {pixel}"
        print("duration:", result.get("duration"))
finally:
    stop_server(server)

print("PASS video render frames")
