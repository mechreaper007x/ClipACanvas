import base64
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
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
            assert "ANIMATION CODE" == page.locator("#codePaneTitle").inner_text()
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
            assert page.locator("#codePaneTitle").inner_text() == "PROJECT MEDIA"
            assert page.locator("#miRemoveScene").is_visible()

            browser.close()
            assert not errors, errors
            print("SCENE MEDIA REMOVE + DROP + DRAG CHECK: OK")
    finally:
        stop_server(server)
