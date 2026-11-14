"""Empty timeline lanes stay compact while lanes with clips stay legible."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-lanes-")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1664, "height": 916})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)
        page.evaluate("""() => {
          const clip = (name, start, duration, track) => ({
            id: newClipId(), name, code: '<!doctype html><html><body></body></html>',
            duration, start, track, explicitDuration: true, type: 'code',
            assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain',
            parentClipId: '', audioTrack: ''
          });
          timelineState.clips.length = 0;
          [['SCENE 01', 0], ['FESTIVALS', 4], ['SPICES', 8], ['FUTURE', 12]]
            .forEach(([name, start]) => timelineState.clips.push(clip(name, start, 4, 0)));
          [['CAPTION 1', 4, 5.9], ['CAPTION 2', 9.9, 4.1], ['CAPTION 3', 14, 4.1], ['CAPTION 4', 18.1, 4]]
            .forEach(([name, start, duration]) => timelineState.clips.push(clip(name, start, duration, 3)));
          timelineState.layers = 4;
          saveTimelineState(true);
          renderLogicBoxes();
          updateStageTimeline();
        }""")
        page.wait_for_timeout(600)
        metrics = page.evaluate("""() => {
          const rows = [...document.querySelectorAll('.et-row')].map(row => {
            const rect = row.getBoundingClientRect();
            return {
              track: row.dataset.track !== undefined ? `V${Number(row.dataset.track) + 1}` : row.dataset.audioRow,
              empty: row.classList.contains('is-empty'),
              height: Math.round(rect.height * 10) / 10,
              boxes: [...row.querySelectorAll('.logic-box')].map(box => ({
                label: box.textContent.replace(/\\s+/g, ' ').trim().slice(0, 24),
                clipped: box.scrollHeight > box.clientHeight + 1
              }))
            };
          });
          const host = document.getElementById('logicTracks');
          return { rows, scrolls: host.scrollHeight > host.clientHeight + 1,
                   hostHeight: host.clientHeight, rowsHeight: rows.reduce((sum, row) => sum + row.height, 0) };
        }""")
        print("rows:", [(row["track"], row["empty"], row["height"]) for row in metrics["rows"]])
        print("host:", metrics["hostHeight"], "rows:", metrics["rowsHeight"], "scrolls:", metrics["scrolls"])
        by_track = {row["track"]: row for row in metrics["rows"]}
        assert list(by_track) == ["V4", "V3", "V2", "V1", "A1", "A2", "A3"], list(by_track)
        assert by_track["V4"]["height"] == 46 and by_track["V1"]["height"] == 46, by_track
        for track in ("V3", "V2", "A1", "A2", "A3"):
            assert by_track[track]["empty"], by_track[track]
            assert by_track[track]["height"] == 20, by_track[track]
        assert not metrics["scrolls"], metrics
        assert all(not box["clipped"] for row in metrics["rows"] for box in row["boxes"]), metrics
        assert len(by_track["V4"]["boxes"]) == 4 and len(by_track["V1"]["boxes"]) == 4, metrics
        assert not errors, errors

        # Drag the V4 lane edge 30 px taller: height and playhead stay in sync.
        playhead_before = page.evaluate("() => timelineState.playhead")
        handle = page.locator('.et-row[data-track="3"] .lane-resize').bounding_box()
        page.mouse.move(handle["x"] + 200, handle["y"] + handle["height"] / 2)
        page.mouse.down()
        page.mouse.move(handle["x"] + 200, handle["y"] + handle["height"] / 2 + 30, steps=8)
        page.mouse.up()
        page.wait_for_timeout(400)
        dragged = page.evaluate("""() => ({
            height: Math.round(document.querySelector('.et-row[data-track="3"]').getBoundingClientRect().height),
            stored: JSON.parse(localStorage.getItem('clipacanvas.timeline.v1')).laneHeights,
            playhead: timelineState.playhead
        })""")
        print("after drag:", dragged)
        assert dragged["height"] == 76, dragged
        assert dragged["stored"].get("V4") == 76, dragged
        assert dragged["playhead"] == playhead_before, dragged

        # Heights are per lane and survive a reload.
        page.reload(wait_until="load")
        page.wait_for_selector('.et-row[data-track="3"]', timeout=20000)
        page.wait_for_timeout(600)
        restored = page.evaluate("() => Math.round(document.querySelector('.et-row[data-track=\"3\"]').getBoundingClientRect().height)")
        print("after reload:", restored)
        assert restored == 76, restored

        # Double-click the handle resets the lane to its default height.
        page.dblclick('.et-row[data-track="3"] .lane-resize')
        page.wait_for_timeout(400)
        reset = page.evaluate("""() => ({
            height: Math.round(document.querySelector('.et-row[data-track="3"]').getBoundingClientRect().height),
            stored: JSON.parse(localStorage.getItem('clipacanvas.timeline.v1')).laneHeights
        })""")
        print("after reset:", reset)
        assert reset["height"] == 46, reset
        assert not reset["stored"].get("V4"), reset

        # Lane heights travel with the project payload.
        project_lanes = page.evaluate("""() => {
          const doc = buildProjectFilePayload();
          doc.timeline.laneHeights = { V1: 90 };
          applyProjectPayload(doc);
          return {
            height: Math.round(document.querySelector('.et-row[data-track="0"]').getBoundingClientRect().height),
            payload: buildProjectFilePayload().timeline.laneHeights
          };
        }""")
        print("project lane heights:", project_lanes)
        assert project_lanes["height"] == 90, project_lanes
        assert project_lanes["payload"].get("V1") == 90, project_lanes
        assert not errors, errors
        page.screenshot(path=str(ROOT / "output" / "playwright" / "timeline-lanes-fixed.png"), full_page=True)
        browser.close()
finally:
    stop_server(server)
print("PASS timeline lanes")
