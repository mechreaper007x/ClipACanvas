"""Large briefs run through a hidden markdown plan and sequential tool steps."""
import json
import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

from serve import server_url, start_server, stop_server

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
        step_match = "CURRENT STEP — " in last_user
        step_title = last_user.split("CURRENT STEP — ", 1)[1].split(chr(10), 1)[0].strip() if step_match else ""
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


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(appdata)
    server, thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.route("**/api/llm/chat", handle_chat)
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)
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

            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_function("() => !chatBusy", timeout=60000)
            page.wait_for_timeout(500)
            session_id = page.evaluate("activeSession().id")
            plan_file = appdata / "agent-plans" / f"{session_id}.md"
            assert plan_file.exists(), f"hidden plan missing: {plan_file}"
            plan_text = plan_file.read_text(encoding="utf-8")
            print("plan file:", plan_file.name, len(plan_text), "bytes")
            print(plan_text)
            assert "- [x] 01." in plan_text and "- [x] 02." in plan_text and "- [x] 03." in plan_text, plan_text

            state = page.evaluate("""() => ({
                clips: timelineState.clips.map(c => ({ name: c.name, start: c.start, code: String(c.code || '').length })),
                chat: document.getElementById('chatMessages').innerText,
                meta: window.lastRenderMeta || null
            })""")
            print("clips:", state["clips"])
            print("render meta:", state["meta"])
            assert len([c for c in state["clips"] if c["code"] > 0]) >= 2, state["clips"]
            assert all(c["code"] > 0 for c in state["clips"]), state["clips"]
            assert "MICRO PLAN" not in state["chat"], "plan leaked into the chat"
            assert "solid red one second canvas" not in state["chat"], "plan instructions leaked into the chat"
            assert "PLAN COMPLETE" in state["chat"], state["chat"][-400:]
            assert state["meta"] and float(state["meta"].get("duration") or 0) > 1.5, state["meta"]
            assert not errors, errors
            page.screenshot(path=str(ROOT / "output" / "playwright" / "agent-plan.png"), full_page=True)
            browser.close()
    finally:
        stop_server(server)
    print("PASS agent plan")
