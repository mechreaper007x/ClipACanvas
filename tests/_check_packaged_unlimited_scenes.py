"""Packaged exe: scenes and the timeline are not capped at 40 clips or 60 seconds."""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

DEBUG_PORT = 9432
EXE = ROOT / "dist" / "ClipACanvas.exe"

assert EXE.exists(), "build dist/ClipACanvas.exe first"
print("exe:", EXE.stat().st_size, "bytes", time.strftime("%Y-%m-%d %H:%M", time.localtime(EXE.stat().st_mtime)))

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    appdata.mkdir(parents=True)
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(appdata)
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["APPDATA"] = str(tmp / "appdata-webview")
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    log_path = tmp / "packaged.log"
    log = open(log_path, "wb")
    proc = subprocess.Popen([str(EXE)], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(360):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("packaged app did not expose the CDP port")
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
            page = None
            for _ in range(120):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "packaged page not found"
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.wait_for_function("() => typeof timelineState !== 'undefined'", timeout=60000)
            page.wait_for_selector("#homeNew", timeout=30000)
            page.click("#homeNew")
            page.wait_for_selector("#homeDialogInput", timeout=15000)
            page.fill("#homeDialogInput", "UNLIMITED SPRINT")
            page.click("#homeDialogConfirm")
            page.wait_for_function("() => !projectHomeVisible && document.querySelectorAll('.et-row').length > 0", timeout=60000)
            page.wait_for_timeout(800)

            result = page.evaluate("""() => {
              const initial = {
                span: timelineViewSpan(),
                total: timelineTotalSeconds(),
                zoomWidth: document.getElementById('timelineZoomInput').getBoundingClientRect().width
              };
              timelineState.clips.length = 0;
              timelineState.transitions.length = 0;
              const code = '<!doctype html><html><body style="margin:0;background:#101010"></body></html>';
              const failures = [];
              for (let i = 0; i < 45; i += 1) {
                const created = createSceneClip({ name: `S${i + 1}`, code, duration: 4 });
                if (created.error) failures.push(created.error);
              }
              const dup = projectOps.duplicateClip(timelineState.clips[timelineState.clips.length - 1].id);
              const track = timelineState.clips.filter(clip => clip.track === 0).sort((a, b) => a.start - b.start);
              const transition = projectOps.addTransition({
                fromClipId: track[40].id, toClipId: track[41].id, type: 'dissolve'
              });
              saveTimelineState(true);
              const plan = buildTimelineRenderPlan();
              setTimelineZoom(0.5);
              const zoom50 = { span: timelineViewSpan(), start: timelineView.start, zoom: timelineView.zoom };
              fitTimelineView();
              return {
                initial,
                failures,
                dup: Boolean(dup.ok),
                transition: Boolean(transition.ok),
                clips: timelineState.clips.length,
                total: timelineTotalSeconds(),
                planEnd: plan?.end ?? null,
                zoom50,
                inputs: {
                  renderEndMax: document.getElementById('renderEnd').max,
                  customMax: document.getElementById('customClipLength').max
                }
              };
            }""")
            print("packaged unlimited:", result)
            assert not result["failures"], result
            assert result["dup"] and result["transition"], result
            assert result["clips"] == 46, result
            assert result["total"] == 184 and result["planEnd"] == 184, result
            assert abs(result["initial"]["span"] - 30) < 0.01, result["initial"]
            assert result["initial"]["zoomWidth"] >= 56, result["initial"]
            assert abs(result["zoom50"]["span"] - 368) < 0.01 and result["zoom50"]["start"] == 0, result["zoom50"]
            assert result["inputs"]["renderEndMax"] == "86400", result
            assert result["inputs"]["customMax"] == "86400", result
            assert not errors, errors
            browser.close()
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()

print("PASS packaged unlimited scenes")
