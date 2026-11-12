import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

from serve import server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

CLIP_A = """<!doctype html><html><head><style>
html,body{margin:0;height:100%;background:#ff3300;overflow:hidden}
h1{color:#fff;font:700 64px sans-serif;padding:40px;animation:pulse 1s infinite alternate}
@keyframes pulse{to{transform:scale(1.3)}}
</style></head><body><h1>SCENE A</h1></body></html>"""

CLIP_B = """<!doctype html><html><head><style>
html,body{margin:0;height:100%;background:#0033ff;overflow:hidden}
h1{color:#fff;font:700 64px sans-serif;padding:40px}
</style></head><body><h1>SCENE B</h1></body></html>"""

server, thread = start_server()
base = server_url(server)
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1480, "height": 960})
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.goto(f"{base}/clipacanvas.html", wait_until="load")
    page.wait_for_timeout(1200)

    # A fresh timeline is one single track, not a stacked V2 over V1.
    labels = page.locator(".et-label").all_inner_texts()
    meta = page.locator("#timelineMeta").inner_text()
    print("initial layers:", labels, "meta:", meta)
    assert labels == ["V1"], labels
    assert "1 LAYER" in meta, meta
    assert page.locator(".et-row").count() == 1

    # Seed clip A into the initial box.
    page.evaluate("""code => {
        const editor = document.getElementById('codeInput');
        editor.value = code;
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }""", CLIP_A)
    page.wait_for_timeout(350)

    # + BOX must create a blank scene, not a copy of the active code.
    page.click("#boxAdd")
    page.wait_for_timeout(400)
    assert page.locator(".logic-box").count() == 2, "box did not get added"
    editor_value = page.evaluate("document.getElementById('codeInput').value")
    new_snippet = page.locator(".logic-box.active .logic-snippet").inner_text()
    hint_visible = page.evaluate("document.getElementById('emptyScene').classList.contains('visible')")
    stored = json.loads(page.evaluate("localStorage.getItem('clipacanvas.timeline.v1')"))
    new_clip = next(clip for clip in stored["clips"] if clip["id"] == page.evaluate("timelineState.activeId"))
    print("new box blank:", repr(editor_value), new_snippet, hint_visible)
    assert editor_value == "", "new box copied the active code instead of starting blank"
    assert new_clip["code"] == "", "stored new box is not blank"
    assert new_snippet == "EMPTY BOX", new_snippet
    assert hint_visible, "empty scene hint did not show"

    # Filling the blank scene hides the hint and updates its snippet.
    page.evaluate("""code => {
        const editor = document.getElementById('codeInput');
        editor.value = code;
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }""", CLIP_B)
    page.wait_for_timeout(350)
    assert not page.evaluate("document.getElementById('emptyScene').classList.contains('visible')")
    stored = json.loads(page.evaluate("localStorage.getItem('clipacanvas.timeline.v1')"))
    active_box = next(clip for clip in stored["clips"] if clip["id"] == page.evaluate("timelineState.activeId"))
    assert "SCENE B" in active_box["code"], active_box

    names = page.locator(".logic-name").all_inner_texts()
    durations = page.locator(".logic-dur").all_inner_texts()
    print("names:", names, "durations:", durations)
    print("active:", page.locator(".logic-box.active .logic-name").inner_text())

    # Click the first box: editor and preview must load scene A.
    page.locator(".logic-box").nth(0).click()
    page.wait_for_timeout(600)
    editor_value = page.evaluate("document.getElementById('codeInput').value")
    print("first box loaded A:", "SCENE A" in editor_value)
    assert "SCENE A" in editor_value, "clicking box 1 did not load clip A"
    assert page.locator(".logic-box").nth(0).evaluate("el => el.classList.contains('active')")

    # Click the second box: editor loads scene B.
    page.locator(".logic-box").nth(1).click()
    page.wait_for_timeout(500)
    editor_value = page.evaluate("document.getElementById('codeInput').value")
    print("second box loaded B:", "SCENE B" in editor_value)
    assert "SCENE B" in editor_value, "clicking box 2 did not load clip B"

    # Resize the second box by dragging its handle left, then check persistence.
    handle = page.locator(".logic-box").nth(1).locator(".logic-resize")
    box = handle.bounding_box()
    page.mouse.move(box["x"] + 4, box["y"] + box["height"] / 2)
    page.mouse.down()
    page.mouse.move(box["x"] - 90, box["y"] + box["height"] / 2, steps=8)
    page.mouse.up()
    page.wait_for_timeout(400)
    durations = page.locator(".logic-dur").all_inner_texts()
    print("after resize durations:", durations)
    stored = json.loads(page.evaluate("localStorage.getItem('clipacanvas.timeline.v1')"))
    print("stored durations:", [c["duration"] for c in stored["clips"]])
    assert len(stored["clips"]) == 2

    # Reload and confirm both boxes and the active selection survive.
    page.reload(wait_until="load")
    page.wait_for_timeout(1200)
    assert page.locator(".logic-box").count() == 2, "timeline did not persist"
    labels = page.locator(".et-label").all_inner_texts()
    print("after reload layers:", labels)
    assert labels == ["V1"], "an empty extra layer survived the reload"
    active_name = page.locator(".logic-box.active .logic-name").inner_text()
    editor_value = page.evaluate("document.getElementById('codeInput').value")
    print("after reload active:", active_name, "editor has B:", "SCENE B" in editor_value)
    assert "SCENE B" in editor_value, "active clip code did not restore on reload"

    # Chat insert must edit only the active logic box and can set its length.
    page.evaluate("""async () => {
        await executeChatTool({ name: 'insert_animation_code', args: { duration: 2.4, code:
            '<!doctype html><html><body style="background:#00aa00">CHAT SCENE</body></html>' } });
    }""")
    page.wait_for_timeout(400)
    stored = json.loads(page.evaluate("localStorage.getItem('clipacanvas.timeline.v1')"))
    active_id = page.evaluate("timelineState.activeId")
    active_box = next(clip for clip in stored["clips"] if clip["id"] == active_id)
    print("chat edited active box:", "CHAT SCENE" in active_box["code"], active_box["duration"])
    assert "CHAT SCENE" in active_box["code"], "chat did not write into the active box"
    assert abs(active_box["duration"] - 2.4) < 0.001, active_box["duration"]
    snippets = page.locator(".logic-snippet").all_inner_texts()
    print("snippets:", snippets)

    # Rename via double click.
    page.locator(".logic-box.active .logic-name").dblclick()
    page.wait_for_timeout(150)
    page.locator(".logic-rename").fill("FINALE")
    page.locator(".logic-rename").press("Enter")
    page.wait_for_timeout(300)
    names = page.locator(".logic-name").all_inner_texts()
    print("renamed:", names)
    assert "FINALE" in names, names

    # Layers appear only when added: +LAYER adds V2 above the single timeline.
    page.click("#layerAdd")
    page.wait_for_timeout(300)
    labels = page.locator(".et-label").all_inner_texts()
    print("after add layer:", labels)
    assert labels == ["V2", "V1"], labels
    assert "2 LAYERS" in page.locator("#timelineMeta").inner_text()

    # Drag the active box right into free space: this changes its start time
    # without reordering or overlapping the clip before it.
    source = page.locator(".logic-box.active").bounding_box()
    page.mouse.move(source["x"] + 30, source["y"] + source["height"] / 2)
    page.mouse.down()
    page.mouse.move(source["x"] + 110, source["y"] + source["height"] / 2, steps=10)
    page.mouse.up()
    page.wait_for_timeout(400)
    stored = json.loads(page.evaluate("localStorage.getItem('clipacanvas.timeline.v1')"))
    moved = next(clip for clip in stored["clips"] if clip["name"] == "FINALE")
    print("moved start/track:", moved["start"], moved["track"])
    assert moved["start"] > 6, moved
    assert moved["track"] == 0, moved

    # Drag it up onto the empty V2 lane, then left along that empty track.
    source = page.locator(".logic-box.active").bounding_box()
    v2_lane = page.locator(".et-row").nth(0).locator(".et-lane").bounding_box()
    page.mouse.move(source["x"] + 30, source["y"] + source["height"] / 2)
    page.mouse.down()
    page.mouse.move(source["x"] + 30, v2_lane["y"] + v2_lane["height"] / 2, steps=8)
    page.mouse.up()
    page.wait_for_timeout(400)
    source = page.locator(".logic-box.active").bounding_box()
    v2_lane = page.locator(".et-row").nth(0).locator(".et-lane").bounding_box()
    page.mouse.move(source["x"] + 30, source["y"] + source["height"] / 2)
    page.mouse.down()
    page.mouse.move(v2_lane["x"] + 8, v2_lane["y"] + v2_lane["height"] / 2, steps=10)
    page.mouse.up()
    page.wait_for_timeout(400)
    stored = json.loads(page.evaluate("localStorage.getItem('clipacanvas.timeline.v1')"))
    moved = next(clip for clip in stored["clips"] if clip["name"] == "FINALE")
    print("layer moved:", moved["track"], moved["start"])
    assert moved["track"] == 1, moved
    assert moved["start"] < 1.5, moved

    # Add a layer.
    page.click("#layerAdd")
    page.wait_for_timeout(300)
    labels = page.locator(".et-label").all_inner_texts()
    print("after add layer:", labels)
    assert labels == ["V3", "V2", "V1"], labels
    assert "3 LAYERS" in page.locator("#timelineMeta").inner_text()

    # Duplicate then delete.
    page.click("#boxDup")
    page.wait_for_timeout(350)
    assert page.locator(".logic-box").count() == 3, "duplicate failed"
    page.click("#boxDel")
    page.wait_for_timeout(350)
    assert page.locator(".logic-box").count() == 2, "delete failed"

    # Empty extra layers collapse on reload; layers come from the clips.
    page.reload(wait_until="load")
    page.wait_for_timeout(1200)
    labels = page.locator(".et-label").all_inner_texts()
    print("after reload layers:", labels)
    assert labels == ["V2", "V1"], "empty V3 did not collapse on reload"

    # Chat add_scene creates a real separate scene box with its own code.
    page.evaluate("""async code => {
        const result = await executeChatTool({
            name: 'add_scene',
            args: { code, name: 'TITLE', layer: 'above', duration: 1.5 }
        });
        window.__addSceneResult = result;
    }""", CLIP_A.replace("SCENE A", "TITLE CARD"))
    page.wait_for_timeout(500)
    result = page.evaluate("window.__addSceneResult")
    print("add_scene result:", json.dumps(result)[:400])
    assert result["ok"], result
    assert result["scene"]["name"] == "TITLE", result
    assert result["scene"]["layer"] != "V1", "above layer did not rise above the selected scene"
    assert len(result["timeline"]["scenes"]) == 3, result["timeline"]
    assert page.locator(".logic-box").count() == 3, "add_scene did not create a box"
    assert "TITLE CARD" in page.evaluate("document.getElementById('codeInput').value")
    assert page.locator(".logic-box.active .logic-name").inner_text() == "TITLE"

    # add_scene without code is rejected; it never creates an empty box.
    rejected = page.evaluate("""async () => {
        return await executeChatTool({ name: 'add_scene', args: { name: 'NOPE' } });
    }""")
    assert not rejected["ok"], rejected
    assert page.locator(".logic-box").count() == 3

    # get_app_state exposes the whole timeline to the model.
    state = page.evaluate("""async () => await executeChatTool({ name: 'get_app_state', args: {} })""")
    print("app state timeline:", json.dumps(state["timeline"])[:400])
    assert len(state["timeline"]["scenes"]) == 3
    assert state["timeline"]["selectedSceneId"] == page.evaluate("timelineState.activeId")

    # Frame range trims the whole sequence.
    plan = page.evaluate("""() => {
        document.getElementById('renderStart').value = '0.25';
        document.getElementById('renderEnd').value = '0.75';
        const plan = buildTimelineRenderPlan();
        document.getElementById('renderStart').value = '';
        document.getElementById('renderEnd').value = '';
        return plan ? { start: plan.start, end: plan.end, total: plan.total, count: plan.clips.length } : null;
    }""")
    print("trimmed plan:", plan)
    assert plan and plan["count"] == 3, plan
    assert abs(plan["start"] - 0.25) < 0.001 and abs(plan["end"] - 0.75) < 0.001, plan

    page.screenshot(path=str(ROOT / "output" / "playwright" / "logic-timeline.png"), full_page=True)
    browser.close()

stop_server(server)
print("console errors:", errors)
assert not errors, errors
print("LOGIC TIMELINE UI OK")
