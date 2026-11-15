"""Footage retrieval: local frame embeddings, text-to-moment search, UI and agent tool."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-footage-")
os.environ["CLIPACANVAS_EMBEDDING_PYTHON"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "python" / "Scripts" / "python.exe")
os.environ["CLIPACANVAS_EMBEDDING_ASSETS"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "assets")
os.environ["CLIPACANVAS_EMBEDDING_DEVICE"] = "cpu"

import serve
from serve import resolve_ffmpeg_exe, server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

SOURCE_IMAGE = ROOT / "output" / "uitest" / "embed" / "football.jpg"
ffmpeg = resolve_ffmpeg_exe()
errors = []

with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    red = tmp / "red.mp4"
    ball = tmp / "ball.mp4"
    blue = tmp / "blue.mp4"
    video = tmp / "moments.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=0xd01818:s=640x360:d=3:r=12",
         "-pix_fmt", "yuv420p", str(red)], check=True)
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-loop", "1", "-i", str(SOURCE_IMAGE), "-t", "3", "-r", "12",
         "-vf", "scale=640:360", "-pix_fmt", "yuv420p", str(ball)], check=True)
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-f", "lavfi", "-i", "color=c=0x1848d0:s=640x360:d=3:r=12",
         "-pix_fmt", "yuv420p", str(blue)], check=True)
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(red), "-i", str(ball), "-i", str(blue),
         "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0[out]",
         "-map", "[out]", "-r", "12", "-pix_fmt", "yuv420p", str(video)], check=True)
    print("test video seconds:", serve._probe_media_technical(video)["duration"])

    server, _thread = start_server()
    base = server_url(server)
    try:
        body = json.dumps({"query": "", "limit": 5}).encode()
        try:
            urllib.request.urlopen(urllib.request.Request(
                f"{base}/api/media/search", data=body, method="POST",
                headers={"Content-Type": "application/json"}))
            raise AssertionError("empty search query was accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 400, error.code

        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text)
                    if msg.type == "error" and "Failed to load resource" not in msg.text else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)
            page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
            page.set_input_files("#mediaInput", str(video))
            page.wait_for_function(
                "() => timelineState.assets.length === 1"
                " && timelineState.assets[0].analysis?.visual?.status === 'indexed'"
                " && (timelineState.assets[0].analysis.visual.frames || []).length >= 7",
                timeout=600000,
            )
            asset = page.evaluate("""() => {
                const a = timelineState.assets[0];
                return {id: a.id, name: a.name, url: a.url, frames: a.analysis.visual.frames.length};
            }""")
            print("indexed asset:", asset)
            assert asset["frames"] <= serve.VISUAL_FRAME_LIMIT, asset

            def search(query, limit=6):
                return page.evaluate("""async ([query, limit]) => {
                    const response = await fetch('/api/media/search', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({query, limit})
                    });
                    return response.json();
                }""", [query, limit])

            football = search("football ball on grass field", 6)
            print("football search:", json.dumps(football)[:600])
            assert football["ok"] and football["count"] >= 1, football
            best = football["results"][0]
            assert best["url"] == asset["url"], best
            assert 2.0 <= best["time"] <= 6.5, best
            assert best["score"] >= serve.VISUAL_SEARCH_MIN_SCORE, best
            assert best["thumb"].startswith("/api/media/frames/"), best
            thumb = urllib.request.urlopen(base + best["thumb"]).read()
            assert thumb[:2] == b"\xff\xd8" and len(thumb) > 500

            blue = search("solid blue screen", 6)
            print("blue search:", json.dumps(blue)[:400])
            assert blue["ok"] and blue["count"] >= 1, blue
            assert blue["results"][0]["time"] >= 5.5, blue["results"][:3]

            # UI search area renders moments and jumps/selects the asset.
            page.fill("#footageSearchInput", "football on grass")
            page.press("#footageSearchInput", "Enter")
            page.wait_for_function(
                "() => document.querySelectorAll('#footageSearchResults .footage-result').length >= 1",
                timeout=120000,
            )
            first_text = page.locator("#footageSearchResults .footage-result").first.inner_text()
            print("UI result:", first_text.replace("\n", " | "))
            assert "IN SOURCE" in first_text and "%" in first_text, first_text
            page.locator("#footageSearchResults .footage-result").first.click()
            page.wait_for_timeout(600)
            selected = page.evaluate("() => timelineState.selectedAssetId")
            assert selected == asset["id"], selected
            assert "FOOTAGE" in page.locator("#statusBar").inner_text()

            # Agent tool returns asset ids and timestamps, no upload.
            agent = page.evaluate("""async () => executeChatTool({
                name: 'search_footage', args: {query: 'football on grass', limit: 4}
            })""")
            print("agent search:", json.dumps(agent)[:500])
            assert agent["ok"] and agent["count"] >= 1, agent
            assert agent["results"][0]["assetId"] == asset["id"], agent["results"][0]
            assert isinstance(agent["results"][0]["timeSeconds"], (int, float)), agent["results"][0]

            OUT = ROOT / "output" / "playwright"
            OUT.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(OUT / "footage-search.png"))
            browser.close()
            assert not errors, errors
            print("FOOTAGE SEARCH CHECK: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
