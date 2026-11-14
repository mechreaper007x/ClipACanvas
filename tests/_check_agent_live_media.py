"""Live Gemini run: media-aware overlay on an image clip and a model-written custom transition.

Uses the real stored API keys (copied into an isolated data dir), the local
EmbeddingGemma visual index, and the deterministic preview to prove the
generated transition code actually changes the frame at the cut.
"""
import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DATA = Path(tempfile.mkdtemp(prefix="cc-live-media-"))
os.environ["CLIPACANVAS_KEYS_DIR"] = str(DATA)
os.environ["CLIPACANVAS_EMBEDDING_PYTHON"] = str(
    Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python311" / "python.exe")
os.environ["CLIPACANVAS_EMBEDDING_ASSETS"] = str(
    Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "embedgemma2" / "assets")
os.environ["CLIPACANVAS_EMBEDDING_DEVICE"] = "cpu"

for name in ("keys.dat", "keys.key"):
    source = Path(os.environ["APPDATA"]) / "ClipACanvas" / name
    if source.exists():
        shutil.copy(source, DATA / name)
media_dir = DATA / "media"
media_dir.mkdir()
shutil.copy(ROOT / "output" / "uitest" / "embed" / "football.jpg",
            media_dir / "media-0123456789abcdef0123.jpg")

from playwright.sync_api import sync_playwright

from serve import server_url, start_server, stop_server

MEDIA_URL = "/media/media-0123456789abcdef0123.jpg"
OVERLAY_PROMPT = (
    "Just do it now, no questions: the selected clip is imported football footage. "
    "Create exactly one lower-third overlay with create_overlay, with parentClipId set to that clip, "
    "a fully transparent page background, and a short title that fits what is actually in the footage. "
    "Do not modify or replace the media clip."
)
TRANSITION_PROMPT = (
    "Just do it now, no questions: add YOUR OWN custom transition between these two touching scenes. "
    "Call add_transition with type \"custom\" and write the renderTransition(ctx) code yourself — "
    "do not use a preset. Keep it between 0.3 and 0.8 seconds."
)

server, thread = start_server()
base = server_url(server)


def wait_for_chat(page, timeout=90):
    deadline = time.time() + timeout
    while time.time() < deadline:
        ready = page.evaluate("""() => ({
            key: (chatState.keys.gemini || '').length > 0,
            models: (chatState.models.gemini || []).length
        })""")
        if ready["key"] and ready["models"]:
            return ready
        page.wait_for_timeout(1500)
    raise AssertionError("chat keys or models never became ready")


def ask(page, prompt, timeout=180):
    page.evaluate("() => { window.__toolCalls = []; }")
    page.fill("#chatInput", prompt)
    page.click("#chatSend")
    deadline = time.time() + timeout
    while time.time() < deadline:
        page.wait_for_timeout(2000)
        if not page.evaluate("chatBusy"):
            break
    page.wait_for_timeout(800)
    return {
        "calls": page.evaluate("() => (window.__toolCalls || []).slice()"),
        "chat": page.evaluate("document.getElementById('chatMessages').innerText"),
    }


try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        page.set_default_timeout(180000)
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)
        page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
        ready = wait_for_chat(page)
        print("chat ready:", ready)
        page.evaluate("""() => {
            const select = document.getElementById('llmModel');
            if (select && [...select.options].some(option => option.value === 'gemini-2.5-flash')) {
                select.value = 'gemini-2.5-flash';
                select.dispatchEvent(new Event('change'));
            }
            const original = window.executeChatTool;
            window.__originalExecuteChatTool = original;
            window.executeChatTool = function (call) {
                window.__toolCalls.push(call && call.name);
                return original.apply(this, arguments);
            };
        }""")

        analysis = page.evaluate("""async url => {
            const response = await fetch('/api/media/analyze', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            return response.json();
        }""", MEDIA_URL)
        manifest = analysis.get("manifest") or {}
        print("analysis:", analysis.get("ok"), manifest.get("visual", {}).get("status"),
              [tag.get("label") for tag in (manifest.get("visual") or {}).get("tags") or []])
        assert analysis.get("ok") and manifest.get("visual", {}).get("status") == "indexed", analysis

        page.evaluate("""manifest => {
            const asset = {
                id: 'asset-live-image', name: 'FOOTBALL', kind: 'image',
                url: '/media/media-0123456789abcdef0123.jpg', duration: 4,
                addedAt: Date.now(), analysis: manifest, analysisError: ''
            };
            timelineState.assets.length = 0;
            timelineState.assets.push(asset);
            const clip = {
                id: newClipId(), name: 'FOOTBALL', code: '', duration: 4, start: 0,
                track: 0, explicitDuration: true, type: 'image', assetId: asset.id,
                mediaUrl: asset.url, mediaName: 'football.jpg', sourceIn: 0,
                fit: 'cover', parentClipId: '', audioTrack: ''
            };
            timelineState.clips.length = 0;
            timelineState.clips.push(clip);
            timelineState.layers = 2;
            timelineState.activeId = clip.id;
            timelineState.selectedIds = [clip.id];
            timelineState.transitions = [];
            saveTimelineState(true);
            renderLogicBoxes();
            renderProjectBin();
            updateStageTimeline();
        }""", manifest)
        page.click("#tabAssistant")
        page.wait_for_selector("#chatInput", state="visible")

        first = ask(page, OVERLAY_PROMPT)
        print("overlay tool calls:", first["calls"])
        print("overlay chat tail:", first["chat"][-500:])
        overlay_state = page.evaluate("""() => {
            const parent = timelineState.clips[0];
            const overlay = timelineState.clips.find(clip => clip.id !== parent.id);
            return overlay ? {
                type: overlay.type, track: overlay.track, parent: overlay.parentClipId,
                duration: overlay.duration, start: overlay.start,
                codeLength: String(overlay.code || '').length,
                transparent: /transparent/i.test(String(overlay.code || ''))
            } : null;
        }""")
        print("overlay:", overlay_state)
        assert overlay_state, first["chat"][-600:]
        assert overlay_state["type"] == "code", overlay_state
        assert overlay_state["parent"] == page.evaluate("timelineState.clips[0].id"), overlay_state
        assert overlay_state["track"] == 1, overlay_state
        assert abs(overlay_state["duration"] - 4) < 0.01, overlay_state
        assert overlay_state["codeLength"] > 80, overlay_state
        assert overlay_state["transparent"], overlay_state
        visual_summary = page.evaluate("""() => {
            const asset = timelineState.assets[0];
            const summary = assetTechnicalSummary(asset);
            return { tags: summary.visualTags, motion: summary.motion };
        }""")
        print("visual summary the model can see:", visual_summary)
        assert visual_summary["tags"], visual_summary
        page.screenshot(path=str(ROOT / "output" / "playwright" / "live-media-overlay.png"))

        page.evaluate("""() => {
            const clip = (name, start, color) => ({
                id: newClipId(), name, code: `<!doctype html><html><body style="margin:0;width:100%;height:100%;background:${color}"></body></html>`,
                duration: 2, start, track: 0, explicitDuration: true, type: 'code',
                assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain',
                parentClipId: '', audioTrack: ''
            });
            timelineState.clips.length = 0;
            timelineState.clips.push(clip('RED', 0, '#d01818'));
            timelineState.clips.push(clip('BLUE', 2, '#1848d0'));
            timelineState.layers = 1;
            timelineState.activeId = timelineState.clips[0].id;
            timelineState.selectedIds = [timelineState.clips[0].id];
            timelineState.transitions = [];
            saveTimelineState(true);
            renderLogicBoxes();
            updateStageTimeline();
        }""")
        second = ask(page, TRANSITION_PROMPT)
        print("transition tool calls:", second["calls"])
        print("transition chat tail:", second["chat"][-500:])
        transition = page.evaluate("""() => {
            const item = timelineState.transitions[0];
            return item ? { type: item.type, duration: item.duration, code: item.code || '',
                             cut: item.cut ?? null } : null;
        }""")
        print("transition:", {key: transition.get(key) for key in ("type", "duration", "cut", "code")} if transition else None)
        assert transition, second["chat"][-600:]
        assert transition["type"] == "custom", transition
        assert "renderTransition" in transition["code"], transition["code"][:300]
        assert 0.2 <= float(transition["duration"]) <= 1.0, transition

        def composite_layers():
            page.evaluate("() => setPlayhead(2.0, { preview: true })")
            page.wait_for_timeout(900)
            state = page.evaluate("previewCompositeState")
            assert state["active"] and state["count"] == 2, state
            for frame in page.frames:
                try:
                    if frame.evaluate("() => document.querySelectorAll('.cc-layer').length === 2"):
                        return frame.evaluate(
                            "() => Array.from(document.querySelectorAll('.cc-layer')).map(el => el.getAttribute('style') || '')")
                except Exception:
                    continue
            raise AssertionError("composite iframe missing")

        with_transition = composite_layers()
        print("layer styles with custom transition:", with_transition)
        assert any(style.strip() for style in with_transition), with_transition
        page.evaluate("""() => {
            window.__savedTransitions = timelineState.transitions.slice();
            timelineState.transitions = [];
            saveTimelineState(true);
            updateStageTimeline();
        }""")
        page.evaluate("() => setPlayhead(2.0, { preview: true })")
        page.wait_for_timeout(900)
        without_state = page.evaluate("previewCompositeState")
        print("preview state without transition:", without_state)
        if without_state["active"]:
            without_transition = composite_layers()
            print("layer styles without transition:", without_transition)
            assert with_transition != without_transition, "custom transition did not change the preview layers at the cut"
        else:
            assert without_state["count"] == 0, without_state
        page.evaluate("""() => {
            timelineState.transitions = window.__savedTransitions;
            saveTimelineState(true);
            updateStageTimeline();
        }""")
        page.screenshot(path=str(ROOT / "output" / "playwright" / "live-custom-transition.png"))
        print("page errors:", errors)
        assert not errors, errors
        print("PASS live media overlay + model-written transition")
        browser.close()
finally:
    stop_server(server)
