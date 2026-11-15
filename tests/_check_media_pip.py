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
    still = tmp / "pip.png"
    video = tmp / "base.mp4"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00c040:s=400x226:d=2:rate=24",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(video)],
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

            page.set_input_files("#mediaInput", [str(video), str(still)])
            page.wait_for_function("() => timelineState.assets.length === 2", timeout=60000)
            page.wait_for_timeout(600)
            asset_ids = page.evaluate("() => Object.fromEntries(timelineState.assets.map(a => [a.kind, a.id]))")
            urls = page.evaluate("() => Object.fromEntries(timelineState.assets.map(a => [a.kind, a.url]))")
            print("assets:", asset_ids, urls)

            page.evaluate("""({videoId}) => {
                timelineState.clips = [];
                timelineState.activeId = null;
                timelineState.layers = 1;
                const asset = timelineState.assets.find(a => a.id === videoId);
                insertAssetClip(asset, { track: 0, at: 0, duration: 2, mode: 'overwrite' });
            }""", {"videoId": asset_ids["video"]})
            page.wait_for_function("() => timelineState.clips.length === 1", timeout=10000)
            page.wait_for_timeout(500)
            video_clip_id = page.evaluate("timelineState.clips[0].id")
            page.evaluate(f"selectAsset('{asset_ids['image']}')")
            page.wait_for_timeout(300)

            embed = page.locator("#miEmbedScene")
            assert embed.is_visible(), "embed button missing for an image asset on a video clip"
            print("embed label:", embed.inner_text())
            assert "BASE" in embed.inner_text().upper(), embed.inner_text()
            page.evaluate(f"setPlayhead(0.5)")
            embed.click()
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=10000)
            page.wait_for_timeout(800)

            state = page.evaluate("""() => {
                const video = timelineState.clips.find(c => c.type === 'video');
                const overlay = timelineState.clips.find(c => c.parentClipId);
                return {
                    video: { id: video.id, start: video.start, duration: video.duration, track: video.track },
                    overlay: overlay ? {
                        id: overlay.id, start: overlay.start, duration: overlay.duration,
                        track: overlay.track, parentClipId: overlay.parentClipId, code: overlay.code
                    } : null,
                    layers: timelineState.layers,
                    activeId: timelineState.activeId
                };
            }""")
            print("state:", state["video"], {k: state["overlay"][k] for k in ("start", "duration", "track", "parentClipId")})
            overlay = state["overlay"]
            assert overlay, "media embed did not create an attached overlay"
            assert overlay["parentClipId"] == video_clip_id, overlay
            assert overlay["start"] == state["video"]["start"], overlay
            assert abs(overlay["duration"] - state["video"]["duration"]) < 0.01, overlay
            assert overlay["track"] == state["video"]["track"] + 1, overlay
            assert urls["image"] in overlay["code"] and "cc-scene-media" in overlay["code"], overlay["code"]
            assert "background:transparent" in overlay["code"], overlay["code"][:300]
            assert state["layers"] == 2, state
            assert "inside" in page.locator("#statusBar").inner_text()
            # The new overlay is attached and selected, ready to edit.
            assert state["activeId"] == overlay["id"], state

            srcdoc = page.evaluate("document.getElementById('liveFrame').srcdoc")
            assert srcdoc.count('<iframe class="cc-layer"') == 2, srcdoc[:400]
            assert urls["video"] in srcdoc and urls["image"] in srcdoc, srcdoc[:800]

            stage_shot = tmp / "stage.png"
            page.locator("#previewStage").screenshot(path=str(stage_shot))
            from PIL import Image
            shot = Image.open(stage_shot).convert("RGB")
            w, h = shot.size
            band = shot.getpixel((int(w * 0.5), int(h * 0.37)))
            center = shot.getpixel((int(w * 0.5), int(h * 0.5)))
            print("stage band/center:", band, center)
            assert band[1] > 120 and band[0] < 90, f"video layer missing under the pip: {band}"
            assert center[0] > 150 and center[1] < 100 and center[2] > 150, f"pip image missing in preview: {center}"

            # Dragging the picture on the preview repositions the attached
            # overlay even when its media parent is the selected clip.
            with_bot = page.evaluate("""({url, videoId}) => {
                timelineState.activeId = videoId;
                return sceneMediaOwner(url);
            }""", {"url": urls["image"], "videoId": video_clip_id})
            print("owner with video selected:", with_bot["id"])
            assert with_bot["id"] == overlay["id"], with_bot["id"]

            frame = next(
                f for f in page.frames
                if f != page.main_frame and f.locator(".cc-scene-media").count()
            )
            box = frame.locator(".cc-scene-media").bounding_box()
            before_code = page.evaluate("timelineState.clips.find(c => c.parentClipId).code")
            sx, sy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
            page.mouse.move(sx, sy)
            page.mouse.down()
            page.mouse.move(sx + 60, sy + 60, steps=10)
            page.mouse.up()
            page.wait_for_timeout(500)
            after_code = page.evaluate("timelineState.clips.find(c => c.parentClipId).code")
            before_left = float(re.search(r"left:([\d.]+)%", before_code).group(1))
            after_left = float(re.search(r"left:([\d.]+)%", after_code).group(1))
            before_top = float(re.search(r"top:([\d.]+)%", before_code).group(1))
            after_top = float(re.search(r"top:([\d.]+)%", after_code).group(1))
            print("pip drag:", (before_left, before_top), "->", (after_left, after_top))
            assert after_left - before_left > 8, (before_left, after_left)
            assert after_top - before_top > 5, (before_top, after_top)

            # Remove from scene deletes the generated pip overlay, keeps the video.
            page.evaluate(f"selectAsset('{asset_ids['image']}')")
            page.wait_for_timeout(300)
            remove = page.locator("#miRemoveScene")
            assert remove.is_visible(), "remove button missing for the pip overlay"
            print("remove label:", remove.inner_text())
            remove.click()
            page.wait_for_timeout(700)
            left = page.evaluate("() => ({ count: timelineState.clips.length, types: timelineState.clips.map(c => c.type), active: timelineState.clips.find(c => c.id === timelineState.activeId)?.type })")
            print("after remove:", left)
            assert left["count"] == 1 and left["types"] == ["video"], left
            assert left["active"] == "video", left

            # Export shows only the video once the pip is removed.
            page.evaluate("setFrameRange(0, 1)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
            video_path = tmp / "pip.mp4"
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
            r_top = probe_pixel(video_path, 0.4, 270, 40)
            r_center = probe_pixel(video_path, 0.4, 270, 480)
            print("render top/center:", r_top, r_center)
            assert r_top[0] < 60 and r_top[1] < 60 and r_top[2] < 60, f"unexpected content above the video: {r_top}"
            assert r_center[1] > 120 and r_center[0] < 90 and r_center[2] < 90, f"video missing or pip still present: {r_center}"

            # An empty code scene adopts the video as its full-frame content.
            page.evaluate("() => clearResultVideo()")
            page.wait_for_timeout(300)
            page.evaluate("""() => {
                timelineState.clips = [{
                    id: 'scene-full', name: 'SCENE 01', code: '', duration: 2, start: 0,
                    track: 0, explicitDuration: true, type: 'code'
                }];
                timelineState.layers = 1;
                timelineState.activeId = 'scene-full';
                timelineState.playhead = 0.5;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: false });
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(300)
            page.evaluate(f"selectAsset('{asset_ids['video']}')")
            page.wait_for_timeout(200)
            page.locator(f'.dock-bin[data-asset-id="{asset_ids["video"]}"]').dblclick()
            page.wait_for_timeout(900)
            full = page.evaluate("""() => ({
                count: timelineState.clips.length,
                layers: timelineState.layers,
                code: timelineState.clips[0].code
            })""")
            print("empty scene video full-frame:", full["count"], full["layers"], full["code"][:180])
            assert full["count"] == 1 and full["layers"] == 1, full
            assert "<video" in full["code"] and urls["video"] in full["code"], full["code"][:300]
            assert 'data-cc-fill="1"' in full["code"] and "width:100%;height:100%" in full["code"], full["code"][:300]
            full_shot = tmp / "scene-full.png"
            page.locator("#previewStage").screenshot(path=str(full_shot))
            full_img = Image.open(full_shot).convert("RGB")
            fw, fh = full_img.size
            f_corner = full_img.getpixel((int(fw * 0.03), int(fh * 0.03)))
            f_center = full_img.getpixel((int(fw * 0.5), int(fh * 0.5)))
            print("full video corner/center:", f_corner, f_center)
            assert f_corner[0] < 50 and f_corner[1] < 50 and f_corner[2] < 50, f_corner
            assert f_center[1] > 120 and f_center[0] < 90 and f_center[2] < 90, f_center

            browser.close()
            assert not errors, errors
            print("MEDIA PIP CHECK: OK")
    finally:
        stop_server(server)
