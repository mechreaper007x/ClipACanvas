"""Capture the workspace at the reference viewports and report layout overflow.

Usage:
    python tests/_viz_workspace.py [tag] [base_url]

Without a base_url an isolated server is started. Screenshots land in
output/playwright/workspace-<tag>-<width>.png.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

TAG = sys.argv[1] if len(sys.argv) > 1 else "latest"
BASE = sys.argv[2] if len(sys.argv) > 2 else None
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
VIEWPORTS = [(1664, 916), (1440, 900), (1280, 720)]


def start_isolated():
    os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-viz-")
    from serve import server_url, start_server
    server, _thread = start_server()
    return server_url(server), (lambda: None)


stop = lambda: None
if not BASE:
    BASE, _stop = start_isolated()

errors = []
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1664, "height": 916})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(f"{BASE}/clipacanvas.html", wait_until="load")
    page.wait_for_timeout(1500)

    # Give the timeline a multi-scene project so the workspace is representative.
    page.evaluate("""() => {
        const demo = [
            '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:radial-gradient(circle at 50% 35%,#12331f,#050805 70%);display:grid;place-items:center;font:700 54px/1 \\'IBM Plex Mono\\',monospace;color:#c8ff00;letter-spacing:2px}span{opacity:.92}</style></head><body><span>THE END</span></body></html>',
            '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:linear-gradient(140deg,#101820,#050608);display:grid;place-items:center;font:600 34px/1.2 \\'IBM Plex Mono\\',monospace;color:#e9e3d3;text-align:center}</style></head><body><span>SECOND<br>SCENE</span></body></html>'
        ];
        const first = timelineState.clips[0];
        if (first && first.type === 'code') {
            first.name = 'SCENE 01';
            first.duration = 6;
        }
        if (timelineState.clips.length === 1 && typeof addLogicClip === 'function') {
            addLogicClip({ duplicate: true });
            const clips = timelineState.clips.filter(c => c.type === 'code');
            if (clips[1]) clips[1].name = 'SCENE 02';
        }
        if (first) first.code = demo[0];
        const second = timelineState.clips.filter(c => c.type === 'code')[1];
        if (second) second.code = demo[1];
        timelineState.activeId = timelineState.clips[0].id;
        timelineState.playhead = 1.5;
        saveTimelineState(true);
        renderLogicBoxes();
        renderProjectBin();
        applyActiveClipToEditor({ preview: true });
        updateStageTimeline();
    }""")
    page.wait_for_timeout(900)

    for width, height in VIEWPORTS:
        page.set_viewport_size({"width": width, "height": height})
        page.wait_for_timeout(700)
        shot = OUT / f"workspace-{TAG}-{width}.png"
        page.screenshot(path=str(shot))
        metrics = page.evaluate("""() => {
            const rect = (sel) => {
                const el = document.querySelector(sel);
                if (!el) return null;
                const r = el.getBoundingClientRect();
                return {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)};
            };
            const doc = document.documentElement;
            return {
                viewport: [innerWidth, innerHeight],
                overflowX: doc.scrollWidth - innerWidth,
                overflowY: doc.scrollHeight - innerHeight,
                header: rect('.command-bar'),
                left: rect('.code-pane'),
                stage: rect('.stage-pane'),
                right: rect('.right-pane'),
                dock: rect('.transport-dock'),
                timeline: rect('.editor-timeline'),
                bin: rect('#projectBin'),
                monitor: rect('#previewContainer'),
                preview: rect('#previewStage'),
                timelineTime: document.getElementById('timelineTime')?.textContent,
                monitorTime: document.getElementById('monitorTime')?.textContent,
                playhead: timelineState.playhead,
                emptyScene: document.getElementById('emptyScene')?.classList.contains('visible'),
            };
        }""")
        print(width, json.dumps(metrics))
        print("saved", shot)

    if errors:
        print("CONSOLE ERRORS:", errors[:10])
    else:
        print("no console errors")
    browser.close()

print("RESULT:", "FAIL" if errors else "PASS")
