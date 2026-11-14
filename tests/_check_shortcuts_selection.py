"""Premiere-style timeline shortcuts: selection, lift/ripple, shuttle, zoom."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-shortcuts-")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

SEED = """() => {
  const clip = (name, start, duration, track) => ({
    id: newClipId(), name, code: '<!doctype html><html><body></body></html>',
    duration, start, track, explicitDuration: true, type: 'code',
    assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain',
    parentClipId: '', audioTrack: ''
  });
  timelineState.clips.length = 0;
  timelineState.clips.push(clip('ALPHA', 0, 2, 0), clip('BETA', 2, 2, 0), clip('GAMMA', 6, 2, 1));
  timelineState.layers = 2;
  timelineState.activeId = timelineState.clips[0].id;
  timelineState.selectedIds = [];
  timelineState.playhead = 0;
  timelineState.snapEnabled = true;
  saveTimelineState(true);
  renderLogicBoxes();
  updateStageTimeline();
  return timelineState.clips.map(item => item.id);
}"""

SEED_MULTI = """() => {
  const clip = (name, start) => ({
    id: newClipId(), name, code: '<!doctype html><html><body></body></html>',
    duration: 2, start, track: 0, explicitDuration: true, type: 'code',
    assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain',
    parentClipId: '', audioTrack: ''
  });
  timelineState.clips.length = 0;
  timelineState.clips.push(clip('ONE', 0), clip('TWO', 2), clip('THREE', 4));
  timelineState.layers = 1;
  timelineState.activeId = timelineState.clips[0].id;
  timelineState.selectedIds = [];
  timelineState.playhead = 0;
  saveTimelineState(true);
  renderLogicBoxes();
  updateStageTimeline();
  return timelineState.clips.map(item => item.id);
}"""

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
        ids = page.evaluate(SEED)
        page.wait_for_timeout(300)
        print("seed ids:", ids)

        # Ctrl+A selects every clip and never highlights page text.
        page.evaluate("window.getSelection().removeAllRanges(); document.activeElement?.blur()")
        page.keyboard.press("Control+a")
        page.wait_for_timeout(200)
        select_all = page.evaluate("""() => ({
            selected: timelineState.selectedIds.length,
            boxes: document.querySelectorAll('.logic-box.selected').length,
            text: window.getSelection().toString()
        })""")
        print("ctrl+a:", select_all)
        assert select_all["selected"] == 3 and select_all["boxes"] == 3, select_all
        assert select_all["text"] == "", select_all
        page.screenshot(path=str(ROOT / "output" / "playwright" / "shortcuts-select-all.png"))

        # Ctrl+Shift+A clears the selection but keeps the active clip.
        page.keyboard.press("Control+Shift+a")
        page.wait_for_timeout(150)
        assert page.evaluate("timelineState.selectedIds.length") == 0
        assert page.locator(".logic-box.selected").count() == 0
        assert page.evaluate("timelineState.activeId") is not None

        # Shift+click adds, Ctrl+click toggles.
        page.locator(f'.logic-box[data-id="{ids[0]}"]').click()
        page.wait_for_timeout(120)
        page.locator(f'.logic-box[data-id="{ids[1]}"]').click(modifiers=["Shift"])
        page.wait_for_timeout(120)
        assert page.evaluate("timelineState.selectedIds.length") == 2, page.evaluate("timelineState.selectedIds")
        page.locator(f'.logic-box[data-id="{ids[1]}"]').click(modifiers=["Control"])
        page.wait_for_timeout(120)
        assert page.evaluate("timelineState.selectedIds.length") == 1, page.evaluate("timelineState.selectedIds")

        # Ctrl+A inside a text input still performs a native select-all.
        page.evaluate("""() => {
          const input = document.createElement('input');
          input.id = 'shortcutGuardProbe';
          input.value = 'select me';
          document.body.appendChild(input);
          input.focus();
        }""")
        page.keyboard.press("Control+a")
        native_select = page.evaluate("""() => {
            const el = document.getElementById('shortcutGuardProbe');
            return { focused: document.activeElement === el, from: el.selectionStart, to: el.selectionEnd, length: el.value.length };
        }""")
        page.evaluate("document.getElementById('shortcutGuardProbe').remove()")
        print("input ctrl+a:", native_select)
        assert native_select["focused"] and native_select["from"] == 0 and native_select["to"] == native_select["length"], native_select

        # Delete lifts (gap stays); Shift+Delete ripple deletes (gap closes).
        ids = page.evaluate(SEED)
        page.wait_for_timeout(150)
        page.locator(f'.logic-box[data-id="{ids[0]}"]').click()
        page.wait_for_timeout(120)
        page.keyboard.press("Delete")
        page.wait_for_timeout(200)
        lifted = page.evaluate("""() => ({
            count: timelineState.clips.length,
            betaStart: timelineState.clips.find(item => item.name === 'BETA')?.start,
            status: document.getElementById('statusBar').textContent
        })""")
        print("lift:", lifted)
        assert lifted["count"] == 2 and lifted["betaStart"] == 2, lifted
        assert "gap left" in lifted["status"].lower(), lifted

        ids = page.evaluate(SEED)
        page.wait_for_timeout(150)
        page.locator(f'.logic-box[data-id="{ids[0]}"]').click()
        page.wait_for_timeout(120)
        page.keyboard.press("Shift+Delete")
        page.wait_for_timeout(200)
        rippled = page.evaluate("""() => ({
            count: timelineState.clips.length,
            betaStart: timelineState.clips.find(item => item.name === 'BETA')?.start,
            status: document.getElementById('statusBar').textContent
        })""")
        print("ripple:", rippled)
        assert rippled["count"] == 2 and abs(rippled["betaStart"]) < 1e-6, rippled
        assert "gap closed" in rippled["status"].lower(), rippled

        # Ripple deleting a multi-clip selection applies one undoable step.
        multi_ids = page.evaluate(SEED_MULTI)
        page.wait_for_timeout(150)
        page.locator(f'.logic-box[data-id="{multi_ids[0]}"]').click()
        page.locator(f'.logic-box[data-id="{multi_ids[1]}"]').click(modifiers=["Control"])
        page.wait_for_timeout(120)
        assert page.evaluate("timelineState.selectedIds.length") == 2
        page.keyboard.press("Shift+Delete")
        page.wait_for_timeout(250)
        multi = page.evaluate("""() => ({
            names: timelineState.clips.map(item => item.name),
            threeStart: timelineState.clips[0]?.start,
            selected: timelineState.selectedIds.length
        })""")
        print("multi ripple:", multi)
        assert multi["names"] == ["THREE"] and abs(multi["threeStart"]) < 1e-6, multi
        assert multi["selected"] == 0, multi
        page.keyboard.press("Control+z")
        page.wait_for_timeout(250)
        assert page.evaluate("timelineState.clips.length") == 3, "multi delete was not one undo step"

        # Ctrl+K adds an edit at the playhead; S now toggles snapping.
        page.evaluate(SEED)
        page.evaluate("setPlayhead(1)")
        page.keyboard.press("Control+k")
        page.wait_for_timeout(200)
        split = page.evaluate("""() => ({
            count: timelineState.clips.length,
            pieces: timelineState.clips.filter(item => item.name.startsWith('ALPHA')).map(item => [item.start, item.duration]).sort()
        })""")
        print("ctrl+k:", split)
        assert split["count"] == 4 and split["pieces"] == [[0, 1], [1, 1]], split

        page.keyboard.press("s")
        page.wait_for_timeout(120)
        snap = page.evaluate("""() => ({
            enabled: timelineState.snapEnabled,
            pressed: document.getElementById('snapToggle').getAttribute('aria-pressed'),
            meta: document.getElementById('timelineMeta').textContent
        })""")
        print("snap off:", snap)
        assert snap["enabled"] is False and snap["pressed"] == "false" and "SNAP OFF" in snap["meta"], snap
        assert page.evaluate("timelineState.clips.length") == 4, "S must not split anymore"
        page.keyboard.press("s")
        assert page.evaluate("timelineState.snapEnabled") is True

        # Up / Down jump between edit points; Shift+Arrow steps five frames.
        page.evaluate(SEED)
        page.evaluate("setPlayhead(1); document.activeElement?.blur()")
        page.keyboard.press("ArrowDown")
        down = page.evaluate("timelineState.playhead")
        page.keyboard.press("ArrowUp")
        up = page.evaluate("timelineState.playhead")
        print("edit points down/up:", down, up)
        assert abs(down - 2) < 1e-6 and abs(up - 0) < 1e-6, (down, up)

        page.evaluate("setPlayhead(0); document.getElementById('frameRate').value = '60'")
        page.keyboard.press("Shift+ArrowRight")
        stepped = page.evaluate("timelineState.playhead")
        print("shift step:", stepped)
        assert abs(stepped - 5 / 60) < 1e-5, stepped

        # = / - zoom, \ fits.
        page.keyboard.press("=")
        zoomed = page.evaluate("timelineView.zoom")
        page.keyboard.press("-")
        unzoomed = page.evaluate("timelineView.zoom")
        page.keyboard.press("=")
        page.keyboard.press("Backslash")
        fitted = page.evaluate("timelineView.zoom")
        print("zoom:", zoomed, unzoomed, fitted)
        assert zoomed > 1 and abs(unzoomed - 1) < 1e-6 and abs(fitted - 1) < 1e-6, (zoomed, unzoomed, fitted)

        # J / K / L shuttle with rate doubling.
        page.evaluate(SEED)
        page.wait_for_timeout(100)
        page.keyboard.press("l")
        page.wait_for_timeout(350)
        forward = page.evaluate("() => ({ playing: playbackState.playing, at: timelineState.playhead, rate: playbackState.rate })")
        page.keyboard.press("l")
        doubled = page.evaluate("playbackState.rate")
        page.keyboard.press("k")
        stopped = page.evaluate("playbackState.playing")
        page.keyboard.press("j")
        page.wait_for_timeout(250)
        reverse = page.evaluate("() => ({ playing: playbackState.playing, direction: playbackState.direction, at: timelineState.playhead })")
        page.keyboard.press("k")
        print("shuttle:", forward, doubled, stopped, reverse)
        assert forward["playing"] and forward["at"] > 0, forward
        assert doubled == 2, doubled
        assert stopped is False, stopped
        assert reverse["playing"] and reverse["direction"] == -1, reverse

        # Shortcut sheet opens from the ? button and lists the NLE keys.
        page.click("#shortcutHelpBtn")
        page.wait_for_timeout(200)
        sheet = page.evaluate("""() => ({
            text: document.getElementById('shortcutHelpModal').textContent
        })""")
        sheet_visible = page.locator("#shortcutHelpModal").is_visible()
        print("shortcut sheet:", sheet_visible, len(sheet["text"]))
        assert sheet_visible, sheet
        page.screenshot(path=str(ROOT / "output" / "playwright" / "shortcuts-sheet.png"))
        for phrase in ("Add edit", "Select all timeline clips", "Toggle snapping", "PREMIERE-STYLE"):
            assert phrase.lower() in sheet["text"].lower(), phrase
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        assert page.evaluate("document.getElementById('shortcutHelpModal').style.display") == "none"
        page.keyboard.press("?")
        page.wait_for_timeout(150)
        assert page.locator("#shortcutHelpModal").is_visible()
        page.keyboard.press("Escape")

        # SNAP and ? must not overflow the timeline header at common widths.
        for width in (1664, 1440, 1280):
            page.set_viewport_size({"width": width, "height": 900})
            page.wait_for_timeout(250)
            head = page.evaluate("""() => {
                const head = document.querySelector('.timeline-head');
                const actions = document.querySelector('.timeline-actions').getBoundingClientRect();
                const zoom = document.querySelector('.timeline-zoom').getBoundingClientRect();
                return {
                    overflow: head.scrollWidth > head.clientWidth + 1,
                    actionsRight: actions.right,
                    zoomLeft: zoom.left,
                    snapVisible: document.getElementById('snapToggle').offsetWidth > 0,
                    helpVisible: document.getElementById('shortcutHelpBtn').offsetWidth > 0
                };
            }""")
            print("header", width, head)
            assert not head["overflow"], (width, head)
            assert head["actionsRight"] <= head["zoomLeft"] + 1, (width, head)
            assert head["snapVisible"] and head["helpVisible"], (width, head)

        assert not errors, errors
        browser.close()
finally:
    stop_server(server)
print("PASS shortcuts and selection")
