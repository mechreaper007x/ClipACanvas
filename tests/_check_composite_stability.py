"""Composite preview must stay mounted across clip boundaries and seek every layer."""
import io
import os
import sys
import tempfile
from pathlib import Path

os.environ["APPDATA"] = tempfile.mkdtemp(prefix="cc-composite-")

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image
from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

SCENE1 = """<!doctype html><html><head><style>
html,body{margin:0;background:#1b2026;overflow:hidden}
#redbox{position:absolute;top:40%;left:0;width:80px;height:80px;background:#e33;animation:move 2s linear forwards}
@keyframes move{from{transform:translateX(0)}to{transform:translateX(400px)}}
</style></head><body><div id="redbox"></div></body></html>"""

SCENE2 = """<!doctype html><html><head><style>
html,body{margin:0;background:#20261b;overflow:hidden}
#bluebox{position:absolute;top:40%;left:0;width:80px;height:80px;background:#38f;animation:move 2s linear forwards}
@keyframes move{from{transform:translateX(0)}to{transform:translateX(400px)}}
</style></head><body><div id="bluebox"></div></body></html>"""


def child_with(page, element_id):
    for frame in page.frames:
        try:
            if frame.is_detached():
                continue
            if frame.evaluate(f"() => !!document.getElementById('{element_id}')"):
                return frame
        except Exception:
            continue
    return None


def transform_x(frame, element_id):
    value = frame.evaluate(
        f"() => getComputedStyle(document.getElementById('{element_id}')).transform"
    )
    if value == "none":
        return 0.0
    return float(value.split("(")[1].split(",")[4])


def composite_frame(page):
    for frame in page.frames:
        try:
            if not frame.is_detached() and frame.evaluate("() => !!document.querySelector('.cc-layer')"):
                return frame
        except Exception:
            continue
    return None


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
        page.evaluate("() => { setResolutionValue('640x360'); setFrameRange(0, 2); }")
        page.evaluate("""() => {
            timelineState.clips = [];
            timelineState.transitions = [];
            timelineState.assets = [];
            timelineState.layers = 4;
            timelineState.activeId = '';
            timelineState.playhead = 0;
            saveTimelineState(true);
            renderLogicBoxes();
            updateStageTimeline();
        }""")
        page.evaluate("""async ([scene1, scene2]) => {
            const first = await executeChatTool({ name: 'add_scene', args: { code: scene1, name: 'SCENE 01', duration: 2, layer: 'same' } });
            const second = await executeChatTool({ name: 'add_scene', args: { code: scene2, name: 'SCENE 02', duration: 2, layer: 'same' } });
            return { first: first.ok, second: second.ok, clips: timelineState.clips.map(c => [c.name, c.start, c.duration, c.track]) };
        }""", [SCENE1, SCENE2])
        page.wait_for_timeout(400)
        clips = page.evaluate("() => timelineState.clips.map(c => ({ name: c.name, start: c.start, duration: c.duration, track: c.track }))")
        print("clips:", clips)
        assert len(clips) == 2, clips

        page.evaluate("() => setPlayhead(1, { preview: true })")
        page.wait_for_timeout(900)
        page.evaluate("() => setPlayhead(1, { preview: true })")
        page.wait_for_timeout(400)
        comp = composite_frame(page)
        assert comp is not None, "no composite frame"
        comp.evaluate("() => { window.__generation = 'g1'; }")
        red = child_with(page, "redbox")
        assert red is not None, "scene 1 frame missing"
        red_x = transform_x(red, "redbox")
        print("t=1.0 red x:", red_x)
        assert 180 <= red_x <= 220, red_x

        key_before = page.evaluate("() => previewCompositeState.key")
        page.evaluate("() => setPlayhead(2.5, { preview: true })")
        page.wait_for_timeout(500)
        comp2 = composite_frame(page)
        assert comp2 is not None, "composite disappeared over the cut"
        marker = comp2.evaluate("() => window.__generation || ''")
        print("marker after cut:", marker)
        assert marker == "g1", "composite page was rebuilt at the cut"
        key_after = page.evaluate("() => previewCompositeState.key")
        assert key_before == key_after, (key_before, key_after)

        blue = child_with(page, "bluebox")
        assert blue is not None, "scene 2 frame missing"
        blue_x = transform_x(blue, "bluebox")
        print("t=2.5 blue x:", blue_x)
        assert 80 <= blue_x <= 120, blue_x

        page.evaluate("() => setPlayhead(0.4, { preview: true })")
        page.wait_for_timeout(400)
        red_x = transform_x(red, "redbox")
        print("t=0.4 red x:", red_x)
        assert 60 <= red_x <= 100, red_x
        assert comp2.evaluate("() => window.__generation || ''") == "g1", "scrubbing rebuilt the composite"

        def stage_image():
            shot = page.locator("#previewStage").screenshot()
            return Image.open(io.BytesIO(shot)).convert("RGB")

        def count_near(image, target, tolerance=45):
            return sum(
                1
                for pixel in image.getdata()
                if abs(pixel[0] - target[0]) <= tolerance
                and abs(pixel[1] - target[1]) <= tolerance
                and abs(pixel[2] - target[2]) <= tolerance
            )

        page.evaluate("() => setPlayhead(1, { preview: true })")
        page.wait_for_timeout(500)
        red_pixels = count_near(stage_image(), (227, 51, 51))
        print("red pixels at 1.0s:", red_pixels)
        assert red_pixels > 800, red_pixels

        page.evaluate("() => setPlayhead(2.5, { preview: true })")
        page.wait_for_timeout(500)
        blue_pixels = count_near(stage_image(), (51, 136, 255))
        print("blue pixels at 2.5s:", blue_pixels)
        assert blue_pixels > 800, blue_pixels

        page.evaluate("() => setPlayhead(2.01, { preview: true })")
        page.wait_for_timeout(400)
        boundary = stage_image()
        lit = sum(1 for pixel in boundary.getdata() if sum(pixel) > 120)
        print("lit pixels at the cut:", lit)
        assert lit > 1000, "monitor went black at the cut"
        assert not errors, errors
        browser.close()
finally:
    stop_server(server)

print("PASS composite stability")
