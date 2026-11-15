import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="cc-scene-embed-")
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()


def probe_pixel(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(seconds), "-i", str(path),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y},scale=2:2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return out[0], out[1], out[2]


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    still = tmp / "wide.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    server, thread = start_server()
    base = server_url(server)
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                if (!timelineState.clips.some(c => c.type === 'code')) createSceneClip({ layer: 'same' });
            }""")
            page.wait_for_timeout(300)
            page.evaluate("""() => {
                setResolutionValue('540x960');
                const fps = document.getElementById('frameRate');
                fps.value = '24';
                fps.dispatchEvent(new Event('change', { bubbles: true }));
            }""")

            page.set_input_files("#mediaInput", str(still))
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=30000)
            page.wait_for_timeout(600)

            page.evaluate("""() => {
                const scene = timelineState.clips.find(c => c.type === 'code');
                scene.code = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#00c040}</style></head><body></body></html>';
                timelineState.activeId = scene.id;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: true });
            }""")
            page.wait_for_timeout(500)

            asset_id = page.evaluate("timelineState.assets[0].id")
            asset_url = page.evaluate("timelineState.assets[0].url")
            page.evaluate(f"selectAsset('{asset_id}')")
            page.wait_for_timeout(300)
            embed = page.locator("#miEmbedScene")
            assert embed.is_visible(), "embed button missing for an image asset"
            print("embed label:", embed.inner_text())
            embed.click()
            page.wait_for_timeout(800)

            state = page.evaluate("() => ({ clips: timelineState.clips.length, layers: timelineState.layers, code: timelineState.clips.find(c => c.type === 'code').code })")
            print("clips/layers:", state["clips"], state["layers"])
            assert state["clips"] == 1 and state["layers"] == 1, "embedding created a separate clip/layer"
            assert "<img" in state["code"] and asset_url in state["code"], state["code"][-400:]
            assert state["code"].lower().rindex("<img") < state["code"].lower().rindex("</body>"), "media not inside the scene body"
            assert "inside" in page.locator("#statusBar").inner_text()
            assert page.locator("#codeClipName").inner_text().startswith("SCENE 01")
            assert page.locator("#clipInspector").is_visible()
            assert "clipacanvas-scene-media" in page.evaluate("document.getElementById('liveFrame').srcdoc")

            from PIL import Image

            def stage_pixels():
                shot_path = tmp / "stage.png"
                page.locator("#previewStage").screenshot(path=str(shot_path))
                shot = Image.open(shot_path).convert("RGB")
                w, h = shot.size
                return shot.getpixel((int(w * 0.03), int(h * 0.03))), shot.getpixel((int(w * 0.5), int(h * 0.5)))

            corner, center = stage_pixels()
            print("stage corner/center:", corner, center)
            assert corner[1] > 100 and corner[0] < 90, f"scene background missing: {corner}"
            assert center[0] > 140 and center[1] < 100 and center[2] > 140, f"embedded image missing in the scene preview: {center}"

            page.screenshot(path=str(ROOT / "output" / "playwright" / "scene-embed.png"), full_page=True)

            # Export the scene with the embedded image.
            page.evaluate("setFrameRange(0, 1)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
            video_path = tmp / "embed.mp4"
            video_b64 = page.evaluate("""async () => {
                const response = await fetch(resultVideoUrl);
                const buffer = await response.arrayBuffer();
                const bytes = new Uint8Array(buffer);
                let text = '';
                const chunk = 0x8000;
                for (let i = 0; i < bytes.length; i += chunk) {
                    text += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
                }
                return btoa(text);
            }""")
            video_path.write_bytes(base64.b64decode(video_b64))
            r_corner = probe_pixel(video_path, 0.4, 20, 20)
            r_center = probe_pixel(video_path, 0.4, 270, 480)
            print("render corner/center:", r_corner, r_center)
            assert r_corner[1] > 100 and r_corner[0] < 90, f"scene background missing from the render: {r_corner}"
            assert r_center[0] > 140 and r_center[1] < 100 and r_center[2] > 140, f"embedded image missing from the render: {r_center}"
            page.evaluate("() => clearResultVideo()")
            page.wait_for_timeout(200)

            # Removing: select the asset again, the inspector offers REMOVE FROM SCENE.
            page.evaluate(f"selectAsset('{asset_id}')")
            page.wait_for_timeout(300)
            remove = page.locator("#miRemoveScene")
            assert remove.is_visible(), "remove button missing after embedding"
            print("remove label:", remove.inner_text())
            remove.click()
            page.wait_for_timeout(700)
            code = page.evaluate("timelineState.clips.find(c => c.type === 'code').code")
            assert asset_url not in code and "<img" not in code, code[-300:]
            assert page.evaluate("timelineState.clips.length") == 1
            corner, center = stage_pixels()
            print("after remove stage corner/center:", corner, center)
            assert center[1] > 100 and center[0] < 90, f"image still visible after remove: {center}"

            # Drag the bin asset onto the stage: embedded at the drop point, no new clip.
            page.evaluate(f"selectAsset('{asset_id}')")
            page.wait_for_timeout(200)
            stage_box = page.locator("#previewStage").bounding_box()
            page.drag_and_drop(
                ".dock-bin",
                "#previewStage",
                target_position={"x": stage_box["width"] * 0.7, "y": stage_box["height"] * 0.3},
            )
            page.wait_for_timeout(900)
            code = page.evaluate("timelineState.clips.find(c => c.type === 'code').code")
            print("after drop tail:", code[-280:])
            assert "<img" in code and asset_url in code, code[-400:]
            assert page.evaluate("timelineState.clips.length") == 1
            left = float(re.search(r"left:([\d.]+)%", code).group(1))
            top = float(re.search(r"top:([\d.]+)%", code).group(1))
            print("drop position:", left, top)
            assert abs(left - 70) < 8, left
            assert abs(top - 30) < 8, top

            # Dragging the picture inside the preview moves it and writes the new position.
            frame = next(
                f for f in page.frames
                if f != page.main_frame and f.locator(".cc-scene-media").count()
            )
            box = frame.locator(".cc-scene-media").bounding_box()
            before_left = float(re.search(r"left:([\d.]+)%", code).group(1))
            before_top = float(re.search(r"top:([\d.]+)%", code).group(1))
            sx, sy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.mouse.move(sx, sy)
            page.mouse.down()
            page.mouse.move(sx + 60, sy + 60, steps=10)
            page.mouse.up()
            page.wait_for_timeout(500)
            code = page.evaluate("timelineState.clips.find(c => c.type === 'code').code")
            after_left = float(re.search(r"left:([\d.]+)%", code).group(1))
            after_top = float(re.search(r"top:([\d.]+)%", code).group(1))
            print("drag position before/after:", (before_left, before_top), (after_left, after_top))
            assert after_left - before_left > 8, (before_left, after_left)
            assert after_top - before_top > 5, (before_top, after_top)

            # Clicking the picture in the preview selects the asset in the bin,
            # so REMOVE FROM SCENE is one click away.
            assert page.locator("#mediaInspector").is_visible()
            assert page.locator("#inspectorTag").inner_text() == "MEDIA"
            assert page.locator("#miRemoveScene").is_visible()

            # Dropping the bin asset onto Scene 01's timeline box embeds it in
            # that scene's HTML instead of stacking a new layer on top.
            page.evaluate("""() => {
                const first = timelineState.clips.find(c => c.type === 'code');
                first.code = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#00c040}</style></head><body></body></html>';
                const second = JSON.parse(JSON.stringify(first));
                second.id = 'scene-two';
                second.name = 'SCENE 02';
                second.start = first.start + first.duration;
                second.code = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#0040c0}</style></head><body></body></html>';
                timelineState.clips.push(second);
                timelineState.activeId = first.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            page.wait_for_timeout(400)
            page.evaluate(f"selectAsset('{asset_id}')")
            page.wait_for_timeout(200)
            box = page.locator(".logic-box.code").first.bounding_box()
            page.drag_and_drop(
                ".dock-bin",
                ".logic-box.code",
                target_position={"x": box["width"] * 0.5, "y": box["height"] * 0.5},
            )
            page.wait_for_timeout(900)
            dropped = page.evaluate("""() => {
                const first = timelineState.clips.find(c => c.id === document.querySelector('.logic-box.code').dataset.id);
                return {
                    count: timelineState.clips.length,
                    layers: timelineState.layers,
                    first: first.code,
                    second: timelineState.clips.find(c => c.name === 'SCENE 02').code,
                    active: timelineState.activeId === first.id
                };
            }""")
            print("scene drop clips/layers:", dropped["count"], dropped["layers"])
            assert dropped["count"] == 2 and dropped["layers"] == 1, dropped
            assert asset_url in dropped["first"] and "<img" in dropped["first"], dropped["first"][-300:]
            assert asset_url not in dropped["second"], dropped["second"][-200:]
            assert dropped["active"], dropped
            assert "inside" in page.locator("#statusBar").inner_text()

            # The agent path uses the same embedding: sceneId + assetId, no layer.
            page.evaluate("""() => {
                const second = timelineState.clips.find(c => c.name === 'SCENE 02');
                second.code = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#0040c0}</style></head><body></body></html>';
                timelineState.activeId = second.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            tool = page.evaluate(
                "async ([assetId]) => executeChatTool({name: 'put_media_in_scene', args: {assetId, sceneId: 'scene-two', x: 30, y: 40}})",
                [asset_id],
            )
            print("agent put_media_in_scene:", tool.get("ok"), tool.get("scene"))
            assert tool["ok"], tool
            assert tool["scene"]["id"] == "scene-two", tool
            after_tool = page.evaluate("""() => {
                const second = timelineState.clips.find(c => c.id === 'scene-two');
                return {
                    count: timelineState.clips.length,
                    layers: timelineState.layers,
                    code: second.code,
                    active: timelineState.activeId === second.id
                };
            }""")
            assert after_tool["count"] == 2 and after_tool["layers"] == 1, after_tool
            assert asset_url in after_tool["code"] and "<img" in after_tool["code"], after_tool["code"][-300:]
            assert "left:30.0%" in after_tool["code"] and "top:40.0%" in after_tool["code"], after_tool["code"][-300:]
            assert after_tool["active"], after_tool
            missing = page.evaluate(
                "async () => executeChatTool({name: 'put_media_in_scene', args: {assetId: 'missing-asset'}})"
            )
            assert missing["ok"] is False, missing

            # Double-clicking the bin card adds the image to the selected
            # scene, not to a new layer above it.
            page.evaluate("""() => {
                const second = timelineState.clips.find(c => c.id === 'scene-two');
                second.code = '<!doctype html><html><head><style>html,body{margin:0;height:100%;background:#0040c0}</style></head><body></body></html>';
                timelineState.activeId = second.id;
                timelineState.playhead = second.start + 1;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: false });
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(400)
            page.locator(".dock-bin").first.dblclick()
            page.wait_for_timeout(800)
            binned = page.evaluate("""() => {
                const second = timelineState.clips.find(c => c.id === 'scene-two');
                return {
                    count: timelineState.clips.length,
                    layers: timelineState.layers,
                    code: second.code,
                    active: timelineState.activeId === second.id
                };
            }""")
            print("bin double-click scene embed:", binned["count"], binned["layers"])
            assert binned["count"] == 2 and binned["layers"] == 1, binned
            assert asset_url in binned["code"] and "<img" in binned["code"], binned["code"][-300:]
            assert binned["active"], binned

            # An EMPTY scene adopts the media as full-frame content instead of
            # showing a small picture floating on a blank page.
            page.evaluate("""() => {
                const two = timelineState.clips.find(c => c.id === 'scene-two');
                two.code = '';
                timelineState.activeId = two.id;
                timelineState.playhead = two.start + 1;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: false });
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(400)
            page.locator(".dock-bin").first.dblclick()
            page.wait_for_timeout(900)
            full = page.evaluate("() => timelineState.clips.find(c => c.id === 'scene-two').code")
            print("empty scene full-frame:", full[:240])
            assert full.strip().lower().startswith("<!doctype html"), full[:240]
            assert asset_url in full and 'data-cc-fill="1"' in full, full[:300]
            assert "width:100%;height:100%" in full, full[:300]
            shot_path = tmp / "full-scene.png"
            page.locator("#previewStage").screenshot(path=str(shot_path))
            full_shot = Image.open(shot_path).convert("RGB")
            fw, fh = full_shot.size
            f_corner = full_shot.getpixel((int(fw * 0.03), int(fh * 0.03)))
            f_center = full_shot.getpixel((int(fw * 0.5), int(fh * 0.5)))
            print("full-frame corner/center:", f_corner, f_center)
            assert f_corner[0] < 40 and f_corner[1] < 40 and f_corner[2] < 40, f_corner
            assert f_center[0] > 150 and f_center[1] < 100 and f_center[2] > 150, f_center

            # The agent must extend the selected scene in place when it already
            # contains embedded media, instead of adding an overlay layer.
            agent_state = page.evaluate("""() => {
                const two = timelineState.clips.find(c => c.id === 'scene-two');
                timelineState.activeId = two.id;
                timelineState.playhead = two.start + 1;
                const app = chatToolAppState();
                const msgs = buildChatApiMessages('add a title over it');
                return {
                    media: app.selectedClip.embeddedMedia,
                    cue: msgs.some(m => m.role === 'system' && m.content.includes('belong INSIDE this same document'))
                };
            }""")
            print("agent scene media:", agent_state)
            assert agent_state["media"] and agent_state["media"][0]["src"] == asset_url, agent_state
            assert agent_state["cue"], agent_state

            preserved = page.evaluate("""async () => {
                const two = timelineState.clips.find(c => c.id === 'scene-two');
                const before = { count: timelineState.clips.length, layers: timelineState.layers };
                const result = await executeChatTool({name: 'insert_animation_code', args: {
                    code: '<!doctype html><html><head><style>html,body{margin:0;background:#000;overflow:hidden}</style></head><body><h1 style="position:fixed;top:10%;left:50%;transform:translateX(-50%);color:#fff;z-index:30">TITLE</h1></body></html>'
                }});
                return { result, before, after: { count: timelineState.clips.length, layers: timelineState.layers, code: two.code, editor: document.getElementById('codeInput').value } };
            }""")
            print("agent omitted media -> kept:", preserved["result"])
            assert preserved["result"]["ok"] is True, preserved
            assert preserved["result"]["preservedMedia"] == 1, preserved
            assert preserved["after"]["count"] == preserved["before"]["count"], preserved
            assert preserved["after"]["layers"] == preserved["before"]["layers"], preserved
            assert "cc-scene-media" in preserved["after"]["code"] and "TITLE" in preserved["after"]["code"], preserved
            assert preserved["after"]["code"].index("cc-scene-media") < preserved["after"]["code"].index("TITLE"), "kept media must be the background layer"
            assert preserved["after"]["code"] == preserved["after"]["editor"], "editor did not receive the scene update"

            extended = page.evaluate("""async () => {
                const two = timelineState.clips.find(c => c.id === 'scene-two');
                const mediaTag = (two.code.match(/<img\\b[^>]*cc-scene-media[^>]*>/i) || [])[0];
                const code = '<!doctype html><html><head><style>html,body{margin:0;background:#000;overflow:hidden}</style></head><body>' + mediaTag + '<h1 style="position:fixed;left:50%;top:12%;transform:translateX(-50%);color:#fff;z-index:30">TITLE TWO</h1></body></html>';
                const result = await executeChatTool({name: 'insert_animation_code', args: { code }});
                return { result, count: timelineState.clips.length, layers: timelineState.layers, code: two.code, editor: document.getElementById('codeInput').value };
            }""")
            print("agent in-scene title:", extended["result"])
            assert extended["result"]["ok"] is True, extended
            assert extended["result"]["preservedMedia"] == 0, extended
            assert extended["count"] == 2 and extended["layers"] == 1, extended
            assert "cc-scene-media" in extended["code"] and "TITLE TWO" in extended["code"], extended
            assert extended["code"] == extended["editor"], "editor did not receive the scene update"

            removed = page.evaluate("""async () => {
                const two = timelineState.clips.find(c => c.id === 'scene-two');
                const result = await executeChatTool({name: 'insert_animation_code', args: {
                    code: '<!doctype html><html><head><style>html,body{margin:0;background:#000}</style></head><body><h1>ONLY TITLE</h1></body></html>',
                    removeMedia: true
                }});
                return { result, code: two.code, count: timelineState.clips.length };
            }""")
            print("agent explicit remove:", removed["result"])
            assert removed["result"]["ok"] is True, removed
            assert removed["result"]["preservedMedia"] == 0, removed
            assert "cc-scene-media" not in removed["code"], removed
            assert removed["count"] == 2, removed

            # Old projects saved a lone 72% media fragment; loading upgrades it
            # to the full-frame scene document without touching rich scenes.
            legacy = (
                '<video class="cc-scene-media" src="' + asset_url + '" data-media="wide" muted '
                'playsinline autoplay loop style="position:fixed;left:50.0%;top:50.0%;width:72%;'
                'height:auto;max-height:72%;transform:translate(-50%,-50%);object-fit:contain;z-index:20;"></video>'
            )
            upgraded = page.evaluate("(code) => upgradeLegacySceneMedia(code)", legacy)
            print("legacy upgrade:", upgraded[:180])
            assert upgraded.lower().startswith("<!doctype html"), upgraded[:200]
            assert 'data-cc-fill="1"' in upgraded and "width:100%;height:100%" in upgraded, upgraded[:300]
            rich = '<!doctype html><html><body style="background:#00c040"><img class="cc-scene-media" src="' + asset_url + '" style="width:72%"></body></html>'
            assert page.evaluate("(code) => upgradeLegacySceneMedia(code)", rich) == rich

            browser.close()
            assert not errors, errors
            print("SCENE MEDIA REMOVE + DROP + DRAG CHECK: OK")
    finally:
        stop_server(server)
