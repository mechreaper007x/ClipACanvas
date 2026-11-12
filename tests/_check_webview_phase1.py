"""Phase 1 in the real desktop WebView2: analysis inspector, zoom presets, overlay attachment."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import resolve_ffmpeg_exe

from playwright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()
DEBUG_PORT = 9413
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
OVERLAY_CODE = '<!doctype html><html><body style="margin:0;background:transparent"></body></html>'

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    video = tmp / "motion.mp4"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=1.2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    proc = subprocess.Popen([sys.executable, str(ROOT / "desktop_app.py")],
                            cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for _ in range(160):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
            page = None
            for _ in range(60):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "desktop page not found"
            page.wait_for_function("() => typeof timelineState !== 'undefined' && typeof projectOps === 'object'", timeout=45000)
            page.wait_for_timeout(800)
            errors = []
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            print("webview:", page.evaluate("navigator.userAgent"))

            page.set_input_files("#mediaInput", str(video))
            page.wait_for_function(
                "() => timelineState.assets.length === 1 && timelineState.assets[0].analysis?.technical",
                timeout=45000,
            )
            asset_id = page.evaluate("timelineState.assets[0].id")
            page.locator(f'.dock-bin[data-asset-id="{asset_id}"]').click()
            page.wait_for_timeout(400)
            assert page.locator("#miAnalysis").is_visible(), "analysis inspector missing in WebView2"
            grid = page.locator("#miAnalysisGrid").inner_text()
            print("analysis inspector:", grid.replace("\n", " | "))
            assert "320×180" in grid and "24.00" in grid, grid

            page.locator("#timelineZoomInput").fill("400")
            page.locator("#timelineZoomInput").press("Tab")
            page.wait_for_timeout(250)
            assert abs(page.evaluate("timelineView.zoom") - 4) < 0.001
            assert page.locator("#timelineZoomRange").input_value() == "400"
            print("webview zoom:", page.evaluate("timelineView.zoom"))

            seeded = page.evaluate(f"""() => {{
                timelineState.clips = [];
                timelineState.layers = 1;
                const parent = projectOps.insertAsset('{asset_id}', {{track: 0, at: 0.5}});
                const overlay = projectOps.createComposition({{
                    name: 'WEB TITLE', code: '{OVERLAY_CODE}', track: 1, start: 0.5, duration: 1.2
                }});
                const attached = projectOps.attachOverlay(overlay.clipId, parent.clipId);
                projectOps.selectClip(overlay.clipId);
                return {{parent: parent.clipId, overlay: overlay.clipId, attached}};
            }}""")
            print("webview overlay:", seeded)
            assert seeded["attached"]["ok"], seeded
            page.wait_for_timeout(400)
            assert page.locator("#ciParentField").is_visible(), "attachment row missing in WebView2"
            assert "motion" in page.locator("#ciParent").inner_text()
            inspector = page.evaluate("projectOps.getClipContext('" + seeded["overlay"] + "')")
            assert inspector["parent"]["id"] == seeded["parent"], inspector
            page.screenshot(path=str(OUT / "webview-phase1.png"))
            assert not errors, errors
            print("WEBVIEW2 PHASE 1 CHECK: OK")
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=10)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
        time.sleep(1)
