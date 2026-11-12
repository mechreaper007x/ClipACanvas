"""Packaged WebView2 check: Project Home, durable project state + 1080p A/V export.

Launches dist/ClipACanvas.exe twice with an isolated data dir and CDP enabled.
First run creates a project from Project Home, builds a two-image film with two
audio lanes, renders 1920x1080 and writes the MP4. Second run verifies the app
returns to Project Home and the project (name, clips, assets) reopens intact
without any localStorage carry-over.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
EXE = ROOT / "dist" / "ClipACanvas.exe"
PORT = 9333

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

import psutil
from serve import resolve_ffmpeg_exe

ffmpeg = resolve_ffmpeg_exe()


def clipacanvas_pids() -> set[int]:
    return {
        p.pid for p in psutil.process_iter(["pid", "name"])
        if p.info["name"] == "ClipACanvas.exe"
    }


def kill_all() -> None:
    for pid in clipacanvas_pids():
        try:
            psutil.Process(pid).kill()
        except Exception:
            pass
    time.sleep(1.5)


def launch(data_dir: Path) -> subprocess.Popen:
    env = os.environ.copy()
    env["CLIPACANVAS_KEYS_DIR"] = str(data_dir)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        f"--remote-debugging-port={PORT} --remote-allow-origins=*"
    )
    return subprocess.Popen([str(EXE)], env=env)


def attach(pw):
    deadline = time.time() + 60
    last = None
    while time.time() < deadline:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}", timeout=5000)
            pages = [page for context in browser.contexts for page in context.pages]
            page = next((p for p in pages if "clipacanvas.html" in p.url), None)
            if page:
                page.wait_for_timeout(1500)
                return browser, page
        except Exception as exc:
            last = exc
        time.sleep(2)
    raise RuntimeError(f"could not attach to packaged app: {last}")


def probe_pixel(path: Path, seconds: float) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", f"{seconds:.3f}", "-i", str(path),
         "-frames:v", "1", "-vf", "scale=1:1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return out[0], out[1], out[2]


def mean_volume(path: Path, start: float, duration: float) -> float:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{duration:.3f}",
         "-i", str(path), "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    match = re.search(r"mean_volume:\s*(-?[\d.]+) dB", result.stderr)
    assert match, result.stderr[-800:]
    return float(match.group(1))


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    data_dir = tmp / "appdata"
    stills = []
    for name, color in (("a", "0xd01818"), ("b", "0x1848d0")):
        path = tmp / f"{name}.png"
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", f"color=c={color}:s=640x360:d=1",
             "-frames:v", "1", str(path)],
            capture_output=True, check=True,
        )
        stills.append(path)
    music = tmp / "music.mp3"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=6",
         "-af", "volume=0.6", "-b:a", "128k", str(music)],
        capture_output=True, check=True,
    )
    sfx = tmp / "sfx.mp3"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=880:duration=1",
         "-b:a", "128k", str(sfx)],
        capture_output=True, check=True,
    )

    kill_all()
    movie = ROOT / "output" / "uitest" / "renders" / "packaged-film-1080p.mp4"
    movie.parent.mkdir(parents=True, exist_ok=True)
    proc = launch(data_dir)
    try:
        with sync_playwright() as pw:
            browser, page = attach(pw)
            assert page.evaluate("isDesktopShell()"), "packaged page is not the desktop shell"
            page.wait_for_function("() => document.getElementById('projectHome').hidden === false", timeout=30000)
            print("launched into Project Home")
            page.click("#homeNew")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            page.fill("#homeDialogInput", "Packaged Film")
            page.click("#homeDialogConfirm")
            page.wait_for_function("() => document.getElementById('projectHome').hidden === true", timeout=30000)
            page.wait_for_timeout(800)
            assert page.evaluate("activeProject && activeProject.id === 'packaged-film'"), "project id missing"
            assert page.evaluate("typeof undoTimeline === 'function' && typeof redoTimeline === 'function'"), "undo not packaged"
            assert page.evaluate("Boolean(document.getElementById('projectLibrary') && document.getElementById('boxUndo'))"), "project library/undo UI missing"
            print("attached:", page.title())

            page.set_input_files("#mediaInput", [str(p) for p in stills] + [str(music), str(sfx)])
            page.wait_for_function("() => timelineState.assets.length === 4", timeout=120000)
            page.evaluate("""() => {
                setResolutionValue('1920x1080');
                const fps = document.getElementById('frameRate');
                fps.value = '30';
                fps.dispatchEvent(new Event('change', { bubbles: true }));
                const a = timelineState.assets.find(asset => asset.name === 'a');
                const b = timelineState.assets.find(asset => asset.name === 'b');
                const music = timelineState.assets.find(asset => asset.name === 'music');
                const sfx = timelineState.assets.find(asset => asset.name === 'sfx');
                timelineState.clips = [];
                timelineState.transitions = [];
                timelineState.layers = 1;
                const first = insertAssetClip(a, { at: 0, duration: 3, track: 0, mode: 'overwrite' });
                const second = insertAssetClip(b, { at: 3, duration: 3, track: 0, mode: 'overwrite' });
                insertAssetClip(music, { at: 0, duration: 6, audioTrack: 'A2' });
                insertAssetClip(sfx, { at: 1.5, duration: 1, audioTrack: 'A3' });
                projectOps.setAudioTrackMix('A2', { volume: 0.3 });
                projectOps.setAudioTrackMix('A3', { volume: 1.0 });
                projectOps.addTransition({ fromClipId: first.id, toClipId: second.id, type: 'dissolve', duration: 1.0 });
                setFrameRange(0, 6);
                document.getElementById('projectName').value = 'PACKAGED FILM';
                document.getElementById('projectName').dispatchEvent(new Event('change', { bubbles: true }));
                return timelineState.clips.length;
            }""")
            page.wait_for_timeout(2500)
            page.click("#boxUndo")
            page.wait_for_function("() => timelineState.transitions.length === 0", timeout=5000)
            page.click("#boxRedo")
            page.wait_for_function("() => timelineState.transitions.length === 1", timeout=5000)
            page.wait_for_timeout(1200)
            deadline = time.time() + 20
            autosave = None
            while time.time() < deadline:
                candidates = list((data_dir / "projects").glob("*.autosave.ccproj.json"))
                if candidates:
                    try:
                        saved = json.loads(candidates[0].read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        saved = None
                    if saved and saved.get("projectName") == "PACKAGED FILM" \
                            and len(saved["timeline"]["clips"]) == 4:
                        autosave = candidates[0]
                        break
                page.wait_for_timeout(250)
            assert autosave is not None, "per-project autosave file missing"
            saved = json.loads(autosave.read_text(encoding="utf-8"))
            print("autosave:", autosave.name, "name:", saved.get("projectName"),
                  "clips:", len(saved["timeline"]["clips"]))
            assert saved.get("projectId") == "packaged-film", saved.get("projectId")
            page.evaluate("saveProjectToLibrary()")
            page.wait_for_function(
                "() => document.querySelectorAll('#projectLibraryList .project-row').length >= 1",
                timeout=15000,
            )
            print("library rows:", page.evaluate("document.querySelectorAll('#projectLibraryList .project-row').length"))

            page.click("#btnConvert")
            deadline = time.time() + 420
            while time.time() < deadline:
                status = page.locator("#statusBar").inner_text()
                if "ready" in status.lower() and not page.locator("#btnDownload").is_disabled():
                    break
                if "error" in status.lower():
                    raise AssertionError(f"render failed: {status}")
                page.wait_for_timeout(1000)
            else:
                raise AssertionError("render timed out")
            print("render status:", page.locator("#statusBar").inner_text().encode("ascii", "replace").decode())
            b64 = page.evaluate("""async () => {
                const response = await fetch(resultVideoUrl);
                const buffer = await response.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let text = '';
                for (let i = 0; i < bytes.length; i += 0x8000) {
                    text += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
                }
                return btoa(text);
            }""")
            import base64
            movie.write_bytes(base64.b64decode(b64))
            print("movie:", movie.stat().st_size, "bytes")
            streams = subprocess.run([ffmpeg, "-hide_banner", "-i", str(movie)],
                                     capture_output=True, text=True).stderr
            print(streams[-500:])
            assert "1920x1080" in streams, "not a 1080p export"
            assert "Audio:" in streams, "export has no audio track"
            red = probe_pixel(movie, 1.0)
            blue = probe_pixel(movie, 4.5)
            print("pixels red/blue:", red, blue)
            assert red[0] > 150 and red[2] < 90, red
            assert blue[2] > 130 and blue[0] < 90, blue
            music_only = mean_volume(movie, 0.5, 0.5)
            music_sfx = mean_volume(movie, 1.8, 0.4)
            print("mean volume music:", music_only, "music+sfx:", music_sfx)
            assert music_only > -45, music_only
            assert music_sfx > music_only + 3, (music_sfx, music_only)
            browser.close()
    finally:
        kill_all()

    # Second launch: the app must open Project Home; the project is intact.
    proc = launch(data_dir)
    try:
        with sync_playwright() as pw:
            browser, page = attach(pw)
            page.wait_for_function("() => document.getElementById('projectHome').hidden === false", timeout=60000)
            page.wait_for_function(
                "() => document.querySelectorAll('.home-card').length >= 1", timeout=30000,
            )
            assert page.evaluate("activeProject === null"), "relaunch must not auto-open a project"
            page.click('.home-card[data-project-id="packaged-film"]')
            page.wait_for_function(
                "() => timelineState.clips.length === 4 && timelineState.assets.length === 4",
                timeout=60000,
            )
            state = page.evaluate("""() => ({
                name: document.getElementById('projectName').value,
                clips: timelineState.clips.length,
                assets: timelineState.assets.length,
                lanes: timelineState.clips.filter(c => c.type === 'audio').map(c => c.audioTrack).sort(),
                bins: document.getElementById('binsCount').textContent,
                stored: Boolean(localStorage.getItem('clipacanvas.timeline.v1')),
                homeHidden: document.getElementById('projectHome').hidden
            })""")
            print("relaunch state:", state)
            assert state["homeHidden"] is True, state
            assert state["name"] == "PACKAGED FILM", state
            assert state["clips"] == 4 and state["assets"] == 4, state
            assert state["lanes"] == ["A2", "A3"], state
            assert state["bins"] == "4 ASSETS", state
            assert state["stored"] is True, "webview profile did not persist localStorage"
            browser.close()
    finally:
        kill_all()

    print("saved movie:", movie)
    print("PASS packaged persistence + render")
