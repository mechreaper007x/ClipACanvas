import base64
import os
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

            # Bin thumbnail shows the whole picture (contain) over a blurred backdrop.
            bin_art = page.evaluate("""() => {
                const img = document.querySelector('.bin-art img');
                const style = img ? getComputedStyle(img) : null;
                return {
                    fit: style ? style.objectFit : null,
                    natural: img ? [img.naturalWidth, img.naturalHeight] : null,
                    client: img ? [img.clientWidth, img.clientHeight] : null
                };
            }""")
            print("bin art:", bin_art)
            assert bin_art["fit"] == "contain", bin_art

            # Bin card keeps a 16:9 thumbnail instead of stretching to panel height.
            art_box = page.locator(".dock-bin .bin-art").first.bounding_box()
            print("bin art box:", art_box)
            assert art_box["height"] < 120, art_box
            assert abs(art_box["width"] / art_box["height"] - 16 / 9) < 0.2, art_box

            # Insert at playhead over the occupied V1 scene: overlay lands on V2.
            asset_id = page.evaluate("timelineState.assets[0].id")
            page.evaluate("""() => {
                const scene = timelineState.clips.find(c => c.type === 'code');
                scene.code = '<!doctype html><html><body style="margin:0;background:#00c040"></body></html>';
                timelineState.activeId = scene.id;
                saveTimelineState(true);
                applyActiveClipToEditor({ preview: true });
            }""")
            page.wait_for_timeout(400)
            page.evaluate(f"selectAsset('{asset_id}')")
            page.evaluate("setPlayhead(0)")
            page.click("#miInsert")
            page.wait_for_function("() => timelineState.clips.filter(c => c.type === 'image').length === 1", timeout=10000)
            page.wait_for_timeout(700)
            state = page.evaluate("() => ({ clips: timelineState.clips.map(c => ({ type: c.type, start: c.start, duration: c.duration, track: c.track })), layers: timelineState.layers })")
            print("after overlay insert:", state)
            image_clip = next(clip for clip in state["clips"] if clip["type"] == "image")
            scene_clip = next(clip for clip in state["clips"] if clip["type"] == "code")
            assert image_clip["track"] == 1, state
            assert scene_clip["start"] == 0 and abs(scene_clip["duration"] - 6) < 0.01, state
            assert state["layers"] == 2, state
            assert page.locator(".et-row").count() == 2
            assert "overlay" in page.locator("#statusBar").inner_text()

            # The stage preview composites BOTH layers at the playhead.
            srcdoc = page.evaluate("document.getElementById('liveFrame').srcdoc")
            assert srcdoc.count('<iframe class="cc-layer"') == 2, srcdoc[:400]
            assert "/media/media-" in srcdoc, "media layer missing from the composite preview"
            stage_shot = tmp / "stage.png"
            page.locator("#previewStage").screenshot(path=str(stage_shot))
            from PIL import Image
            shot = Image.open(stage_shot).convert("RGB")
            w, h = shot.size
            corner = shot.getpixel((int(w * 0.03), int(h * 0.03)))
            center = shot.getpixel((int(w * 0.5), int(h * 0.5)))
            print("stage corner/center:", corner, center)
            assert corner[1] > 100 and corner[0] < 90, f"scene layer not under the photo in preview: {corner}"
            assert center[0] > 140 and center[1] < 100 and center[2] > 140, f"photo layer missing from preview: {center}"

            # Dragging the photo over the scene moves it onto a free layer above.
            page.evaluate("""() => {
                const img = timelineState.clips.find(c => c.type === 'image');
                const scene = timelineState.clips.find(c => c.type === 'code');
                img.track = 0; img.start = 0; img.duration = 3;
                scene.track = 0; scene.start = 3; scene.duration = 6;
                timelineState.layers = 1;
                timelineState.activeId = img.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            page.wait_for_timeout(300)
            box = page.locator(".logic-box.media").first.bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 + 450, box["y"] + box["height"] / 2, steps=14)
            page.mouse.up()
            page.wait_for_timeout(500)
            moved = page.evaluate("timelineState.clips.find(c => c.type === 'image')")
            print("after drag over scene:", {k: moved[k] for k in ("start", "track")})
            assert moved["track"] >= 1, "media drag was blocked instead of layering above the scene"
            assert moved["start"] >= 2.5, moved
            scene_after = page.evaluate("timelineState.clips.find(c => c.type === 'code')")
            assert scene_after["start"] == 3 and abs(scene_after["duration"] - 6) < 0.01, scene_after

            page.screenshot(path=str(ROOT / "output" / "playwright" / "media-overlay-fixed.png"), full_page=True)

            # Export composites the still over the scene below it, unstretched.
            page.evaluate("""() => {
                const img = timelineState.clips.find(c => c.type === 'image');
                const scene = timelineState.clips.find(c => c.type === 'code');
                img.start = 0; img.duration = 1; img.track = 1;
                scene.start = 0; scene.duration = 1; scene.track = 0;
                scene.code = '<!doctype html><html><body style="margin:0;background:#00c040"></body></html>';
                timelineState.clips = [scene, img];
                timelineState.activeId = img.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            page.evaluate("setFrameRange(0, 1)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
            video_path = tmp / "overlay.mp4"
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
            top = probe_pixel(video_path, 0.4, 270, 40)
            middle = probe_pixel(video_path, 0.4, 270, 480)
            print("frame top/middle:", top, middle)
            assert top[1] > 120 and top[0] < 80, f"scene layer missing under the still: {top}"
            assert middle[0] > 150 and middle[1] < 90 and middle[2] > 150, middle

            browser.close()
            assert not errors, errors
            print("MEDIA OVERLAY + THUMBNAIL CHECK: OK")
    finally:
        stop_server(server)
