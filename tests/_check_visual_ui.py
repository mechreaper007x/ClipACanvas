"""Media inspector shows the local visual index tags and motion."""
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
DATA = Path(tempfile.mkdtemp(prefix="cc-visual-ui-"))
os.environ["CLIPACANVAS_KEYS_DIR"] = str(DATA)
os.environ["CLIPACANVAS_EMBEDDING_PYTHON"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "python" / "Scripts" / "python.exe")
os.environ["CLIPACANVAS_EMBEDDING_ASSETS"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "litert" / "assets")
os.environ["CLIPACANVAS_EMBEDDING_DEVICE"] = "cpu"

import serve
from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

media_dir = DATA / "media"
media_dir.mkdir()
shutil.copy(ROOT / "output" / "uitest" / "embed" / "football.jpg",
            media_dir / "media-0123456789abcdef0123.jpg")
manifest = serve.analyze_media_file("media-0123456789abcdef0123.jpg")
assert manifest["visual"]["status"] == "indexed", manifest["visual"]

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1664, "height": 916})
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1000)
        page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
        page.evaluate("""manifest => {
            const asset = {
                id: 'asset-visual-ui', name: 'FOOTBALL', kind: 'image',
                url: '/media/media-0123456789abcdef0123.jpg', duration: 4,
                addedAt: Date.now(), analysis: manifest, analysisError: ''
            };
            timelineState.assets = [asset];
            saveTimelineState(true);
            renderProjectBin();
            showMediaInspectorForAsset(asset);
        }""", manifest)
        page.wait_for_timeout(600)
        state = page.evaluate("""() => ({
            tags: document.getElementById('miTags')?.innerText || '',
            status: document.getElementById('miContentStatus')?.innerText || '',
            summary: document.getElementById('miSemanticText')?.innerText || '',
            shots: document.getElementById('miShotsMeta')?.innerText || ''
        })""")
        print("inspector:", state)
        assert "football" in state["tags"].lower(), state
        assert "LOCAL" in state["status"], state
        assert "EMBEDDINGGEMMA 2" in state["status"], state
        assert "Local visual index:" in state["summary"], state
        page.screenshot(path=str(ROOT / "output" / "playwright" / "visual-index-inspector.png"))
        print("PASS visual index UI")
        browser.close()
finally:
    stop_server(server)
