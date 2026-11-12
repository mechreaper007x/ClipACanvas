"""Asset intelligence: technical manifest, cache, inspector and agent tools."""
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import resolve_ffmpeg_exe, server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()
errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    image = tmp / "still.png"
    video = tmp / "motion.mp4"
    audio = tmp / "tone.mp3"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
                    "-frames:v", "1", str(image)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=1.2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)

    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)
            page.set_input_files("#mediaInput", [str(image), str(video), str(audio)])
            page.wait_for_function(
                "() => timelineState.assets.length === 3 && timelineState.assets.every(a => a.analysis?.technical)",
                timeout=45000,
            )
            assets = page.evaluate("""() => Object.fromEntries(timelineState.assets.map(a => [a.kind, {
                id: a.id, name: a.name, url: a.url, analysis: a.analysis
            }]))""")
            video_asset = assets["video"]["analysis"]["technical"]
            image_asset = assets["image"]["analysis"]["technical"]
            audio_asset = assets["audio"]["analysis"]["technical"]
            print("video technical:", video_asset)
            print("image technical:", image_asset)
            print("audio technical:", audio_asset)
            assert video_asset["width"] == 320 and video_asset["height"] == 180, video_asset
            assert abs(video_asset["fps"] - 24) < 0.1, video_asset
            assert abs(video_asset["duration"] - 1.2) < 0.1, video_asset
            assert video_asset["videoCodec"] == "h264"
            assert image_asset["width"] == 400 and image_asset["height"] == 225, image_asset
            assert image_asset["duration"] is None, image_asset
            assert audio_asset["audioCodec"] == "mp3" and audio_asset["sampleRate"] == 44100, audio_asset
            assert audio_asset["channels"] == 1, audio_asset

            # Inspector shows the real technical block, no invented semantic data.
            video_id = assets["video"]["id"]
            page.locator(f'.dock-bin[data-asset-id="{video_id}"]').click()
            page.wait_for_timeout(400)
            assert page.locator("#miAnalysis").is_visible(), "analysis block hidden"
            grid = page.locator("#miAnalysisGrid").inner_text()
            print("inspector analysis:", grid.replace("\n", " | "))
            assert "320×180" in grid and "24.00" in grid and "h264" in grid, grid
            semantic_note = page.locator("#miSemanticNote").inner_text()
            assert "NOT RUN" in semantic_note, semantic_note

            def tool(name, args):
                return page.evaluate(
                    "async ([name, args]) => executeChatTool({name, args})", [name, args]
                )

            search = tool("search_assets", {"query": "motion"})
            assert search["ok"] and search["count"] == 1, search
            summary = search["assets"][0]
            assert summary["resolution"] == "320x180" and summary["semanticStatus"] == "not_analyzed", summary
            assert set(summary) == {"id", "name", "type", "durationSeconds", "resolution", "fps",
                                    "videoCodec", "audioCodec", "analyzed", "semanticStatus", "description"}

            analysis = tool("get_asset_analysis", {"assetId": video_id})
            assert analysis["ok"] and analysis["semanticAvailable"] is False, analysis
            assert analysis["manifest"]["semantic"]["status"] == "not_analyzed"
            assert abs(analysis["manifest"]["technical"]["duration"] - 1.2) < 0.1
            missing = tool("get_asset_analysis", {"assetId": "missing-asset"})
            assert missing["ok"] is False

            updated = tool("update_asset_description", {
                "assetId": video_id,
                "description": "Blue test clip for the title overlay",
                "notes": "Recorded in the studio",
            })
            assert updated["ok"], updated
            assert "USER NOTE" in page.locator("#miSemanticNote").inner_text()
            stored = page.evaluate(
                "() => timelineState.assets.find(a => a.kind === 'video').analysis.user"
            )
            assert "Blue test clip" in stored["description"] and stored["updatedAt"] > 0, stored
            preserved = page.evaluate(
                "() => timelineState.assets.find(a => a.kind === 'video').analysis.semantic.status"
            )
            assert preserved == "not_analyzed"

            # Cache: the second request returns the identical manifest.
            cache = page.evaluate("""async () => {
                const asset = timelineState.assets.find(a => a.kind === 'video');
                const call = async () => {
                    const response = await fetch('/api/media/analyze', {
                        method: 'POST', headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({url: asset.url})
                    });
                    return response.json();
                };
                const a = await call();
                const b = await call();
                return {same: JSON.stringify(a) === JSON.stringify(b), at: a.manifest.analyzer.analyzedAt};
            }""")
            print("cache:", cache)
            assert cache["same"], cache

            bad_request = urllib.request.Request(
                f"{base}/api/media/analyze",
                data=json.dumps({"url": "/media/media-00000000000000000000.mp4"}).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            try:
                urllib.request.urlopen(bad_request)
                raise AssertionError("analysis of a missing file did not fail")
            except urllib.error.HTTPError as error:
                bad = {"status": error.code, "body": json.loads(error.read())}
            assert bad["status"] == 404 and bad["body"]["ok"] is False, bad

            # LLM context stays concise: technical summary, no full manifest.
            context_assets = page.evaluate("() => timelineSummaryForChat().projectAssets")
            assert len(context_assets) == 3
            assert "resolution" in context_assets[0] and "manifest" not in context_assets[0]
            assert "semanticStatus" in context_assets[0]

            # Reload keeps analysis and the human note.
            page.reload(wait_until="load")
            page.wait_for_timeout(1800)
            restored = page.evaluate("""() => {
                const asset = timelineState.assets.find(a => a.kind === 'video');
                return {analysis: Boolean(asset.analysis?.technical), user: asset.analysis?.user || null};
            }""")
            assert restored["analysis"] and "Blue test clip" in restored["user"]["description"], restored

            browser.close()
            assert not errors, errors
            print("ASSET INTELLIGENCE CHECK: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
