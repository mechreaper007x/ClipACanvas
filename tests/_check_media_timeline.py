import base64
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

# NLE media pipeline: project bin, insert edits, trims, split source ranges.
from serve import resolve_ffmpeg_exe, server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()


def probe_pixel(path: Path, seconds: float) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(seconds), "-i", str(path),
         "-frames:v", "1", "-vf", "scale=2:2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True,
        check=True,
    ).stdout
    return out[0], out[1], out[2]


def make_media(tmp: Path) -> tuple[Path, Path]:
    still = tmp / "still.png"
    subprocess.run(
        [ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00d040:s=320x180:d=1",
         "-frames:v", "1", str(still)],
        capture_output=True, check=True,
    )
    motion = tmp / "motion.mp4"
    subprocess.run(
        [ffmpeg, "-y",
         "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=0.6:r=24",
         "-f", "lavfi", "-i", "color=c=0xff3300:s=320x180:d=0.6:r=24",
         "-filter_complex", "[0:v][1:v]concat=n=2:v=1[v]", "-map", "[v]",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", "6", str(motion)],
        capture_output=True, check=True,
    )
    return still, motion


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    still_file, motion_file = make_media(tmp)
    server, thread = start_server()
    base = server_url(server)
    errors = []
    render_payloads = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1480, "height": 960})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))

            def remember_render(request):
                if request.url.endswith("/render") and request.method == "POST":
                    try:
                        render_payloads.append(json.loads(request.post_data or "{}"))
                    except ValueError:
                        pass

            page.on("request", remember_render)
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1200)
            page.evaluate("""() => {
                setResolutionValue('320x180');
                const fps = document.getElementById('frameRate');
                fps.value = '24';
                fps.dispatchEvent(new Event('change', { bubbles: true }));
            }""")

            # Import goes to the project bin only; it never auto-drops clips.
            page.set_input_files("#mediaInput", [str(still_file), str(motion_file)])
            page.wait_for_function("() => timelineState.assets.length === 2", timeout=60000)
            page.wait_for_timeout(1000)

            assets = page.evaluate("timelineState.assets.map(a => ({ id: a.id, name: a.name, kind: a.kind, duration: a.duration, url: a.url }))")
            print("project assets:", json.dumps(assets))
            assert len(assets) == 2, assets
            assert {asset["kind"] for asset in assets} == {"image", "video"}, assets
            assert all(asset["url"].startswith("/media/") for asset in assets), assets
            assert page.locator(".logic-box.media").count() == 0, "import auto-placed media on the timeline"
            assert page.evaluate("timelineState.clips.filter(c => c.type === 'code').length") == 1, "starter scene changed"
            assert page.locator("#binsCount").inner_text() == "2 ASSETS"
            assert page.locator(".dock-bin").count() == 2
            assert page.locator("#codePaneTitle").inner_text() == "PROJECT MEDIA"
            assert page.locator("#mediaInspector").is_visible()
            assert page.evaluate("document.getElementById('monacoHost').hidden")

            page.screenshot(path=str(ROOT / "output" / "playwright" / "media-project-bin.png"), full_page=True)

            still_id = next(asset["id"] for asset in assets if asset["kind"] == "image")
            video_id = next(asset["id"] for asset in assets if asset["kind"] == "video")
            video_duration = next(asset["duration"] for asset in assets if asset["kind"] == "video")

            # Insert the still at the playhead: the occupied V1 scene stays put and
            # the still lands as an overlay on V2.
            page.evaluate(f"selectAsset('{still_id}')")
            page.evaluate("setPlayhead(0)")
            page.click("#miInsert")
            page.wait_for_function("() => timelineState.clips.filter(c => c.type === 'image').length === 1", timeout=10000)
            page.wait_for_timeout(400)
            image_clip = page.evaluate("timelineState.clips.find(c => c.type === 'image')")
            print("image clip:", image_clip)
            assert image_clip["start"] == 0, image_clip
            assert abs(image_clip["duration"] - 3.0) < 0.01, image_clip
            assert image_clip["assetId"] == still_id, image_clip
            assert image_clip["track"] == 1, image_clip
            assert image_clip["code"] == "", "media clip stored a fake HTML wrapper"
            starter = page.evaluate("timelineState.clips.find(c => c.type === 'code')")
            assert starter["start"] == 0, starter
            assert page.locator("#codePaneTitle").inner_text() == "MEDIA CLIP"
            assert page.locator("#miInsert").is_hidden()

            # Insert the video at 3s, then use the inspector for length and slip.
            page.evaluate(f"selectAsset('{video_id}')")
            page.evaluate("setPlayhead(3.0)")
            page.click("#miInsert")
            page.wait_for_function("() => timelineState.clips.filter(c => c.type === 'video').length === 1", timeout=10000)
            page.wait_for_timeout(400)
            video_clip = page.evaluate("timelineState.clips.find(c => c.type === 'video')")
            print("video clip:", video_clip)
            assert abs(video_clip["start"] - 3.0) < 0.01, video_clip
            assert 1.0 <= video_clip["duration"] <= video_duration + 0.01, video_clip
            assert page.locator("#miSourceInField").is_visible()

            page.evaluate("""() => {
                const d = document.getElementById('miDuration');
                d.value = '0.6';
                d.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
            page.wait_for_timeout(300)
            video_clip = page.evaluate("timelineState.clips.find(c => c.type === 'video')")
            assert abs(video_clip["duration"] - 0.6) < 0.01, video_clip
            page.evaluate("""() => {
                const s = document.getElementById('miSourceIn');
                s.value = '0.6';
                s.dispatchEvent(new Event('change', { bubbles: true }));
            }""")
            page.wait_for_timeout(300)
            video_clip = page.evaluate("timelineState.clips.find(c => c.type === 'video')")
            print("slipped video:", {k: video_clip[k] for k in ('start', 'duration', 'sourceIn')})
            assert abs(video_clip["sourceIn"] - 0.6) < 0.01, video_clip
            assert abs(video_clip["duration"] - 0.6) < 0.01, video_clip

            # Left trim handle: trims the head and advances the source in point.
            reset = page.evaluate("""() => {
                const v = timelineState.clips.find(c => c.type === 'video');
                v.start = 3; v.duration = 1.2; v.sourceIn = 0;
                timelineState.activeId = v.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
                return v.id;
            }""")
            page.wait_for_timeout(250)
            handle = page.locator(".logic-box.media.video .logic-trim").first
            box = handle.bounding_box()
            page.mouse.move(box["x"] + 3, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + 30, box["y"] + box["height"] / 2, steps=8)
            page.mouse.up()
            page.wait_for_timeout(400)
            trimmed = page.evaluate(f"timelineState.clips.find(c => c.id === '{reset}')")
            print("left trimmed:", {k: trimmed[k] for k in ('start', 'duration', 'sourceIn')})
            assert trimmed["sourceIn"] > 0.02, trimmed
            assert trimmed["start"] > 3.0, trimmed
            assert trimmed["duration"] < 1.2, trimmed

            # Ripple delete: later clips shift left by the removed duration.
            page.evaluate("""() => {
                timelineState.clips.push({
                    id: 'box-ripple-probe', name: 'RIPPLE PROBE', code: '', duration: 1,
                    start: 8, track: 0, explicitDuration: true, type: 'code',
                    assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain'
                });
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            page.evaluate("() => { timelineState.activeId = 'box-ripple-probe'; saveTimelineState(true); renderLogicBoxes(); }")
            page.evaluate(f"selectAsset('{still_id}')")
            page.evaluate("setPlayhead(6.0)")
            page.click("#miInsert")
            page.wait_for_timeout(500)
            after_insert = page.evaluate("timelineState.clips.find(c => c.id === 'box-ripple-probe')")
            image_count = page.evaluate("timelineState.clips.filter(c => c.type === 'image').length")
            print("probe after insert:", after_insert["start"], "images:", image_count)
            assert image_count == 2, image_count
            assert after_insert["start"] >= 9.0, after_insert
            page.click("#boxDel")
            page.wait_for_timeout(400)
            after_delete = page.evaluate("timelineState.clips.find(c => c.id === 'box-ripple-probe')")
            print("probe after ripple delete:", after_delete["start"])
            assert abs(after_delete["start"] - 8.0) < 0.01, after_delete
            assert page.evaluate("timelineState.assets.length") == 2, "deleting a clip removed its project asset"
            page.evaluate("() => { timelineState.clips = timelineState.clips.filter(c => c.id !== 'box-ripple-probe'); saveTimelineState(true); renderLogicBoxes(); updateStageTimeline(); }")

            # Compact the media and split the video so the right half uses source-in 0.6.
            page.evaluate("""() => {
                const image = timelineState.clips.find(c => c.type === 'image');
                const video = timelineState.clips.find(c => c.type === 'video');
                timelineState.clips = [image, video];
                image.start = 0; image.duration = 0.8; image.track = 0; image.explicitDuration = true;
                video.start = 0.8; video.duration = 1.2; video.sourceIn = 0; video.track = 0; video.explicitDuration = true;
                timelineState.layers = 1;
                timelineState.activeId = video.id;
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""")
            page.evaluate("setPlayhead(1.4)")
            page.click("#boxSplit")
            page.wait_for_timeout(500)
            media_clips = page.evaluate("timelineState.clips.map(c => ({ type: c.type, start: c.start, duration: c.duration, sourceIn: c.sourceIn }))")
            print("after split:", media_clips)
            assert len(media_clips) == 3, media_clips
            right = next(clip for clip in media_clips if clip["start"] == 1.4)
            assert abs(right["sourceIn"] - 0.6) < 0.01, right
            assert abs(right["duration"] - 0.6) < 0.01, right
            assert page.evaluate("document.getElementById('miSourceIn').value") == "0.60"

            plan = page.evaluate("() => { const p = buildTimelineRenderPlan(); return p ? { total: p.total, count: p.clips.length, starts: p.clips.map(c => c.start), codes: p.clips.map(c => c.code.includes('http://127.0.0.1:')) } : null; }")
            print("media plan:", plan)
            assert plan and plan["count"] == 3, plan
            assert plan["starts"] == [0, 0.8, 1.4], plan
            assert all(plan["codes"]), plan

            page.evaluate("setFrameRange(0, 2)")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(400)

            assert render_payloads, "no /render request captured"
            payload = render_payloads[-1]
            payload_clips = payload.get("clips", [])
            print("payload clips:", [(clip.get("start"), clip.get("duration"), clip.get("track")) for clip in payload_clips])
            assert len(payload_clips) == 3, payload_clips
            for clip in payload_clips:
                assert "http://127.0.0.1:" in clip["code"], clip["code"][:200]
                assert 'src="/media/' not in clip["code"], "relative media URL leaked into the render payload"
                if "<video" in clip["code"]:
                    assert "data-source-in=" in clip["code"], clip["code"][:200]

            meta = page.evaluate("window.lastRenderMeta")
            print("render meta:", meta)
            duration = float(meta.get("duration") or 0)
            assert 1.8 <= duration <= 2.3, duration

            video_path = tmp / "rendered-media.mp4"
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
            print("rendered file:", video_path, video_path.stat().st_size)
            assert video_path.stat().st_size > 2000, video_path.stat().st_size
            still_pixel = probe_pixel(video_path, 0.3)
            blue_pixel = probe_pixel(video_path, 1.0)
            red_pixel = probe_pixel(video_path, 1.7)
            print("pixels still/blue/red:", still_pixel, blue_pixel, red_pixel)
            assert still_pixel[1] > 110 and still_pixel[0] < 90 and still_pixel[2] < 110, still_pixel
            assert blue_pixel[2] > 130 and blue_pixel[0] < 100, blue_pixel
            assert red_pixel[0] > 130 and red_pixel[2] < 100, red_pixel

            page.screenshot(path=str(ROOT / "output" / "playwright" / "media-timeline.png"), full_page=True)

            # Media clips survive a reload with assets, in points and no fake code.
            page.reload(wait_until="load")
            page.wait_for_timeout(1400)
            reloaded = page.evaluate("timelineState.clips.map(c => ({ type: c.type, name: c.name, url: c.mediaUrl, assetId: c.assetId, sourceIn: c.sourceIn, code: c.code }))")
            print("after reload:", reloaded)
            assert len(reloaded) == 3, reloaded
            assert [clip["type"] for clip in reloaded] == ["image", "video", "video"], reloaded
            assert all(clip["url"].startswith("/media/") for clip in reloaded), reloaded
            assert all(clip["assetId"] for clip in reloaded), reloaded
            assert next(clip for clip in reloaded if clip["sourceIn"] > 0)["sourceIn"] > 0, reloaded
            assert all(clip["code"] == "" for clip in reloaded), reloaded
            assert page.evaluate("timelineState.assets.length") == 2
            assert page.locator(".logic-box.media").count() == 3

            # Assistant code on a selected media clip creates a new code scene;
            # it never converts the user's media.
            page.locator(".logic-box.media").nth(0).click()
            page.wait_for_timeout(300)
            before_ids = page.evaluate("timelineState.clips.map(c => c.id)")
            page.evaluate("""async () => {
                await executeChatTool({
                    name: 'insert_animation_code',
                    args: {
                        code: '<!doctype html><html><body style="margin:0;background:#123456">CODE SCENE</body></html>',
                        duration: 1
                    }
                });
            }""")
            page.wait_for_timeout(500)
            kinds = page.evaluate("timelineState.clips.map(c => ({ id: c.id, type: c.type, url: c.mediaUrl, duration: c.duration }))")
            print("after agent insert:", kinds)
            assert len(kinds) == 4, kinds
            media_after = [clip for clip in kinds if clip["type"] != "code"]
            assert len(media_after) == 3, kinds
            assert all(clip["url"] for clip in media_after), kinds
            new_code = next(clip for clip in kinds if clip["id"] not in before_ids)
            assert new_code["type"] == "code" and new_code["url"] == "", new_code
            assert "CODE SCENE" in page.evaluate("document.getElementById('codeInput').value")
            browser.close()
    finally:
        stop_server(server)

    print("console errors:", errors)
    assert not errors, errors
    print("MEDIA TIMELINE OK")
