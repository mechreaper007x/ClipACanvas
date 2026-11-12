"""Timeline zoom: presets, slider, numeric entry, anchoring and fit."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

PRESETS = [100, 125, 150, 200, 250, 300, 400, 600, 800]
errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(Path(tmp_name) / "appdata")
    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)
            page.evaluate("""() => {
                timelineState.clips = [
                    {id: 'zoom-a', name: 'A', code: '<!doctype html><html><body style="margin:0;background:#123"></body></html>',
                     duration: 6, start: 0, track: 0, explicitDuration: true, type: 'code'},
                    {id: 'zoom-b', name: 'B', code: '<!doctype html><html><body style="margin:0;background:#321"></body></html>',
                     duration: 2, start: 3, track: 1, explicitDuration: true, type: 'code'}
                ];
                timelineState.layers = 2;
                timelineState.activeId = 'zoom-a';
                timelineState.playhead = 2;
                saveTimelineState(true);
                renderLogicBoxes();
                updateStageTimeline();
                positionPlayhead(2);
            }""")
            page.wait_for_timeout(300)

            assert page.locator("#timelineZoomInput").is_visible()
            assert page.locator("#timelineZoomRange").is_visible()
            presets = page.evaluate("Array.from(document.querySelectorAll('#timelineZoomPresets option')).map(o => Number(o.value))")
            assert presets == PRESETS, presets

            def zoom_state():
                return page.evaluate("""() => ({
                    zoom: timelineView.zoom,
                    start: timelineView.start,
                    span: timelineViewSpan(),
                    total: timelineTotalSeconds(),
                    ratio: (timelineState.playhead - timelineView.start) / timelineViewSpan()
                })""")

            def set_percent(value):
                page.locator("#timelineZoomInput").fill(str(value))
                page.locator("#timelineZoomInput").press("Tab")
                page.wait_for_timeout(160)

            anchor_before = zoom_state()
            for percent in PRESETS:
                set_percent(percent)
                state = zoom_state()
                assert abs(state["zoom"] - percent / 100) < 0.001, (percent, state)
                assert abs(state["span"] - state["total"] / (percent / 100)) < 0.01, (percent, state)
                assert abs(state["ratio"] - anchor_before["ratio"]) < 0.02, (percent, state, anchor_before)
                assert page.locator("#timelineZoomRange").input_value() == str(percent)
                assert page.locator("#timelineZoomInput").input_value() == str(percent)
            print("presets anchored:", [p for p in PRESETS], "ratio", round(anchor_before["ratio"], 3))

            # Numeric entry outside the range clamps to 100/800.
            set_percent(900)
            assert abs(page.evaluate("timelineView.zoom") - 8) < 0.001
            assert page.locator("#timelineZoomInput").input_value() == "800"
            set_percent(50)
            assert abs(page.evaluate("timelineView.zoom") - 1) < 0.001
            assert page.locator("#timelineZoomInput").input_value() == "100"

            # Slider gives finer steps than the presets.
            page.locator("#timelineZoomRange").evaluate(
                "el => { el.value = '350'; el.dispatchEvent(new Event('input', {bubbles: true})); }"
            )
            page.wait_for_timeout(180)
            assert abs(page.evaluate("timelineView.zoom") - 3.5) < 0.001
            assert page.locator("#timelineZoomInput").input_value() == "350"

            # Playhead-anchored zoom at a later playhead.
            page.evaluate("setPlayhead(4.5)")
            page.wait_for_timeout(200)
            before = zoom_state()
            set_percent(400)
            after = zoom_state()
            assert abs(after["ratio"] - before["ratio"]) < 0.02, (before, after)
            assert page.evaluate("timelineState.playhead") == 4.5

            # Ctrl+wheel zooms around the pointer.
            page.evaluate("fitTimelineView(); setPlayhead(0)")
            page.wait_for_timeout(250)
            wrap = page.evaluate("document.getElementById('etTracksWrap').getBoundingClientRect().toJSON()")
            pointer_x = wrap["x"] + wrap["width"] * 0.6
            pointer_y = wrap["y"] + wrap["height"] * 0.4
            time_before = page.evaluate(
                "([x, y]) => { const r = document.getElementById('etTracksWrap').getBoundingClientRect(); return timelinePctToTime(((x - r.left) / r.width) * 100); }",
                [pointer_x, pointer_y],
            )
            page.mouse.move(pointer_x, pointer_y)
            page.keyboard.down("Control")
            page.mouse.wheel(0, -120)
            page.keyboard.up("Control")
            page.wait_for_timeout(250)
            time_after = page.evaluate(
                "([x, y]) => { const r = document.getElementById('etTracksWrap').getBoundingClientRect(); return timelinePctToTime(((x - r.left) / r.width) * 100); }",
                [pointer_x, pointer_y],
            )
            zoomed = page.evaluate("timelineView.zoom")
            print("wheel zoom:", zoomed, "time under pointer", round(time_before, 2), "->", round(time_after, 2))
            assert zoomed > 1.05, zoomed
            assert abs(time_after - time_before) < 0.3, (time_before, time_after)

            # Zoom buttons and FIT keep the percent controls in sync.
            page.evaluate("fitTimelineView()")
            page.wait_for_timeout(150)
            page.click("#zoomIn")
            page.wait_for_timeout(150)
            assert page.locator("#timelineZoomInput").input_value() == "150"
            page.click("#zoomOut")
            page.wait_for_timeout(150)
            assert page.locator("#timelineZoomInput").input_value() == "100"
            set_percent(800)
            page.click("#zoomFit")
            page.wait_for_timeout(200)
            assert page.evaluate("timelineView.zoom") == 1
            assert page.locator("#timelineZoomInput").input_value() == "100"

            # Clips and ruler follow the zoom without document overflow.
            set_percent(800)
            page.evaluate("setPlayhead(2)")
            page.wait_for_timeout(250)
            box = page.locator('.logic-box[data-id="zoom-a"]').bounding_box()
            lane = page.locator('.et-row[data-track="0"] .et-lane').bounding_box()
            width_ratio = box["width"] / lane["width"]
            ruler = page.locator("#timelineRuler").inner_text()
            print("800% clip width ratio:", round(width_ratio, 2), "ruler:", ruler.replace("\n", " "))
            assert width_ratio > 5, width_ratio
            for width, height in ((1664, 916), (1280, 720)):
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(300)
                overflow = page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                assert overflow <= 0, (width, overflow)

            browser.close()
            assert not errors, errors
            print("TIMELINE ZOOM CHECK: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
