"""Live CLIPPPA multi-scene check through the real chat UI.

Uses the stored provider key in an isolated data dir and asks for three tiny
scenes in one turn. Verifies that the agent calls the scene tools (now that the
Gemini function schema is valid) and that the timeline ends up with >1 scene.
"""
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

from serve import server_url, start_server, stop_server

APPDATA = Path(os.environ["APPDATA"]) / "ClipACanvas"


def copy_key_material(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for name in ("keys.dat", "keys.key"):
        source = APPDATA / name
        if source.exists():
            shutil.copy2(source, target / name)


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    data = tmp / "appdata"
    copy_key_material(data)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(data)
    server, thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1500)
            page.click("#tabAssistant")
            page.wait_for_selector("#chatInput", state="visible")
            page.fill(
                "#chatInput",
                "Create a three-scene micro test: scene one a solid red full-frame canvas, "
                "scene two solid green, scene three solid blue. Each exactly 1 second. "
                "Use insert_animation_code for the selected scene and add_scene for the other two. "
                "Do not paste code in chat, do not ask questions, do not stop until all three exist.",
            )
            page.click("#chatSend")

            deadline = time.time() + 300
            last_count = -1
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                clip_count = page.evaluate("timelineState.clips.length")
                code_count = page.evaluate("timelineState.clips.filter(c => c.type === 'code' && String(c.code).trim()).length")
                traces = page.evaluate("Array.from(document.querySelectorAll('.chat-tool-trace')).map(el => el.textContent.slice(0, 90))")
                if (clip_count, code_count) != last_count:
                    print("clips:", clip_count, "coded:", code_count, "traces:", traces[-4:], flush=True)
                    last_count = (clip_count, code_count)
                busy = page.evaluate("chatBusy")
                if not busy and code_count >= 2:
                    break
            page.wait_for_timeout(3000)
            result = page.evaluate("""() => ({
                clips: timelineState.clips.map(c => ({ name: c.name, type: c.type, start: c.start, duration: c.duration, code: String(c.code || '').length })),
                traces: Array.from(document.querySelectorAll('.chat-tool-trace')).map(el => el.textContent.slice(0, 120)),
                last: Array.from(document.querySelectorAll('.chat-msg')).slice(-4).map(el => el.textContent.slice(0, 160))
            })""")
            print("final clips:", result["clips"])
            print("tool traces:", result["traces"])
            print("last messages:", result["last"])
            print("page errors:", errors[:3])
            page.screenshot(path=str(ROOT / "output" / "playwright" / "clipppa-multiscene.png"), full_page=True)
            assert len([c for c in result["clips"] if c["code"] > 0]) >= 2, result["clips"]
            browser.close()
    finally:
        stop_server(server)
    print("PASS clipppa multi-scene")
