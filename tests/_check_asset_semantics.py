"""Asset content semantics are local only: EmbeddingGemma tags, shots, notes."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-semantics-")
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

analyze_calls = []
original_analyze = serve.analyze_media_file


def spy_analyze(filename, refresh=False):
    analyze_calls.append(bool(refresh))
    return original_analyze(filename, refresh=refresh)


serve.analyze_media_file = spy_analyze

llm_calls = []


def no_hosted_llm(*args, **kwargs):
    llm_calls.append(args[0] if args else "")
    raise AssertionError("Content analysis must not call a hosted provider.")


serve.ClipACanvasHandler._llm_http_post = staticmethod(no_hosted_llm)

errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    image = tmp / "football.jpg"
    video = tmp / "football-loop.mp4"
    shutil.copy(SOURCE_IMAGE, image)
    subprocess.run(
        [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(image),
         "-t", "2", "-r", "12", "-pix_fmt", "yuv420p", "-vf", "scale=640:-2", str(video)],
        capture_output=True, check=True,
    )

    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text)
                    if msg.type == "error" and "Failed to load resource" not in msg.text else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)
            page.set_input_files("#mediaInput", [str(image), str(video)])
            page.wait_for_function(
                "() => timelineState.assets.length === 2"
                " && timelineState.assets.every(a => a.analysis?.technical)"
                " && timelineState.assets.every(a => a.analysis?.visual?.status === 'indexed')",
                timeout=420000,
            )
            assets = page.evaluate("""() => Object.fromEntries(timelineState.assets.map(a => [a.name, {
                id: a.id, name: a.name, url: a.url, kind: a.kind, analysis: a.analysis
            }]))""")
            image_asset = assets["football"]
            video_asset = assets["football-loop"]
            for name, asset in (("image", image_asset), ("video", video_asset)):
                visual = asset["analysis"]["visual"]
                print(name, "| status:", visual["status"], "| device:", visual.get("device"),
                      "| description:", visual.get("description"))
                print("  tags:", [tag["label"] for tag in visual.get("tags") or []])
                assert visual["provider"] == "embeddinggemma-2", visual
                assert visual["tags"], visual
                assert visual.get("description"), visual
                assert "Local visual index:" in visual["description"], visual["description"]
                assert asset["analysis"]["semantic"]["status"] == "not_analyzed"
            assert "Still image" in image_asset["analysis"]["visual"]["description"]
            assert len(video_asset["analysis"]["visual"]["frames"]) >= 1

            # Inspector: local summary and tags, no upload UI anywhere.
            image_id = image_asset["id"]
            page.locator(f'.dock-bin[data-asset-id="{image_id}"]').click()
            page.wait_for_timeout(500)
            status_text = page.locator("#miContentStatus").inner_text()
            print("content status:", status_text)
            assert "LOCAL" in status_text and "EMBEDDINGGEMMA 2" in status_text, status_text
            summary_text = page.locator("#miSemanticText").inner_text()
            assert "Local visual index:" in summary_text, summary_text
            assert page.locator("#miTags span").count() >= 1
            assert page.locator("#miConsentRow").count() == 0
            assert "NO UPLOAD" in page.locator("#miAnalyzeHint").inner_text()

            # ANALYZE CONTENT forces a local re-index and spends no provider call.
            analyze_calls.clear()
            page.click("#miAnalyzeToggle")
            page.wait_for_function(
                "() => document.getElementById('miAnalyzeHint').textContent.includes('INDEX SAVED')",
                timeout=180000,
            )
            assert analyze_calls and analyze_calls[-1] is True, analyze_calls
            assert not llm_calls, llm_calls
            assert page.evaluate(
                "() => timelineState.assets.find(a => a.name === 'football').analysis.visual.status"
            ) == "indexed"

            # The hosted media-analysis endpoint is gone.
            status_code = page.evaluate("""async () => {
                const response = await fetch('/api/media/semantic', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: '/media/none.jpg', consent: true})
                });
                return response.status;
            }""")
            assert status_code == 404, status_code

            # Human note persists separately from the local index.
            page.fill("#miUserNote", "Football on grass for the opening shot")
            page.click("#miUserNoteSave")
            page.wait_for_timeout(300)
            assert "USER NOTE" in page.locator("#miSemanticNote").inner_text()
            note_state = page.evaluate(
                "() => timelineState.assets.find(a => a.name === 'football').analysis"
            )
            assert "Football on grass" in note_state["user"]["description"], note_state["user"]
            assert note_state["visual"]["tags"], note_state

            # Agent tools search and read the local index.
            def tool(name, args):
                return page.evaluate(
                    "async ([name, args]) => executeChatTool({name, args})", [name, args]
                )

            search = tool("search_assets", {"query": "football"})
            assert search["ok"] and search["count"] >= 1, search
            assert any(item["id"] == image_id for item in search["assets"]), search
            manifest = tool("get_asset_analysis", {"assetId": image_id})["manifest"]
            assert manifest["visual"]["status"] == "indexed"
            assert manifest["visual"]["description"]
            assert [tag["label"] for tag in manifest["visual"]["tags"]]

            # Reload keeps the local description, tags and the human note.
            page.reload(wait_until="load")
            page.wait_for_timeout(1600)
            page.locator(f'.dock-bin[data-asset-id="{image_id}"]').click()
            page.wait_for_timeout(500)
            assert "LOCAL" in page.locator("#miContentStatus").inner_text()
            assert "Local visual index:" in page.locator("#miSemanticText").inner_text()
            assert page.locator("#miTags span").count() >= 1
            assert "USER NOTE" in page.locator("#miSemanticNote").inner_text()
            OUT = ROOT / "output" / "playwright"
            OUT.mkdir(parents=True, exist_ok=True)
            page.locator("#miContentBlock").scroll_into_view_if_needed()
            page.screenshot(path=str(OUT / "asset-semantics.png"))

            browser.close()
            assert not errors, errors
            assert not llm_calls, llm_calls
            print("ASSET SEMANTICS CHECK: OK")
    finally:
        serve.analyze_media_file = original_analyze
        try:
            server.shutdown()
        except Exception:
            pass
