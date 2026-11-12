import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

from serve import LLM_TOOL_DECLARATIONS, server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

SEED = """<!doctype html><html><head><style>
html,body{margin:0;height:100%;background:#101018;overflow:hidden}
h1{color:#fff;font:700 60px sans-serif;padding:40px;animation:pulse 1s infinite alternate}
@keyframes pulse{to{transform:scale(1.2)}}
</style></head><body><h1>OPENING</h1></body></html>"""

INTRO = """<!doctype html><html><head><style>
html,body{margin:0;height:100%;background:#ff3300;overflow:hidden}
h1{color:#fff;font:700 60px sans-serif;padding:40px}
</style></head><body><h1>INTRO BEAT</h1></body></html>"""

TITLE = """<!doctype html><html><head><style>
html,body{margin:0;height:100%;background:transparent;overflow:hidden}
h1{color:#fff;font:700 48px sans-serif;padding-top:80px;text-align:center}
</style></head><body><h1>THE END</h1></body></html>"""

tools = {tool["name"]: tool for tool in LLM_TOOL_DECLARATIONS}
assert "add_scene" in tools, sorted(tools)
assert tools["add_scene"]["parameters"]["required"] == ["code"]
assert tools["add_scene"]["parameters"]["properties"]["layer"]["enum"] == ["same", "above"]
assert "duration" in tools["insert_animation_code"]["parameters"]["properties"]
assert "selected scene" in tools["insert_animation_code"]["description"].lower()

server, thread = start_server()
base = server_url(server)
errors = []
requests = []
goldfish_reviews = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1480, "height": 960})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(str(err)))

    def mock_chat(route):
        data = route.request.post_data_json or {}
        messages = data.get("messages") or []
        system = str(messages[0].get("content", "")) if messages else ""
        if data.get("tools") is False:
            if "Goldfish" in system:
                code = ""
                for message in messages:
                    if message.get("role") == "user":
                        code = str(message.get("content", ""))
                goldfish_reviews.append(code)
                body = json.dumps({"verdict": "pass", "summary": "both scenes render", "findings": []})
            else:
                body = "Two scene ad"
            route.fulfill(json={"ok": True, "text": body, "model": "mock-model"})
            return
        requests.append(data)
        has_tool_result = any(message.get("role") == "tool" for message in messages)
        if not has_tool_result:
            route.fulfill(json={
                "ok": True,
                "text": "Building both scenes…",
                "model": "mock-model",
                "toolCalls": [
                    {"id": "call_scene_1", "name": "add_scene", "args": {
                        "code": INTRO, "name": "INTRO", "duration": 1.2, "layer": "same"
                    }},
                    {"id": "call_scene_2", "name": "add_scene", "args": {
                        "code": TITLE, "name": "TITLE", "duration": 0.8, "layer": "above"
                    }},
                ],
            })
        else:
            route.fulfill(json={
                "ok": True,
                "text": "Two scenes added: INTRO and TITLE.",
                "model": "mock-model",
                "toolCalls": [],
            })

    page.route("**/api/llm/chat", mock_chat)
    page.goto(f"{base}/clipacanvas.html", wait_until="load")
    page.wait_for_timeout(1200)

    page.evaluate("""code => {
        const editor = document.getElementById('codeInput');
        editor.value = code;
        editor.dispatchEvent(new Event('input', { bubbles: true }));
        chatState.keys.gemini = 'mock-key';
        chatState.models.gemini = [{ name: 'gemini-2.5-flash', displayName: 'Flash' }];
        chatState.knownGood.gemini = { flash: 'gemini-2.5-flash' };
        document.getElementById('llmModel').value = 'auto';
    }""", SEED)
    page.wait_for_timeout(400)

    page.evaluate("""async () => {
        document.getElementById('chatInput').value = 'make a two scene ad with an intro and a title';
        await sendChat();
    }""")
    page.wait_for_timeout(900)

    assert len(requests) >= 2, f"expected tool rounds, got {len(requests)}"
    first_request = requests[0]
    first_system = "\n".join(
        str(message.get("content", ""))
        for message in first_request.get("messages", [])
        if message.get("role") == "system"
    )
    print("first request has timeline:", "Current timeline" in first_system)
    print("first request has add_scene prompt:", "add_scene" in first_system)
    assert "Current timeline" in first_system, first_system[:600]
    assert "add_scene" in first_system

    second_request = requests[1]
    tool_messages = [m for m in second_request.get("messages", []) if m.get("role") == "tool"]
    print("tool results:", [m.get("name") for m in tool_messages])
    assert [m.get("name") for m in tool_messages] == ["add_scene", "add_scene"], tool_messages
    first_result = json.loads(tool_messages[0]["content"])
    assert first_result["ok"] and first_result["scene"]["layer"] == "V1", first_result
    second_result = json.loads(tool_messages[1]["content"])
    assert second_result["ok"] and second_result["scene"]["layer"] == "V2", second_result

    timeline = page.evaluate("timelineSummaryForChat()")
    print("timeline:", json.dumps(timeline))
    scenes = {scene["name"]: scene for scene in timeline["scenes"]}
    assert len(timeline["scenes"]) == 3, timeline
    assert scenes["INTRO"]["layer"] == "V1", scenes
    assert scenes["TITLE"]["layer"] == "V2", scenes
    assert scenes["TITLE"]["durationSeconds"] == 0.8, scenes
    assert scenes["TITLE"]["startSeconds"] == scenes["INTRO"]["startSeconds"], scenes
    assert page.locator(".logic-box").count() == 3

    active_name = page.locator(".logic-box.active .logic-name").inner_text()
    print("active scene:", active_name)
    assert active_name == "TITLE", active_name
    assert "THE END" in page.evaluate("document.getElementById('codeInput').value")

    traces = page.locator(".chat-tool-trace .tool-name").all_inner_texts()
    print("tool traces:", traces)
    assert [trace.lower() for trace in traces].count("add_scene") == 2, traces

    session = page.evaluate("activeSession()")
    assistant = [m for m in session["messages"] if m["role"] == "assistant"][-1]
    print("assistant codeAfter is title:", "THE END" in (assistant.get("codeAfter") or ""))
    assert "THE END" in (assistant.get("codeAfter") or "")
    assert [tool["name"] for tool in assistant.get("tools") or []].count("add_scene") == 2, assistant

    print("goldfish reviews:", len(goldfish_reviews))
    assert goldfish_reviews, "goldfish never reviewed the new scene"
    assert "THE END" in goldfish_reviews[-1], goldfish_reviews[-1][:300]

    # A render requested after a code-writing tool is queued, not skipped.
    queued = page.evaluate("""async () => {
        chatTurnWroteCode = true;
        chatTurnRendered = false;
        chatTurnRenderBlocked = false;
        chatTurnPendingRender = false;
        const result = await executeChatTool({ name: 'render_video', args: {} });
        chatTurnWroteCode = false;
        chatTurnPendingRender = false;
        return result;
    }""")
    print("queued render:", queued)
    assert queued["ok"] and queued.get("queued"), queued

    page.screenshot(path=str(ROOT / "output" / "playwright" / "chat-scenes.png"), full_page=True)
    browser.close()

stop_server(server)
print("console errors:", errors)
assert not errors, errors
print("CHAT SCENE TOOLS OK")
