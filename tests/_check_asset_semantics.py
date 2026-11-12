"""Asset semantics: local shots/keyframes, consent-gated content analysis, notes."""
import base64
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
import serve
from serve import resolve_ffmpeg_exe, server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()
CANNED_RESULT = {
    "steps": [{
        "type": "model_output",
        "content": [{
            "type": "text",
            "text": json.dumps({
                "description": "Three synthetic test patterns cut together.",
                "subjects": ["test pattern"],
                "tags": ["test pattern", "color bars", "synthetic"],
                "suggestedUses": ["benchmark footage"],
                "confidence": 0.82,
                "transcript": [{"start": 0.4, "text": "Testing one two three."}],
            }),
        }],
    }],
}
captured = {}
original_post = serve.ClipACanvasHandler._llm_http_post


def fake_post(url, body, headers, timeout=180):
    captured["url"] = url
    captured["body"] = body
    captured["headers"] = dict(headers)
    if captured.get("fail"):
        raise urllib.error.URLError("simulated offline")
    return CANNED_RESULT


serve.ClipACanvasHandler._llm_http_post = staticmethod(fake_post)

errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    video = tmp / "cuts.mp4"
    image = tmp / "still.png"
    audio = tmp / "speech.wav"
    talk = tmp / "talk.mp4"
    subprocess.run(
        [ffmpeg, "-y",
         "-f", "lavfi", "-i", "testsrc=size=320x180:rate=24:duration=1",
         "-f", "lavfi", "-i", "smptebars=size=320x180:rate=24:duration=1",
         "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=1",
         "-filter_complex", "[0:v][1:v][2:v]concat=n=3:v=1:a=0",
         "-pix_fmt", "yuv420p", str(video)],
        capture_output=True, check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(talk)],
        capture_output=True, check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
         "-frames:v", "1", str(image)],
        capture_output=True, check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:a", "pcm_s16le", str(audio)],
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
            page.set_input_files("#mediaInput", [str(video), str(image), str(audio), str(talk)])
            page.wait_for_function(
                "() => timelineState.assets.length === 4"
                " && timelineState.assets.every(a => a.analysis?.technical)"
                " && (timelineState.assets.find(a => a.name === 'cuts').analysis.shots || []).length >= 3",
                timeout=60000,
            )
            assets = page.evaluate("""() => Object.fromEntries(timelineState.assets.map(a => [a.name, {
                id: a.id, name: a.name, url: a.url, kind: a.kind, analysis: a.analysis
            }]))""")
            video_asset = assets["cuts"]
            image_asset = assets["still"]
            audio_asset = assets["speech"]
            talk_asset = assets["talk"]
            shots = video_asset["analysis"]["shots"]
            print("video shots:", [(shot["start"], shot["end"]) for shot in shots])
            assert len(shots) >= 3, shots
            starts = [shot["start"] for shot in shots]
            assert starts[0] == 0, starts
            assert any(abs(start - 1.0) < 0.25 for start in starts), starts
            assert any(abs(start - 2.0) < 0.25 for start in starts), starts
            assert all(shot["keyframe"] for shot in shots[:3]), shots[:3]
            assert image_asset["analysis"]["shots"] == []
            assert audio_asset["analysis"]["shots"] == []
            assert video_asset["analysis"]["analyzer"]["version"] == 2
            frame_bytes = urllib.request.urlopen(base + shots[0]["keyframe"]).read()
            print("keyframe bytes:", len(frame_bytes))
            assert frame_bytes[:2] == b"\xff\xd8" and len(frame_bytes) > 500

            # Inspector: local shots visible without any key or consent.
            video_id = video_asset["id"]
            page.locator(f'.dock-bin[data-asset-id="{video_id}"]').click()
            page.wait_for_timeout(400)
            assert page.locator("#miShots").is_visible(), "shot strip hidden"
            assert page.locator("#miShots img").count() >= 3
            assert "NOT ANALYZED" in page.locator("#miContentStatus").inner_text()
            assert "NOT RUN" in page.locator("#miSemanticNote").inner_text()

            # No key: the analyze action reports the provider reason, no upload UI.
            page.click("#miAnalyzeToggle")
            page.wait_for_function(
                "() => document.getElementById('miAnalyzeHint').textContent.includes('Gemini API key')",
                timeout=10000,
            )
            assert page.locator("#miConsentRow").is_hidden()

            # Human note editor persists separately from AI fields.
            page.fill("#miUserNote", "Three test patterns for the opening title")
            page.click("#miUserNoteSave")
            page.wait_for_timeout(300)
            assert "USER NOTE" in page.locator("#miSemanticNote").inner_text()
            note_state = page.evaluate(
                "() => timelineState.assets.find(a => a.name === 'cuts').analysis"
            )
            assert "Three test patterns" in note_state["user"]["description"], note_state["user"]
            assert note_state["semantic"]["status"] == "not_analyzed"

            # Consent must be explicit and the run stays disabled until checked.
            urllib.request.urlopen(urllib.request.Request(
                f"{base}/api/llm/keys",
                data=json.dumps({"gemini": "test-gemini-key"}).encode(),
                method="POST",
                headers={"Content-Type": "application/json"},
            ))
            page.click("#miAnalyzeToggle")
            page.wait_for_selector("#miConsentRow:not([hidden])")
            consent_text = page.locator("#miConsentText").inner_text()
            assert "Google Gemini" in consent_text and "still frames" in consent_text, consent_text
            assert page.locator("#miAnalyzeRun").is_disabled()
            page.check("#miConsentCheck")
            assert not page.locator("#miAnalyzeRun").is_disabled()
            page.click("#miAnalyzeCancel")
            assert page.locator("#miConsentRow").is_hidden()

            # Missing consent is rejected server-side too.
            try:
                urllib.request.urlopen(urllib.request.Request(
                    f"{base}/api/media/semantic",
                    data=json.dumps({"url": video_asset["url"], "provider": "gemini"}).encode(),
                    method="POST",
                    headers={"Content-Type": "application/json"},
                ))
                raise AssertionError("semantic analysis without consent was accepted")
            except urllib.error.HTTPError as error:
                denied = {"status": error.code, "body": json.loads(error.read())}
            assert denied["status"] == 403 and "consent" in denied["body"]["error"], denied

            page.click("#miAnalyzeToggle")
            page.wait_for_selector("#miConsentRow:not([hidden])")
            page.check("#miConsentCheck")
            page.click("#miAnalyzeRun")
            page.wait_for_function(
                "() => timelineState.assets.find(a => a.name === 'cuts').analysis.semantic.status === 'analyzed'",
                timeout=30000,
            )
            page.wait_for_timeout(300)
            body = captured["body"]
            content = body["input"][0]["content"]
            images = [item for item in content if item.get("type") == "image"]
            frame_shots = [shot for shot in shots if shot.get("keyframe")]
            assert captured["url"].endswith("/v1beta/interactions"), captured["url"]
            assert captured["headers"].get("x-goog-api-key") == "test-gemini-key"
            assert body["model"] == "gemini-2.5-flash"
            assert body["response_format"]["mime_type"] == "application/json"
            assert body["response_format"]["schema"]["type"] == "object"
            assert len(images) == min(len(frame_shots), serve.SEMANTIC_MAX_FRAMES), len(images)
            assert all(item["mime_type"] == "image/jpeg" for item in images)
            assert base64.b64decode(images[0]["data"])[:2] == b"\xff\xd8"
            assert not any(item.get("type") == "audio" for item in content)
            analyzed = page.evaluate(
                "() => timelineState.assets.find(a => a.name === 'cuts').analysis"
            )
            assert analyzed["semantic"]["status"] == "analyzed"
            assert analyzed["semantic"]["framesSent"] == len(images)
            assert analyzed["semantic"]["audioSent"] is False
            assert analyzed["semantic"]["provider"] == "gemini"
            assert "Three test patterns" in analyzed["user"]["description"]
            assert "Three synthetic" in page.locator("#miSemanticText").inner_text()
            assert page.locator("#miTags span").count() >= 3
            assert "ANALYZED" in page.locator("#miContentStatus").inner_text()
            print("video semantic:", analyzed["semantic"]["tags"], analyzed["semantic"]["framesSent"])

            # Audio assets analyze through transcription with the audio content item.
            page.locator(f'.dock-bin[data-asset-id="{audio_asset["id"]}"]').click()
            page.wait_for_timeout(300)
            page.click("#miAnalyzeToggle")
            page.wait_for_selector("#miConsentRow:not([hidden])")
            audio_consent = page.locator("#miConsentText").inner_text()
            assert "audio file" in audio_consent, audio_consent
            assert page.locator("#miConsentAudioRow").is_hidden()
            page.check("#miConsentCheck")
            page.click("#miAnalyzeRun")
            page.wait_for_function(
                "() => timelineState.assets.find(a => a.name === 'speech').analysis.semantic.status === 'analyzed'",
                timeout=30000,
            )
            page.wait_for_timeout(300)
            audio_content = captured["body"]["input"][0]["content"]
            audio_items = [item for item in audio_content if item.get("type") == "audio"]
            assert len(audio_items) == 1 and audio_items[0]["mime_type"] == "audio/wav", audio_items
            assert not [item for item in audio_content if item.get("type") == "image"]
            assert "Testing one two three." in page.locator("#miTranscript").inner_text()
            audio_state = page.evaluate(
                "() => timelineState.assets.find(a => a.name === 'speech').analysis"
            )
            assert audio_state["semantic"]["audioSent"] is True
            assert audio_state["semantic"]["transcript"][0]["start"] == 0.4

            # Images analyze as a single still frame with no audio item.
            page.locator(f'.dock-bin[data-asset-id="{image_asset["id"]}"]').click()
            page.wait_for_timeout(300)
            page.click("#miAnalyzeToggle")
            page.wait_for_selector("#miConsentRow:not([hidden])")
            assert "1 still frame" in page.locator("#miConsentText").inner_text()
            assert page.locator("#miConsentAudioRow").is_hidden()
            page.check("#miConsentCheck")
            page.click("#miAnalyzeRun")
            page.wait_for_function(
                "() => timelineState.assets.find(a => a.name === 'still').analysis.semantic.status === 'analyzed'",
                timeout=30000,
            )
            image_content = captured["body"]["input"][0]["content"]
            image_items = [item for item in image_content if item.get("type") == "image"]
            assert len(image_items) == 1, image_items
            assert not [item for item in image_content if item.get("type") == "audio"]

            # Video audio is extracted to mp3 for consented transcription.
            page.locator(f'.dock-bin[data-asset-id="{talk_asset["id"]}"]').click()
            page.wait_for_timeout(300)
            page.click("#miAnalyzeToggle")
            page.wait_for_selector("#miConsentRow:not([hidden])")
            assert page.locator("#miConsentAudioRow").is_visible()
            assert "audio track" in page.locator("#miConsentText").inner_text()
            page.check("#miConsentCheck")
            page.check("#miConsentAudioCheck")
            page.click("#miAnalyzeRun")
            page.wait_for_function(
                "() => timelineState.assets.find(a => a.name === 'talk').analysis.semantic.status === 'analyzed'",
                timeout=60000,
            )
            talk_content = captured["body"]["input"][0]["content"]
            talk_audio = [item for item in talk_content if item.get("type") == "audio"]
            assert len(talk_audio) == 1 and talk_audio[0]["mime_type"] == "audio/mp3", talk_audio
            talk_state = page.evaluate("() => timelineState.assets.find(a => a.name === 'talk').analysis")
            assert talk_state["semantic"]["audioSent"] is True

            # Provider failure keeps the previous result and surfaces the error.
            captured["fail"] = True
            page.locator(f'.dock-bin[data-asset-id="{video_id}"]').click()
            page.wait_for_timeout(300)
            page.click("#miAnalyzeToggle")
            page.wait_for_selector("#miConsentRow:not([hidden])")
            page.check("#miConsentCheck")
            page.click("#miAnalyzeRun")
            page.wait_for_function(
                "() => document.getElementById('miAnalyzeHint').textContent.includes('simulated offline')",
                timeout=15000,
            )
            assert page.evaluate(
                "() => timelineState.assets.find(a => a.name === 'cuts').analysis.semantic.status"
            ) == "analyzed"
            captured["fail"] = False

            # The technical cache returns the merged semantic manifest.
            cache = page.evaluate("""async () => {
                const asset = timelineState.assets.find(a => a.name === 'cuts');
                const response = await fetch('/api/media/analyze', {
                    method: 'POST', headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({url: asset.url})
                });
                return (await response.json()).manifest;
            }""")
            assert cache["semantic"]["status"] == "analyzed"
            assert len(cache["shots"]) >= 3

            # Agent tools see the semantic fields and shots.
            def tool(name, args):
                return page.evaluate(
                    "async ([name, args]) => executeChatTool({name, args})", [name, args]
                )

            search = tool("search_assets", {"query": "color bars"})
            assert search["ok"] and search["count"] >= 1, search
            match = next(item for item in search["assets"] if item["id"] == video_id)
            assert match["semanticStatus"] == "analyzed", match
            manifest = tool("get_asset_analysis", {"assetId": video_id})["manifest"]
            assert manifest["semantic"]["status"] == "analyzed"
            assert len(manifest["shots"]) >= 3
            assert manifest["semantic"]["tags"][0] == "test pattern"

            # Reload keeps shots, AI content and the human note.
            page.reload(wait_until="load")
            page.wait_for_timeout(1600)
            page.locator(f'.dock-bin[data-asset-id="{video_id}"]').click()
            page.wait_for_timeout(400)
            assert page.locator("#miShots img").count() >= 3
            assert "ANALYZED" in page.locator("#miContentStatus").inner_text()
            assert "USER NOTE" in page.locator("#miSemanticNote").inner_text()
            OUT = ROOT / "output" / "playwright"
            OUT.mkdir(parents=True, exist_ok=True)
            page.locator("#miContentBlock").scroll_into_view_if_needed()
            page.screenshot(path=str(OUT / "asset-semantics.png"))

            browser.close()
            assert not errors, errors
            print("ASSET SEMANTICS CHECK: OK")
    finally:
        serve.ClipACanvasHandler._llm_http_post = original_post
        try:
            server.shutdown()
        except Exception:
            pass
