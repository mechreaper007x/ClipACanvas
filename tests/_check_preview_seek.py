"""The program monitor must draw the same time the timeline is parked on."""
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

SCENE = """<!doctype html><html><head><style>
html,body{margin:0;background:#111;overflow:hidden}
#box{position:absolute;top:40%;left:0;width:80px;height:80px;background:#e33;animation:move 2s linear forwards}
@keyframes move{from{transform:translateX(0)}to{transform:translateX(400px)}}
</style></head><body><div id="box"></div></body></html>"""

OVERLAY = """<!doctype html><html><head><style>
html,body{margin:0;background:transparent;overflow:hidden}
#dot{position:absolute;top:10%;left:0;width:60px;height:60px;border-radius:50%;background:#3af;animation:slide 2s linear forwards}
@keyframes slide{from{transform:translateX(0)}to{transform:translateX(300px)}}
</style></head><body><div id="dot"></div></body></html>"""


def serve_frame(page, element_id):
    for frame in page.frames:
        try:
            if frame.evaluate(f"() => !!document.getElementById('{element_id}')"):
                return frame
        except Exception:
            continue
    raise AssertionError(f"frame with #{element_id} not found")


def transform_x(frame, element_id):
    value = frame.evaluate(
        f"() => window.__clipacanvasSetTime ? getComputedStyle(document.getElementById('{element_id}')).transform : 'no-clock'"
    )
    if value == "no-clock":
        return None
    if value == "none":
        return 0.0
    return float(value.split("(")[1].split(",")[4])


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
        page.evaluate(
            """async (code) => {
                const first = await executeChatTool({ name: 'insert_animation_code', args: { code, duration: 2 } });
                const second = await executeChatTool({ name: 'add_scene', args: { code, name: 'SCENE 02', duration: 2, layer: 'same' } });
                return { first: first.ok, second: second.ok };
            }""",
            SCENE,
        )
        page.wait_for_timeout(300)

        page.evaluate("() => setPlayhead(1, { preview: true })")
        page.wait_for_timeout(500)
        frame = serve_frame(page, "box")
        at_1 = transform_x(frame, "box")
        print("preview at 1.0s:", at_1)
        assert at_1 is not None, "preview scene did not get the deterministic clock"
        assert 180 <= at_1 <= 220, at_1

        frame.evaluate("() => { window.__noReloadMarker = 'kept'; }")
        page.evaluate("() => setPlayhead(1.5, { preview: true })")
        page.wait_for_timeout(250)
        at_15 = transform_x(frame, "box")
        marker = frame.evaluate("() => window.__noReloadMarker || ''")
        print("preview at 1.5s:", at_15, "marker:", marker)
        assert 280 <= at_15 <= 320, at_15
        assert marker == "kept", "scrubbing reloaded the scene instead of seeking it"

        page.evaluate("() => setPlayhead(0, { preview: true })")
        page.wait_for_timeout(200)
        assert transform_x(frame, "box") <= 10

        page.evaluate("() => togglePlayback()")
        page.wait_for_timeout(700)
        playhead = page.evaluate("() => timelineState.playhead")
        moving = transform_x(frame, "box")
        page.evaluate("() => togglePlayback()")
        print("playhead after 0.7s:", playhead, "box x:", moving)
        assert playhead > 0.4, playhead
        assert moving > 120, moving

        overlay = page.evaluate(
            """async (code) => {
                const created = await executeChatTool({ name: 'create_overlay', args: { code, name: 'TITLE', duration: 2, start: 0, track: 1 } });
                return created.ok;
            }""",
            OVERLAY,
        )
        assert overlay, overlay
        page.wait_for_timeout(300)
        page.evaluate("() => setPlayhead(1, { preview: true })")
        page.wait_for_timeout(700)
        dot_frame = serve_frame(page, "dot")
        dot_x = transform_x(dot_frame, "dot")
        box_frame = serve_frame(page, "box")
        box_in_composite = transform_x(box_frame, "box")
        print("composite at 1.0s: overlay", dot_x, "scene", box_in_composite)
        assert 130 <= dot_x <= 170, dot_x
        assert 180 <= box_in_composite <= 220, box_in_composite
        assert not errors, errors
        browser.close()
finally:
    stop_server(server)

print("PASS preview seek")
