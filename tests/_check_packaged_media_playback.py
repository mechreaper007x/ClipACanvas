"""Packaged exe: media playback mounts the preview once per clip instead of reloading it."""
import os
import shutil
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

DEBUG_PORT = 9433
EXE = ROOT / "dist" / "ClipACanvas.exe"
SAMPLE = ROOT / "output" / "mcp-smoke.mp4"

assert EXE.exists(), "build dist/ClipACanvas.exe first"
assert SAMPLE.exists(), "sample video missing"

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    (appdata / "media").mkdir(parents=True)
    media_name = "media-0123456789abcdef0123.mp4"
    shutil.copyfile(SAMPLE, appdata / "media" / media_name)
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
            page.fill("#homeDialogInput", "PLAYBACK SPRINT")
            page.click("#homeDialogConfirm")
            page.wait_for_function("() => !projectHomeVisible && document.querySelectorAll('.et-row').length > 0", timeout=60000)
            page.wait_for_timeout(800)

            result = page.evaluate("""async (mediaName) => {
              const url = '/media/' + mediaName;
              const now = new Date().toISOString();
              const asset = { id: 'asset-sample', name: 'sample.mp4', kind: 'video', url,
                duration: 2, addedAt: Date.now(), analysis: null, analysisError: '' };
              const doc = {
                format: 'clipacanvas-project', version: 1,
                projectId: activeProject?.id || '', projectName: currentProjectName(), savedAt: now,
                timeline: {
                  clips: [{ id: 'clip-video', name: 'VIDEO', code: '', duration: 1.8, start: 0,
                    track: 0, explicitDuration: true, type: 'video', assetId: asset.id, mediaUrl: url,
                    mediaName: asset.name, sourceIn: 0, fit: 'contain', parentClipId: '', audioTrack: '' }],
                  transitions: [], audioTracks: defaultAudioTracks(), layers: 1,
                  playhead: 0, assets: [asset]
                }
              };
              applyProjectPayload(doc);
              renderLogicBoxes();
              updateStageTimeline();
              window.__previewMounts = 0;
              const originalPreview = previewMediaSource;
              window.previewMediaSource = function (source) {
                window.__previewMounts += 1;
                return originalPreview(source);
              };
              setPlayhead(0);
              startShuttle(1);
              await new Promise(resolve => setTimeout(resolve, 1400));
              const playing = { at: timelineState.playhead, mounts: window.__previewMounts };
              stopPlayback(false);
              return { docClips: timelineState.clips.length, playing, errors: [] };
            }""", media_name)
            print("packaged playback:", result)
            assert result["docClips"] == 1, result
            assert result["playing"]["at"] > 0.6, result
            assert result["playing"]["mounts"] <= 2, result
            assert not errors, errors
            browser.close()
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                       capture_output=True, check=False)
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()

print("PASS packaged media playback")
