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

PRESETS = [1, 2, 5, 10, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400, 600, 800]
MIN_SPAN = 30
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

            def seed(clips, playhead=2):
                page.evaluate("""({clips, playhead}) => {
                    timelineState.clips = clips.map(item => ({
                        id: item.id, name: item.name,
                        code: '<!doctype html><html><body style="margin:0;background:#123"></body></html>',
                        duration: item.duration, start: item.start, track: item.track || 0,
                        explicitDuration: true, type: 'code'
                    }));
                    timelineState.layers = 1 + (timelineState.clips.length
                        ? Math.max(...timelineState.clips.map(c => c.track || 0)) : 0);
                    timelineState.activeId = clips.length ? clips[0].id : null;
                    timelineState.playhead = playhead;
                    timelineView.zoom = 1;
                    timelineView.start = 0;
                    saveTimelineState(true);
                    renderLogicBoxes();
                    updateStageTimeline();
                    positionPlayhead(playhead);
                }""", {"clips": clips, "playhead": playhead})
                page.wait_for_timeout(300)

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

            # A short sequence keeps a 30s working view: a 3s scene is a small box,
            # not a scene stretched across the whole lane.
            seed([{"id": "solo", "name": "SOLO", "duration": 3, "start": 0}], playhead=0)
            solo = page.evaluate("""() => {
                const box = document.querySelector('.logic-box[data-id="solo"]').getBoundingClientRect();
                const lane = document.querySelector('.et-row[data-track="0"] .et-lane').getBoundingClientRect();
                return {
                    span: timelineViewSpan(),
                    ratio: box.width / lane.width,
                    ruler: document.getElementById('timelineRuler').innerText.replace(/\\s+/g, ' '),
                    total: timelineTotalSeconds()
                };
            }""")
            print("solo scene:", solo)
            assert abs(solo["span"] - MIN_SPAN) < 0.01, solo
            assert 0.08 < solo["ratio"] < 0.12, solo
            assert "30.00s" in solo["ruler"], solo

            # Empty timeline also shows the working span, not half a second.
            seed([], playhead=0)
            empty = page.evaluate("""() => ({
                span: timelineViewSpan(),
                ruler: document.getElementById('timelineRuler').innerText.replace(/\\s+/g, ' ')
            })""")
            print("empty view:", empty)
            assert abs(empty["span"] - MIN_SPAN) < 0.01, empty
            assert "30.00s" in empty["ruler"], empty

            # 6s sequence: 100% is 30s, zoom-out below 100% reveals more time.
            seed([
                {"id": "zoom-a", "name": "A", "duration": 6, "start": 0},
                {"id": "zoom-b", "name": "B", "duration": 2, "start": 3, "track": 1},
            ], playhead=2)
            baseline = zoom_state()
            print("baseline:", baseline)
            assert abs(baseline["span"] - MIN_SPAN) < 0.01, baseline

            presets = page.evaluate("Array.from(document.querySelectorAll('#timelineZoomPresets option')).map(o => Number(o.value))")
            assert presets == PRESETS, presets
            assert page.locator("#timelineZoomInput").is_visible()
            assert page.locator("#timelineZoomRange").is_visible()

            # The percent value must render in full (no clipped "100").
            input_fit = page.evaluate("""() => {
                const el = document.getElementById('timelineZoomInput');
                return { width: el.getBoundingClientRect().width, client: el.clientWidth, scroll: el.scrollWidth };
            }""")
            print("zoom input fit:", input_fit)
            assert input_fit["width"] >= 56, input_fit
            assert input_fit["scroll"] <= input_fit["client"] + 1, input_fit

            anchor_before = baseline
            for percent in PRESETS:
                set_percent(percent)
                state = zoom_state()
                expected_span = max(MIN_SPAN, state["total"]) / (percent / 100)
                assert abs(state["zoom"] - percent / 100) < 0.001, (percent, state)
                assert abs(state["span"] - expected_span) < 0.01, (percent, state)
                if state["span"] >= state["total"]:
                    assert state["start"] == 0, (percent, state)
                assert page.evaluate("timelineState.playhead") == 2, (percent, state)
                assert page.locator("#timelineZoomRange").input_value() == str(percent)
                assert page.locator("#timelineZoomInput").input_value() == str(percent)
            print("presets:", PRESETS)

            # Zoomed out, a short clip shrinks instead of covering the lane.
            set_percent(50)
            out_ratio = page.evaluate("""() => {
                const box = document.querySelector('.logic-box[data-id="zoom-a"]').getBoundingClientRect();
                const lane = document.querySelector('.et-row[data-track="0"] .et-lane').getBoundingClientRect();
                return box.width / lane.width;
            }""")
            print("clip ratio @50%:", round(out_ratio, 3))
            assert 0.08 < out_ratio < 0.12, out_ratio

            # Numeric entry outside the range clamps to 1/800, and 1% must
            # reveal at least 30 minutes of a short sequence.
            set_percent(900)
            assert abs(page.evaluate("timelineView.zoom") - 8) < 0.001
            assert page.locator("#timelineZoomInput").input_value() == "800"
            set_percent(0.2)
            assert abs(page.evaluate("timelineView.zoom") - 0.01) < 0.001
            assert page.locator("#timelineZoomInput").input_value() == "1"
            wide = zoom_state()
            print("1% span:", wide["span"])
            assert wide["span"] >= 1800, wide

            # Slider gives finer steps than the presets.
            page.locator("#timelineZoomRange").evaluate(
                "el => { el.value = '350'; el.dispatchEvent(new Event('input', {bubbles: true})); }"
            )
            page.wait_for_timeout(180)
            assert abs(page.evaluate("timelineView.zoom") - 3.5) < 0.001
            assert page.locator("#timelineZoomInput").input_value() == "350"

            # Playhead-anchored zoom once the content is longer than the view.
            seed([{"id": "long", "name": "LONG", "duration": 120, "start": 0}], playhead=90)
            set_percent(200)
            page.evaluate("setPlayhead(90)")
            page.wait_for_timeout(200)
            before = zoom_state()
            set_percent(300)
            after = zoom_state()
            print("anchor:", before, after)
            assert before["span"] < before["total"] and after["span"] < after["total"], (before, after)
            assert abs(after["ratio"] - before["ratio"]) < 0.02, (before, after)
            assert page.evaluate("timelineState.playhead") == 90

            # Ctrl+wheel zooms around the pointer.
            page.evaluate("fitTimelineView(); setPlayhead(0)")
            page.wait_for_timeout(250)
            wrap = page.evaluate("document.getElementById('etTracksWrap').getBoundingClientRect().toJSON()")
            pointer_x = wrap["x"] + wrap["width"] * 0.6
            pointer_y = wrap["y"] + wrap["height"] * 0.4
            time_before = page.evaluate(
                "([x, y]) => { const r = document.getElementById('etTracksWrap').getBoundingClientRect(); return timelineView.start + ((x - r.left) / r.width) * timelineViewSpan(); }",
                [pointer_x, pointer_y],
            )
            page.mouse.move(pointer_x, pointer_y)
            page.keyboard.down("Control")
            page.mouse.wheel(0, -120)
            page.keyboard.up("Control")
            page.wait_for_timeout(250)
            time_after = page.evaluate(
                "([x, y]) => { const r = document.getElementById('etTracksWrap').getBoundingClientRect(); return timelineView.start + ((x - r.left) / r.width) * timelineViewSpan(); }",
                [pointer_x, pointer_y],
            )
            zoomed = page.evaluate("timelineView.zoom")
            print("wheel zoom:", zoomed, "time under pointer", round(time_before, 2), "->", round(time_after, 2))
            assert zoomed > 1.05, zoomed
            assert abs(time_after - time_before) < 0.5, (time_before, time_after)

            # Zoom buttons and FIT keep the percent controls in sync.
            page.evaluate("fitTimelineView()")
            page.wait_for_timeout(150)
            page.click("#zoomIn")
            page.wait_for_timeout(150)
            assert page.locator("#timelineZoomInput").input_value() == "150"
            page.click("#zoomOut")
            page.wait_for_timeout(150)
            assert page.locator("#timelineZoomInput").input_value() == "100"
            page.click("#zoomOut")
            page.wait_for_timeout(150)
            assert page.locator("#timelineZoomInput").input_value() == "67"
            set_percent(800)
            page.click("#zoomFit")
            page.wait_for_timeout(200)
            assert page.evaluate("timelineView.zoom") == 1
            assert page.locator("#timelineZoomInput").input_value() == "100"

            # Clips and ruler follow the zoom without document overflow.
            set_percent(800)
            page.evaluate("setPlayhead(2)")
            page.wait_for_timeout(250)
            box = page.locator('.logic-box[data-id="long"]').bounding_box()
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
