import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

import playwright_render
from serve import resolve_ffmpeg_exe

ffmpeg = resolve_ffmpeg_exe()

CLIP_RED = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#ff2200;overflow:hidden}
.box{width:40px;height:40px;background:#fff;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body><div class="box"></div></body></html>"""

CLIP_BLUE = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#0033ff;overflow:hidden}
</style></head><body></body></html>"""

CLIP_OVERLAY = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:transparent;overflow:hidden}
.badge{width:40%;height:100%;background:#00ff44}
</style></head><body><div class="badge"></div></body></html>"""


def probe_pixel(path: Path, seconds: float) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(seconds), "-i", str(path),
         "-frames:v", "1", "-vf", "scale=2:2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return out[0], out[1], out[2]


def probe_crop(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(seconds), "-i", str(path),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return out[0], out[1], out[2]


with tempfile.TemporaryDirectory() as tmp:
    output = Path(tmp) / "sequence.mp4"
    result = playwright_render.render_payload({
        "width": 320,
        "height": 240,
        "frameRate": 30,
        "maxDuration": 12,
        "minDuration": 0.35,
        "codec": "h264",
        "bitrate": "2M",
        "clips": [
            {"code": CLIP_RED, "duration": 1.0},
            {"code": CLIP_BLUE, "duration": 1.0},
        ],
    }, output, ffmpeg_exe=ffmpeg)
    print("result:", result)
    duration = float(result.get("duration") or 0)
    assert 1.8 <= duration <= 2.3, f"sequence duration wrong: {duration}"
    red = probe_pixel(output, 0.5)
    blue = probe_pixel(output, 1.5)
    print("pixel @0.5s:", red, "pixel @1.5s:", blue)
    assert red[0] > 140 and red[2] < 90, f"first clip not red: {red}"
    assert blue[2] > 140 and blue[0] < 90, f"second clip not blue: {blue}"

    trimmed = Path(tmp) / "trimmed.mp4"
    trimmed_result = playwright_render.render_payload({
        "width": 320,
        "height": 240,
        "frameRate": 30,
        "maxDuration": 12,
        "minDuration": 0.35,
        "codec": "h264",
        "bitrate": "2M",
        "renderStart": 1.0,
        "renderEnd": 1.5,
        "clips": [
            {"code": CLIP_RED, "duration": 1.0},
            {"code": CLIP_BLUE, "duration": 1.0},
        ],
    }, trimmed, ffmpeg_exe=ffmpeg)
    print("trimmed result:", trimmed_result)
    trimmed_duration = float(trimmed_result.get("duration") or 0)
    assert 1.35 <= trimmed_duration <= 1.55, trimmed_duration
    first = probe_pixel(trimmed, 0.02)
    last = probe_pixel(trimmed, 0.4)
    print("trimmed pixel @start:", first, "@end:", last)
    assert first[2] > 140 and first[0] < 90, f"trimmed render should start in scene 2: {first}"
    assert last[2] > 140 and last[0] < 90, f"trimmed render should stay in scene 2: {last}"

    layered = Path(tmp) / "layered.mp4"
    layered_result = playwright_render.render_payload({
        "width": 320,
        "height": 240,
        "frameRate": 30,
        "maxDuration": 12,
        "minDuration": 0.35,
        "codec": "h264",
        "bitrate": "2M",
        "clips": [
            {"code": CLIP_RED, "duration": 1.0, "start": 0.0, "track": 0},
            {"code": CLIP_BLUE, "duration": 0.5, "start": 0.25, "track": 1},
        ],
    }, layered, ffmpeg_exe=ffmpeg)
    print("layered result:", layered_result)
    below = probe_pixel(layered, 0.1)
    top = probe_pixel(layered, 0.5)
    back = probe_pixel(layered, 0.9)
    print("layered pixels below/top/back:", below, top, back)
    assert below[0] > 140 and below[2] < 90, f"lower layer should show first: {below}"
    assert top[2] > 140 and top[0] < 90, f"top layer should cover: {top}"
    assert back[0] > 140 and back[2] < 90, f"lower layer should return after top ends: {back}"

    overlay = Path(tmp) / "overlay.mp4"
    overlay_result = playwright_render.render_payload({
        "width": 320,
        "height": 240,
        "frameRate": 30,
        "maxDuration": 12,
        "minDuration": 0.35,
        "codec": "h264",
        "bitrate": "2M",
        "clips": [
            {"code": CLIP_RED, "duration": 1.0, "start": 0.0, "track": 0},
            {"code": CLIP_OVERLAY, "duration": 1.0, "start": 0.0, "track": 1},
        ],
    }, overlay, ffmpeg_exe=ffmpeg)
    print("overlay result:", overlay_result)
    overlay_left = probe_crop(overlay, 0.5, 10, 100)
    overlay_right = probe_crop(overlay, 0.5, 290, 100)
    print("overlay left/right:", overlay_left, overlay_right)
    assert overlay_left[1] > 140 and overlay_left[0] < 90, f"transparent overlay failed: {overlay_left}"
    assert overlay_right[0] > 140 and overlay_right[2] < 90, f"lower layer should show through: {overlay_right}"
    print("SEQUENCE RENDER OK")
