"""Packaged check: a large brief runs through the hidden plan inside the exe."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
EXE = ROOT / "dist" / "ClipACanvas.exe"
PORT = 9335

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

import psutil

RED = '<!doctype html><html><body style="margin:0;width:100%;height:100%;background:#d01818"></body></html>'
BLUE = '<!doctype html><html><body style="margin:0;width:100%;height:100%;background:#1848d0"></body></html>'

PLAN = {
    "title": "MICRO PLAN",
    "steps": [
        {"title": "Scene 01 red", "instruction": "Fill the selected scene with a solid red one second canvas using insert_animation_code with duration 1."},
        {"title": "Scene 02 blue", "instruction": "Add a second one second blue scene with add_scene."},
        {"title": "Render", "instruction": "Render the timeline with render_video."},
    ],
}

BRIEF = (
    "Produce a three-scene micro film. SCENE 01 is a solid red frame for one second. "
    "SCENE 02 is a solid blue frame for one second. SCENE 03 is a solid green frame for one second. "
    "Use the exact scene durations. Keep every title inside the safe margins. "
    "The film must be deterministic and render at 320x180. "
) * 12


def handle_chat(route):
    try:
        body = json.loads(route.request.post_data or "{}")
    except ValueError:
        body = {}
    messages = body.get("messages") or []
    system_text = " ".join(
        str(message.get("content") or "") for message in messages if message.get("role") == "system"
    )
    if "production planner" in system_text:
        reply = {"ok": True, "provider": "gemini", "model": "mock-planner", "text": json.dumps(PLAN), "toolCalls": [], "tools": False}
    else:
        last_user = next((str(message.get("content") or "") for message in reversed(messages) if message.get("role") == "user"), "")
        has_tool_result = any(message.get("role") == "tool" for message in messages)
        step_title = last_user.split("CURRENT STEP — ", 1)[1].split(chr(10), 1)[0].strip() if "CURRENT STEP — " in last_user else ""
        if has_tool_result:
            reply = {"ok": True, "provider": "gemini", "model": "mock-elephant", "text": "Step complete.", "toolCalls": [], "tools": True}
        elif "Scene 01 red" in step_title:
            reply = {"ok": True, "provider": "gemini", "model": "mock-elephant", "text": "Writing scene one…",
                     "toolCalls": [{"name": "insert_animation_code", "args": {"code": RED, "duration": 1}}], "tools": True}
        elif "Scene 02 blue" in step_title:
            reply = {"ok": True, "provider": "gemini", "model": "mock-elephant", "text": "Adding scene two…",
                     "toolCalls": [{"name": "add_scene", "args": {"code": BLUE, "name": "SCENE 02", "duration": 1}}], "tools": True}
        elif "Render" in step_title:
            reply = {"ok": True, "provider": "gemini", "model": "mock-elephant", "text": "Rendering…",
                     "toolCalls": [{"name": "render_video", "args": {}}], "tools": True}
        else:
            reply = {"ok": True, "provider": "gemini", "model": "mock-elephant", "text": "Done.", "toolCalls": [], "tools": True}
    route.fulfill(status=200, content_type="application/json", body=json.dumps(reply))


def clipacanvas_pids():
    return {p.pid for p in psutil.process_iter(["pid", "name"]) if p.info["name"] == "ClipACanvas.exe"}


def kill_all():
    for pid in clipacanvas_pids():
        try:
            psutil.Process(pid).kill()
        except Exception:
            pass
    time.sleep(1.5)


def attach(pw):
    deadline = time.time() + 60
    last = None
    while time.time() < deadline:
        try:
            browser = pw.chromium.connect_over_cdp(f"http://127.0.0.1:{PORT}", timeout=5000)
            pages = [page for context in browser.contexts for page in context.pages]
            page = next((p for p in pages if "clipacanvas.html" in p.url), None)
            if page:
                page.wait_for_timeout(1800)
                return browser, page
        except Exception as exc:
            last = exc
        time.sleep(2)
    raise RuntimeError(f"could not attach: {last}")


with tempfile.TemporaryDirectory() as tmp_name:
    data = Path(tmp_name) / "appdata"
    data.mkdir(parents=True)

    kill_all()
    env = os.environ.copy()
    env["CLIPACANVAS_KEYS_DIR"] = str(data)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={PORT} --remote-allow-origins=*"
    runtime_root = Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes"
    for name in ("styletts2", "kokoro", "piper", "zonos", "embedgemma2"):
        runtime_file = runtime_root / name / "runtime.json"
        if not runtime_file.exists():
            continue
        runtime = json.loads(runtime_file.read_text(encoding="utf-8"))
        prefix = "EMBEDDING" if name == "embedgemma2" else name.upper()
        env[f"CLIPACANVAS_{prefix}_PYTHON"] = runtime.get("python", "")
        if runtime.get("assets"):
            env[f"CLIPACANVAS_{prefix}_ASSETS"] = runtime["assets"]
        if runtime.get("voices"):
            env[f"CLIPACANVAS_{prefix}_VOICES"] = runtime["voices"]
    env["CLIPACANVAS_EMBEDDING_DEVICE"] = "cpu"
    media_dir = data / "media"
    media_dir.mkdir()
    shutil.copy(ROOT / "output" / "uitest" / "embed" / "football.jpg",
                media_dir / "media-0123456789abcdef0123.jpg")
    proc = subprocess.Popen([str(EXE)], env=env)
    try:
        with sync_playwright() as pw:
            browser, page = attach(pw)
            page.set_default_timeout(180000)
            page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
            page.wait_for_timeout(400)
            page.route("**/api/llm/chat", handle_chat)
            page.evaluate("""() => {
                chatState.keys.gemini = 'mock-key';
                chatState.models.gemini = [{ name: 'mock-flash', displayName: 'Mock Flash' }];
                chatState.knownGood.gemini = {};
                saveChatState();
            }""")
            page.evaluate("() => { setResolutionValue('320x180'); setFrameRange(0, 2); }")
            page.click("#tabAssistant")
            page.wait_for_selector("#chatInput", state="visible")
            page.fill("#chatInput", BRIEF)
            page.click("#chatSend")
            deadline = time.time() + 240
            while time.time() < deadline:
                page.wait_for_timeout(2000)
                if not page.evaluate("chatBusy") and "PLAN COMPLETE" in page.evaluate("document.getElementById('chatMessages').innerText"):
                    break
            page.wait_for_timeout(1200)
            session_id = page.evaluate("activeSession().id")
            plan_file = data / "agent-plans" / f"{session_id}.md"
            assert plan_file.exists(), f"hidden plan missing: {plan_file}"
            plan_text = plan_file.read_text(encoding="utf-8")
            assert "- [x] 01." in plan_text and "- [x] 02." in plan_text and "- [x] 03." in plan_text, plan_text
            state = page.evaluate("""() => ({
                clips: timelineState.clips.map(c => ({ name: c.name, start: c.start, code: String(c.code || '').length })),
                chat: document.getElementById('chatMessages').innerText,
                meta: window.lastRenderMeta || null
            })""")
            print("clips:", state["clips"])
            print("meta:", state["meta"])
            assert len([c for c in state["clips"] if c["code"] > 0]) >= 2, state["clips"]
            assert "MICRO PLAN" not in state["chat"], "plan leaked into the chat"
            assert "PLAN COMPLETE" in state["chat"], state["chat"][-400:]
            assert state["meta"] and float(state["meta"].get("duration") or 0) > 1.5, state["meta"]
            page.screenshot(path=str(ROOT / "output" / "playwright" / "packaged-agent-plan.png"), full_page=True)

            voice = page.evaluate("""async () => executeChatTool({
                name: 'generate_voiceover',
                args: { text: 'India is not one image.', provider: 'sapi', lane: 'A1', start: 0, captions: true }
            })""")
            print("voice:", {key: voice.get(key) for key in ("ok", "error", "lane", "duration", "captions")})
            assert voice.get("ok"), voice
            assert voice.get("duration") and voice["duration"] > 0.8, voice
            assert voice.get("captions", 0) >= 1, voice

            providers = page.evaluate("""async () => (await (await fetch('/api/tts/providers')).json()).providers
                .map(p => ({ id: p.id, available: p.available, reason: p.reason }))""")
            print("providers:", providers)
            assert [p["id"] for p in providers][:4] == ["styletts2", "kokoro", "piper", "zonos"], providers
            for provider_id in ("styletts2", "kokoro", "piper", "zonos"):
                entry = next((p for p in providers if p["id"] == provider_id), None)
                assert entry and entry["available"], providers
            assert not any(p["id"] == "edge" for p in providers), providers
            analysis = page.evaluate("""async () => {
                const response = await fetch('/api/media/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: '/media/media-0123456789abcdef0123.jpg' })
                });
                return response.json();
            }""")
            visual = (analysis.get('manifest') or {}).get('visual') or {}
            print("packaged visual:", analysis.get("ok"), visual.get("status"),
                  [tag.get("label") for tag in visual.get("tags") or []], visual.get("motion"))
            assert analysis.get("ok"), analysis
            assert visual.get("status") == "indexed", visual
            assert visual.get("tags"), visual
            assert visual.get("motion", {}).get("label") == "still", visual.get("motion")
            sts_voices = page.evaluate("""async () => (await (await fetch('/api/tts/providers')).json())
                .providers.find(p => p.id === 'styletts2').voices.map(v => ({ id: v.id, gender: v.gender }))""")
            print("styletts2 voices:", sts_voices)
            assert len(sts_voices) >= 8, sts_voices
            assert any(v["id"] == "libritts-4077" and v["gender"] == "male" for v in sts_voices), sts_voices
            sts_male = page.evaluate("""async () => executeChatTool({
                name: 'generate_voiceover',
                args: { text: 'The horizon opens like a door.', provider: 'styletts2', voice: 'LibriTTS 4077', lane: 'A3', start: 0 }
            })""")
            print("styletts2 male voice:", {key: sts_male.get(key) for key in ("ok", "error", "provider", "voice", "voiceLabel", "lane", "duration")})
            assert sts_male.get("ok"), sts_male
            assert sts_male.get("provider") == "styletts2" and sts_male.get("voice") == "libritts-4077", sts_male
            assert sts_male.get("duration") and sts_male["duration"] > 0.5, sts_male
            zonos_voices = page.evaluate("""async () => (await (await fetch('/api/tts/providers')).json())
                .providers.find(p => p.id === 'zonos').voices.map(v => v.id)""")
            print("zonos voices:", len(zonos_voices), zonos_voices[:5])
            assert len(zonos_voices) == 27, zonos_voices
            zonos_take = page.evaluate("""async () => executeChatTool({
                name: 'generate_voiceover',
                args: { text: 'The sea keeps its own time.', provider: 'zonos', voice: 'Savannah', lane: 'A2', start: 0 }
            })""")
            print("zonos voice:", {key: zonos_take.get(key) for key in ("ok", "error", "provider", "voice", "lane", "duration")})
            assert zonos_take.get("ok"), zonos_take
            assert zonos_take.get("provider") == "zonos" and zonos_take.get("voice") == "Savannah", zonos_take
            assert zonos_take.get("duration") and zonos_take["duration"] > 0.5, zonos_take
            neural = page.evaluate("""async () => executeChatTool({
                name: 'generate_voiceover',
                args: { text: 'The city wakes before the sun does.', provider: 'styletts2', lane: 'A1', start: 2 }
            })""")
            print("neural voice:", {key: neural.get(key) for key in ("ok", "error", "provider", "lane", "duration")})
            assert neural.get("ok"), neural
            assert neural.get("provider") == "styletts2", neural
            assert neural.get("duration") and neural["duration"] > 1, neural

            default_voice = page.evaluate("""async () => executeChatTool({
                name: 'generate_voiceover',
                args: { text: 'A river remembers every stone it passes.', lane: 'A1', start: 6 }
            })""")
            print("default voice:", {key: default_voice.get(key) for key in ("ok", "error", "provider", "lane", "duration")})
            assert default_voice.get("ok"), default_voice
            assert default_voice.get("provider") == "styletts2", default_voice

            piper_voice = page.evaluate("""async () => executeChatTool({
                name: 'generate_voiceover',
                args: { text: 'Every mile is a different story.', provider: 'piper', lane: 'A2', start: 0 }
            })""")
            print("piper voice:", {key: piper_voice.get(key) for key in ("ok", "error", "provider", "lane", "duration")})
            assert piper_voice.get("ok"), piper_voice
            assert piper_voice.get("provider") == "piper", piper_voice
            assert piper_voice.get("duration") and piper_voice["duration"] > 0.5, piper_voice
            browser.close()
    finally:
        kill_all()
    print("PASS packaged agent plan + voice")
