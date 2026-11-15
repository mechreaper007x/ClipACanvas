"""Packaged exe: adding an image to a code scene embeds it, never a new layer."""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402

DEBUG_PORT = 9436
EXE = ROOT / "dist" / "ClipACanvas.exe"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
assert EXE.exists(), "build dist/ClipACanvas.exe first"

with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    appdata.mkdir(parents=True)
    still = tmp / "scene-media.png"
    subprocess.run(
        [str(FFMPEG), "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(appdata)
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["APPDATA"] = str(tmp / "appdata-webview")
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    log = open(tmp / "packaged.log", "wb")
    proc = subprocess.Popen([str(EXE)], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(360):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("packaged app did not expose the CDP port")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
            page = None
            for _ in range(120):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "packaged page not found"
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.wait_for_function("() => typeof timelineState !== 'undefined'", timeout=60000)
            assert page.evaluate("() => GOLDFISH_SYSTEM_PROMPT.includes('local media and is allowed')"), "reviewer must allow /media/ scene assets"
            page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
            page.wait_for_timeout(400)

            page.set_input_files("#mediaInput", str(still))
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=60000)
            page.wait_for_timeout(600)
            asset = page.evaluate("() => ({id: timelineState.assets[0].id, url: timelineState.assets[0].url})")
            print("asset:", asset)

            page.evaluate("""() => {
                const code = (color) => '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:' + color + '}</style></head><body></body></html>';
                timelineState.clips = [
                    {id: 'scene-one', name: 'SCENE 01', code: code('#00c040'), duration: 6, start: 0, track: 0, explicitDuration: true, type: 'code'},
                    {id: 'scene-two', name: 'SCENE 02', code: code('#0040c0'), duration: 6, start: 6, track: 0, explicitDuration: true, type: 'code'}
                ];
                timelineState.layers = 1;
                timelineState.activeId = 'scene-one';
                timelineState.playhead = 1;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: false });
                renderLogicBoxes();
                updateStageTimeline();
                selectAsset(timelineState.assets[0].id);
            }""")
            page.wait_for_timeout(400)
            page.locator(".dock-bin").first.dblclick()
            page.wait_for_timeout(800)
            state = page.evaluate("""() => ({
                count: timelineState.clips.length,
                layers: timelineState.layers,
                one: timelineState.clips.find(c => c.id === 'scene-one').code,
                two: timelineState.clips.find(c => c.id === 'scene-two').code
            })""")
            print("double-click embed:", state["count"], state["layers"])
            assert state["count"] == 2 and state["layers"] == 1, state
            assert asset["url"] in state["one"] and "<img" in state["one"], state["one"][-300:]
            assert asset["url"] not in state["two"], state["two"][-200:]

            page.evaluate("""() => {
                const two = timelineState.clips.find(c => c.id === 'scene-two');
                two.code = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#0040c0}</style></head><body></body></html>';
                timelineState.activeId = two.id;
                timelineState.playhead = 7;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: false });
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(300)
            page.locator(".dock-bin .bin-insert").first.click()
            page.wait_for_timeout(800)
            plus = page.evaluate("() => ({count: timelineState.clips.length, layers: timelineState.layers, code: timelineState.clips.find(c => c.id === 'scene-two').code})")
            print("plus embed:", plus["count"], plus["layers"])
            assert plus["count"] == 2 and plus["layers"] == 1, plus
            assert asset["url"] in plus["code"] and "<img" in plus["code"], plus["code"][-300:]

            tool = page.evaluate(
                "async ([assetId]) => executeChatTool({name: 'put_media_in_scene', args: {assetId, sceneId: 'scene-one'}})",
                [asset["id"]],
            )
            print("agent tool:", tool.get("ok"), tool.get("scene"))
            assert tool["ok"] and tool["scene"]["id"] == "scene-one", tool

            # The agent writes inside the scene without copying the media tag:
            # the app keeps the existing media as the background layer.
            kept = page.evaluate("""async () => {
                const one = timelineState.clips.find(c => c.id === 'scene-one');
                timelineState.activeId = one.id;
                timelineState.playhead = 1;
                const before = {count: timelineState.clips.length, layers: timelineState.layers};
                const result = await executeChatTool({name: 'insert_animation_code', args: {
                    code: '<!doctype html><html><body style="margin:0;background:#000;overflow:hidden"><h1 style="position:fixed;top:10%;left:50%;transform:translateX(-50%);color:#fff;z-index:30">TITLE</h1></body></html>'
                }});
                return {before, result, after: {count: timelineState.clips.length, layers: timelineState.layers, code: one.code}};
            }""")
            print("agent in-scene edit:", kept["result"])
            assert kept["result"]["ok"] is True, kept["result"]
            assert kept["result"]["preservedMedia"] >= 1, kept["result"]
            assert kept["after"]["count"] == 2 and kept["after"]["layers"] == 1, kept["after"]
            assert "cc-scene-media" in kept["after"]["code"] and "TITLE" in kept["after"]["code"], kept["after"]["code"]
            assert kept["after"]["code"].index("cc-scene-media") < kept["after"]["code"].index("TITLE"), kept["after"]["code"]

            usage_ui = page.evaluate("""async () => {
                chatState.keys.gemini = 'fake-key';
                chatState.models.gemini = [{name: 'fake-model', displayName: 'Fake Model'}];
                chatState.modelPrefs.gemini = 'auto';
                const response = await fetch('/api/llm/usage');
                const payload = await response.json();
                await refreshLlmUsage();
                openComposerModelMenu();
                const block = document.querySelector('.chat-usage');
                const text = block ? block.textContent : '';
                closeComposerModelMenu();
                return {ok: payload.ok === true, hasBlock: Boolean(block), text};
            }""")
            print("packaged usage block:", usage_ui)
            assert usage_ui["ok"], usage_ui
            assert usage_ui["hasBlock"], usage_ui
            assert "Today" in usage_ui["text"], usage_ui
            assert not errors, errors

            browser.close()
            print("PASS packaged scene embed")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False)
        try:
            proc.wait(timeout=30)
        except Exception:
            proc.kill()
