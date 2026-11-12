"""Packaged CLIPPPA check: one chat turn must create multiple scenes via tools."""
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
EXE = ROOT / "dist" / "ClipACanvas.exe"
PORT = 9334

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

import psutil

APPDATA = Path(os.environ["APPDATA"]) / "ClipACanvas"


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
    tmp = Path(tmp_name)
    data = tmp / "appdata"
    data.mkdir(parents=True)
    for name in ("keys.dat", "keys.key"):
        source = APPDATA / name
        if source.exists():
            shutil.copy2(source, data / name)

    kill_all()
    env = os.environ.copy()
    env["CLIPACANVAS_KEYS_DIR"] = str(data)
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={PORT} --remote-allow-origins=*"
    proc = subprocess.Popen([str(EXE)], env=env)
    try:
        with sync_playwright() as pw:
            browser, page = attach(pw)
            page.click("#tabAssistant")
            page.wait_for_selector("#chatInput", state="visible")
            page.fill(
                "#chatInput",
                "Create a two-scene micro test: scene one a solid red full-frame canvas, "
                "scene two solid blue. Each exactly 1 second. Use insert_animation_code for the first "
                "and add_scene for the second. Do not paste code in chat, do not ask questions.",
            )
            page.click("#chatSend")
            deadline = time.time() + 300
            last = -1
            while time.time() < deadline:
                page.wait_for_timeout(3000)
                coded = page.evaluate("timelineState.clips.filter(c => c.type === 'code' && String(c.code).trim()).length")
                if coded != last:
                    print("coded scenes:", coded, flush=True)
                    last = coded
                if not page.evaluate("chatBusy") and coded >= 2:
                    break
            page.wait_for_timeout(2000)
            state = page.evaluate("""() => ({
                clips: timelineState.clips.map(c => ({ name: c.name, start: c.start, code: String(c.code || '').length })),
                traces: Array.from(document.querySelectorAll('.chat-tool-trace')).map(el => el.textContent.slice(0, 100)),
                disabled: Array.from(document.querySelectorAll('.chat-msg.error')).map(el => el.textContent.slice(0, 140))
            })""")
            print("state:", state)
            assert len([c for c in state["clips"] if c["code"] > 0]) >= 2, state
            assert any("add_scene" in trace for trace in state["traces"]), state
            page.screenshot(path=str(ROOT / "output" / "playwright" / "packaged-clipppa-multiscene.png"), full_page=True)
            browser.close()
    finally:
        kill_all()
    print("PASS packaged clipppa multi-scene")
