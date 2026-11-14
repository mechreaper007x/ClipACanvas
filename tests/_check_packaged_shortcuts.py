"""Packaged exe: Premiere-style Ctrl+A selection and shortcut keys."""
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

DEBUG_PORT = 9431
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
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
    # Give this instance its own WebView2 profile so it can expose CDP even if
    # another ClipACanvas window is open.
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
            page.fill("#homeDialogInput", "SHORTCUT SPRINT")
            page.click("#homeDialogConfirm")
            page.wait_for_function("() => !projectHomeVisible && document.querySelectorAll('.et-row').length > 0", timeout=60000)
            page.wait_for_timeout(800)
            print("project opened:", page.evaluate("currentProjectName()"))

            seeded = page.evaluate("""() => {
              const clip = (name, start, duration, track) => ({
                id: newClipId(), name, code: '<!doctype html><html><body></body></html>',
                duration, start, track, explicitDuration: true, type: 'code',
                assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain',
                parentClipId: '', audioTrack: ''
              });
              timelineState.clips.length = 0;
              timelineState.clips.push(clip('ALPHA', 0, 2, 0), clip('BETA', 2, 2, 0), clip('GAMMA', 4, 2, 1));
              timelineState.layers = 2;
              timelineState.activeId = timelineState.clips[0].id;
              timelineState.selectedIds = [];
              timelineState.playhead = 0;
              timelineState.snapEnabled = true;
              saveTimelineState(true);
              renderLogicBoxes();
              updateStageTimeline();
              return {
                clips: timelineState.clips.length,
                shuttle: typeof startShuttle,
                snapButton: Boolean(document.getElementById('snapToggle')),
                helpButton: Boolean(document.getElementById('shortcutHelpBtn'))
              };
            }""")
            print("seeded:", seeded)
            assert seeded == {"clips": 3, "shuttle": "function", "snapButton": True, "helpButton": True}, seeded

            # Ctrl+A selects clips, never page text.
            page.evaluate("window.getSelection().removeAllRanges(); document.activeElement?.blur()")
            page.keyboard.press("Control+a")
            page.wait_for_timeout(250)
            selected = page.evaluate("""() => ({
                ids: timelineState.selectedIds.length,
                boxes: document.querySelectorAll('.logic-box.selected').length,
                text: window.getSelection().toString()
            })""")
            print("ctrl+a:", selected)
            assert selected == {"ids": 3, "boxes": 3, "text": ""}, selected
            page.screenshot(path=str(OUT / "packaged-shortcuts-select-all.png"))

            # Ctrl+K adds an edit instead of focusing chat.
            page.evaluate("setPlayhead(1); document.activeElement?.blur()")
            page.keyboard.press("Control+k")
            page.wait_for_timeout(250)
            split = page.evaluate("""() => ({
                clips: timelineState.clips.length,
                chatFocused: document.activeElement?.id === 'chatInput',
                pieces: timelineState.clips.filter(item => item.name.startsWith('ALPHA')).length
            })""")
            print("ctrl+k:", split)
            assert split["clips"] == 4 and split["pieces"] == 2 and not split["chatFocused"], split

            # S toggles snapping and the header shows it.
            page.keyboard.press("s")
            page.wait_for_timeout(200)
            snap = page.evaluate("""() => ({
                enabled: timelineState.snapEnabled,
                meta: document.getElementById('timelineMeta').textContent
            })""")
            print("snap:", snap)
            assert snap["enabled"] is False and "SNAP OFF" in snap["meta"], snap
            page.keyboard.press("s")

            # J / L shuttle and shortcut sheet.
            page.evaluate("setPlayhead(1.5); document.activeElement?.blur()")
            page.keyboard.press("l")
            page.wait_for_timeout(300)
            playing = page.evaluate("() => ({ playing: playbackState.playing, at: timelineState.playhead })")
            page.keyboard.press("k")
            print("play:", playing)
            assert playing["playing"] and playing["at"] > 1.5, playing

            page.click("#shortcutHelpBtn")
            page.wait_for_timeout(250)
            assert page.locator("#shortcutHelpModal").is_visible()
            assert "PREMIERE-STYLE" in page.locator("#shortcutHelpModal").inner_text()
            page.screenshot(path=str(OUT / "packaged-shortcuts-sheet.png"))
            page.keyboard.press("Escape")
            page.wait_for_timeout(200)
            assert not page.locator("#shortcutHelpModal").is_visible()
            assert not errors, errors
            browser.close()
    finally:
        log.close()
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)

print("PASS packaged shortcuts")
