"""The exported frame at t must match the frame the Program Monitor draws at t."""
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="cc-parity-")

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

ffmpeg = resolve_ffmpeg_exe()
WIDTH, HEIGHT = 640, 360
SCENE = """<!doctype html><html><head><style>
html,body{margin:0;background:#101010;overflow:hidden}
#box{position:absolute;top:40%;left:0;width:80px;height:80px;background:#e33;animation:move 2s linear forwards}
@keyframes move{from{transform:translateX(0)}to{transform:translateX(400px)}}
</style></head><body><div id="box"></div></body></html>"""


def red_left_edge(path: Path, seconds: float) -> int:
    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(path), "-frames:v", "1",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    assert len(raw) >= WIDTH * HEIGHT * 3, len(raw)
    row = int(HEIGHT * 0.55)
    for x in range(WIDTH):
        offset = (row * WIDTH + x) * 3
        r, g, b = raw[offset], raw[offset + 1], raw[offset + 2]
        if r > 150 and g < 110 and b < 110:
            return x
    return -1


def preview_x(page, seconds):
    page.evaluate(f"() => setPlayhead({seconds}, {{ preview: true }})")
    page.wait_for_timeout(400)
    for frame in page.frames:
        try:
            if frame.evaluate("() => !!document.getElementById('box')"):
                value = frame.evaluate("() => getComputedStyle(document.getElementById('box')).transform")
                if value == "none":
                    return 0.0
                return float(value.split("(")[1].split(",")[4])
        except Exception:
            continue
    raise AssertionError("preview box frame missing")


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    server, thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                setResolutionValue('640x360');
                const fps = document.getElementById('frameRate');
                fps.value = '24'; fps.dispatchEvent(new Event('change', { bubbles: true }));
                setFrameRange(0, 2);
            }""")
            page.evaluate(
                """async (code) => executeChatTool({ name: 'insert_animation_code', args: { code, duration: 2 } })""",
                SCENE,
            )
            page.wait_for_timeout(300)

            preview_1 = preview_x(page, 1.0)
            preview_15 = preview_x(page, 1.5)

            page.evaluate("() => setFrameRange(0, 2)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=240000,
            )
            page.wait_for_timeout(400)
            film = tmp / "parity.mp4"
            video_b64 = page.evaluate("""async () => {
                const response = await fetch(resultVideoUrl);
                const bytes = new Uint8Array(await response.arrayBuffer());
                let text = '';
                const chunk = 0x8000;
                for (let i = 0; i < bytes.length; i += chunk) {
                    text += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                }
                return btoa(text);
            }""")
            film.write_bytes(base64.b64decode(video_b64))

            export_1 = red_left_edge(film, 1.0)
            export_15 = red_left_edge(film, 1.5)
            print("monitor 1.0s:", preview_1, "export 1.0s:", export_1)
            print("monitor 1.5s:", preview_15, "export 1.5s:", export_15)
            assert export_1 >= 0 and export_15 >= 0, (export_1, export_15)
            assert abs(export_1 - preview_1) <= 6, (preview_1, export_1)
            assert abs(export_15 - preview_15) <= 6, (preview_15, export_15)
            browser.close()
    finally:
        stop_server(server)

print("PASS preview/export parity")
