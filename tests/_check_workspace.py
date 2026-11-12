"""Verify the NLE workspace shell: full-width timeline, tabs, monitor transport,
timeline zoom and inspector wiring. Screenshots land in output/playwright/."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import resolve_ffmpeg_exe, server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
ffmpeg = resolve_ffmpeg_exe()
VIEWPORTS = [(1664, 916), (1440, 900), (1280, 720)]

errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    still = tmp / "wide.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1500)

            # Header: project name, save state, export.
            assert page.locator("#projectName").is_visible(), "project name missing"
            assert page.locator("#saveState").inner_text().strip() == "SAVED"
            assert page.locator("#btnConvert").is_visible(), "export missing from toolbar"
            assert page.locator("#btnDownload").is_visible(), "download missing from toolbar"

            # Default tabs.
            assert page.locator("#tabProject").get_attribute("aria-selected") == "true"
            assert page.locator("#tabInspector").get_attribute("aria-selected") == "true"
            assert page.locator("#inspectorPanel").is_visible()
            assert not page.locator("#aiChat").is_visible()

            # Bin lives in the left panel; timeline spans the window.
            left = page.evaluate("document.querySelector('.code-pane').getBoundingClientRect().toJSON()")
            bin_rect = page.evaluate("document.getElementById('projectBin').getBoundingClientRect().toJSON()")
            timeline = page.evaluate("document.querySelector('.editor-timeline').getBoundingClientRect().toJSON()")
            assert left["x"] <= bin_rect["x"] and bin_rect["x"] + bin_rect["width"] <= left["x"] + left["width"] + 1
            assert left["y"] <= bin_rect["y"]
            assert timeline["width"] > 0.9 * 1664, f"timeline is not full width: {timeline['width']}"
            print("bin/timeline widths:", round(bin_rect["width"]), round(timeline["width"]))

            # Scene list drives selection + opens the Code tab.
            page.locator(".scene-row").first.click()
            page.wait_for_timeout(400)
            assert page.locator("#tabCodePane").get_attribute("aria-selected") == "true"
            assert page.locator("#monacoHost").is_visible(), "monaco host hidden in CODE tab"
            page.screenshot(path=str(OUT / "workspace-code-tab.png"))

            # Playback transport advances the playhead.
            before = page.evaluate("timelineState.playhead")
            page.click("#playToggle")
            page.wait_for_timeout(800)
            after = page.evaluate("timelineState.playhead")
            assert after > before + 0.3, f"playhead did not advance: {before} -> {after}"
            assert page.locator("#playToggle").get_attribute("aria-label") == "Pause"
            assert page.locator("#playToggle").evaluate("el => el.classList.contains('active')")
            page.click("#playToggle")
            page.wait_for_timeout(300)
            assert page.evaluate("playbackState.playing") is False
            print("playback advanced:", round(before, 2), "->", round(after, 2))

            # Zoom changes the visible time window; FIT restores it.
            page.click("#zoomIn")
            page.wait_for_timeout(400)
            zoom = page.evaluate("timelineView.zoom")
            span = page.evaluate("timelineViewSpan()")
            total = page.evaluate("timelineTotalSeconds()")
            assert zoom > 1.2 and span < total - 0.1, f"zoom did not narrow the view: {zoom} {span}/{total}"
            page.screenshot(path=str(OUT / "workspace-zoomed.png"))
            page.click("#zoomFit")
            page.wait_for_timeout(400)
            assert page.evaluate("timelineView.zoom") == 1
            assert page.evaluate("timelineView.start") == 0

            # Imported media shows in the bin and opens the Inspector tab.
            page.set_input_files("#mediaInput", str(still))
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=30000)
            page.wait_for_timeout(600)
            page.click("#tabProject")
            page.wait_for_timeout(200)
            card = page.locator(".dock-bin").first.bounding_box()
            art = page.locator(".dock-bin .bin-art").first.bounding_box()
            assert art["width"] / art["height"] > 1.6 and art["width"] / art["height"] < 1.9, f"bin art not 16:9: {art}"
            assert card["width"] <= 160, f"bin card stretched: {card['width']}"

            # Dragging the imported card onto an empty video lane must add it
            # to the timeline (audio lanes only accept audio assets).
            target_lane = page.locator('.et-row[data-track="0"] .et-lane').bounding_box()
            page.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
            page.mouse.down()
            page.mouse.move(card["x"] + card["width"] / 2 + 30, card["y"] - 20, steps=5)
            page.mouse.move(
                target_lane["x"] + target_lane["width"] * 0.3,
                target_lane["y"] + target_lane["height"] / 2,
                steps=15,
            )
            page.wait_for_timeout(250)
            drop_live = page.locator("#etDropHint").is_visible()
            drop_text = page.locator("#etDropHint").inner_text() if drop_live else ""
            marker_time = page.locator("#dropMarkerTime").inner_text()
            assert drop_live, "timeline showed no drop feedback for a bin drag"
            assert "DROP AT" in drop_text and marker_time, (drop_text, marker_time)
            print("drop feedback:", drop_text, "| marker:", marker_time)
            page.mouse.up()
            page.wait_for_function("() => timelineState.clips.some(c => c.type === 'image')", timeout=10000)
            dropped = page.evaluate("timelineState.clips.filter(c => c.type === 'image').map(c => [c.start, c.track])")
            print("bin -> timeline drop:", dropped)
            assert dropped and 0 <= dropped[0][1] <= 3, dropped
            page.screenshot(path=str(OUT / "workspace-timeline-drop.png"))

            page.locator(".dock-bin").first.click()
            page.wait_for_timeout(500)
            assert page.locator("#tabInspector").get_attribute("aria-selected") == "true"
            assert page.locator("#mediaInspector").is_visible(), "media inspector did not open"
            assert page.locator("#miInsert").is_visible()
            page.screenshot(path=str(OUT / "workspace-inspector-media.png"))

            # Chat tab stays intact.
            page.click("#tabAssistant")
            page.wait_for_timeout(300)
            assert page.locator("#aiChat").is_visible()
            assert page.locator("#chatInput").is_visible()
            page.screenshot(path=str(OUT / "workspace-chat-tab.png"))

            # Recipe tab still renders all export controls.
            page.click("#tabRecipe")
            page.wait_for_timeout(300)
            assert page.locator("#recipePanel").is_visible()
            assert page.locator("#resolutionTier").is_visible()
            assert page.locator("#codec").is_visible()

            # Reference viewports: no document overflow, monitor keeps aspect.
            for width, height in VIEWPORTS:
                page.set_viewport_size({"width": width, "height": height})
                page.wait_for_timeout(500)
                metrics = page.evaluate("""() => {
                    const doc = document.documentElement;
                    const stage = document.getElementById('previewStage').getBoundingClientRect();
                    const dock = document.querySelector('.transport-dock').getBoundingClientRect();
                    return {
                        overflowX: doc.scrollWidth - innerWidth,
                        overflowY: doc.scrollHeight - innerHeight,
                        ratio: stage.width / stage.height,
                        timelineShare: dock.height / innerHeight,
                    };
                }""")
                assert metrics["overflowX"] <= 0 and metrics["overflowY"] <= 0, f"overflow at {width}x{height}: {metrics}"
                assert abs(metrics["ratio"] - 9 / 16) < 0.02, f"preview aspect broken at {width}x{height}: {metrics}"
                assert 0.3 < metrics["timelineShare"] < 0.55, f"timeline share off at {width}x{height}: {metrics}"
                print(f"{width}x{height}:", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in metrics.items()})

            if errors:
                print("CONSOLE ERRORS:", errors[:10])
            browser.close()
    finally:
        try:
            server.shutdown()
        except Exception:
            pass

print("RESULT:", "FAIL" if errors else "PASS")
