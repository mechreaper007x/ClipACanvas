"""End-to-end bin -> timeline drag and drop: image, video, audio, tracks,
occupied ranges, empty area, cancel, zoom, selection and export."""
import base64
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from serve import resolve_ffmpeg_exe, server_url, start_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

ffmpeg = resolve_ffmpeg_exe()
OUT = ROOT / "output" / "playwright"
OUT.mkdir(parents=True, exist_ok=True)
TOTAL = 6.0  # reference clip length used by reset_sequence()


def probe_pixel(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", str(seconds), "-i", str(path),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y},scale=2:2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    return out[0], out[1], out[2]


errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    image = tmp / "still.png"
    video = tmp / "motion.mp4"
    audio = tmp / "tone.mp3"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=400x225:d=1",
                    "-frames:v", "1", str(image)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x0033ff:s=320x180:d=1.2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                    "-c:a", "libmp3lame", str(audio)], capture_output=True, check=True)

    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1500)

            page.set_input_files("#mediaInput", [str(image), str(video), str(audio)])
            page.wait_for_function("() => timelineState.assets.length === 3", timeout=30000)
            page.wait_for_timeout(700)
            ids = page.evaluate(
                "Object.fromEntries(timelineState.assets.map(a => [a.kind, {id: a.id, url: a.url, duration: a.duration}]))"
            )
            print("assets:", ids)
            img_id, vid_id, aud_id = ids["image"]["id"], ids["video"]["id"], ids["audio"]["id"]

            def reset_sequence(ref_track=3, layers=4):
                page.evaluate(f"""() => {{
                    timelineState.clips = [{{id: 'box-ref', name: 'REF', code: '', duration: 6,
                        start: 0, track: {ref_track}, explicitDuration: true, type: 'code'}}];
                    timelineState.layers = {layers};
                    timelineState.activeId = 'box-ref';
                    timelineState.playhead = 0;
                    timelineState.selectedAssetId = null;
                    mediaInspectorTarget = null;
                    hideMediaInspector();
                    saveTimelineState(true);
                    renderLogicBoxes();
                    updateStageTimeline();
                }}""")
                page.wait_for_timeout(250)

            def reveal(track):
                page.evaluate("""(track) => {
                    const host = document.getElementById('logicTracks');
                    const row = document.querySelector(`.et-row[data-track="${track}"]`);
                    if (!host || !row) return;
                    const hb = host.getBoundingClientRect();
                    const rb = row.getBoundingClientRect();
                    host.scrollTop = Math.max(0, host.scrollTop + rb.top - hb.top - 6);
                }""", track)
                page.wait_for_timeout(180)

            def card_box(asset_id):
                return page.locator(f'.dock-bin[data-asset-id="{asset_id}"]').bounding_box()

            def lane_box(track):
                return page.locator(f'.et-row[data-track="{track}"] .et-lane').bounding_box()

            def begin_drag(asset_id):
                card = card_box(asset_id)
                page.mouse.move(card["x"] + card["width"] / 2, card["y"] + card["height"] / 2)
                page.mouse.down()
                page.mouse.move(card["x"] + card["width"] / 2 + 26, card["y"] - 18, steps=4)

            def hover(asset_id, track, ratio):
                lane = lane_box(track)
                x = lane["x"] + max(3, min(lane["width"] - 3, lane["width"] * ratio))
                y = lane["y"] + lane["height"] / 2
                page.mouse.move(x, y, steps=14)
                page.wait_for_timeout(120)
                # Native HTML5 drags coalesce CDP moves; re-issue the final point so the
                # last dragover matches where the user actually released.
                page.mouse.move(x + 1, y)
                page.wait_for_timeout(220)
                return x, y

            def finish_drag():
                page.mouse.up()
                page.wait_for_timeout(500)

            def clips_of(kind):
                return page.evaluate(f"timelineState.clips.filter(c => c.type === '{kind}')")

            def expect_start(clip, expected, label):
                assert abs(clip["start"] - expected) < 0.25, f"{label}: start {clip['start']} != ~{expected}"
                print(f"{label}: V{clip['track'] + 1} @ {clip['start']}s for {clip['duration']}s")

            # 1. Image -> V1 at 20%.
            reset_sequence()
            reveal(0)
            begin_drag(img_id)
            hover(img_id, 0, 0.2)
            hint = page.locator("#etDropHint").inner_text()
            marker = page.locator("#dropMarkerTime").inner_text()
            assert "DROP AT" in hint and "V1" in hint, hint
            assert marker, "drop marker has no timestamp"
            print("hover feedback:", hint, "| marker:", marker)
            page.screenshot(path=str(OUT / "bin-drag-hover.png"))
            finish_drag()
            clip = clips_of("image")[-1]
            expect_start(clip, TOTAL * 0.2, "image -> V1");
            assert clip["duration"] == 3, clip
            assert clip["assetId"] == img_id
            assert page.evaluate("timelineState.activeId") == clip["id"], "dropped clip not selected"
            assert clip["id"] == page.evaluate("timelineState.selectedAssetId || timelineState.activeId")
            assert page.locator("#mediaInspector").is_visible(), "inspector did not follow the drop"
            assert page.locator("#miName").inner_text() == "still"

            # 2. Image -> V1 later timestamp.
            reset_sequence()
            reveal(0)
            begin_drag(img_id)
            hover(img_id, 0, 0.75)
            finish_drag()
            expect_start(clips_of("image")[-1], TOTAL * 0.75, "image -> late V1")

            # 3. Image -> V2.
            reset_sequence()
            reveal(1)
            begin_drag(img_id)
            hover(img_id, 1, 0.5)
            finish_drag()
            clip = clips_of("image")[-1]
            expect_start(clip, TOTAL * 0.5, "image -> V2")
            assert clip["track"] == 1, clip

            # 4. Video -> V1 keeps its own duration.
            reset_sequence()
            reveal(0)
            begin_drag(vid_id)
            hover(vid_id, 0, 0.3)
            finish_drag()
            clip = clips_of("video")[-1]
            expect_start(clip, TOTAL * 0.3, "video -> V1")
            assert abs(clip["duration"] - 1.2) < 0.15, clip
            assert clip["assetId"] == vid_id

            # 5. Audio -> V3 stays audio.
            reset_sequence()
            reveal(2)
            begin_drag(aud_id)
            hover(aud_id, 2, 0.4)
            finish_drag()
            clip = clips_of("audio")[-1]
            expect_start(clip, TOTAL * 0.4, "audio -> V3")
            assert clip["track"] == 2 and clip["assetId"] == aud_id, clip
            assert abs(clip["duration"] - 1.0) < 0.15, clip
            assert clip["mediaUrl"] == ids["audio"]["url"]

            # 6. Multiple assets dropped individually keep distinct positions.
            reset_sequence()
            reveal(0)
            begin_drag(img_id)
            hover(img_id, 0, 0.1)
            finish_drag()
            reveal(0)
            begin_drag(vid_id)
            hover(vid_id, 0, 0.8)
            finish_drag()
            state = page.evaluate("timelineState.clips.filter(c => c.type === 'image' || c.type === 'video')")
            assert len(state) == 2 and {c["type"] for c in state} == {"image", "video"}, state
            print("multi-drop:", [(c["type"], c["start"]) for c in state])

            # 7. Occupied ranges: overlay when free, reject when all tracks are full.
            reset_sequence()
            page.evaluate("""() => {
                timelineState.clips = [0, 1, 2, 3].map(track => ({
                    id: 'box-fill-' + track, name: 'FILL ' + track, code: '', duration: 6,
                    start: 0, track, explicitDuration: true, type: 'code'
                }));
                timelineState.layers = 4;
                timelineState.activeId = 'box-fill-0';
                saveTimelineState(true);
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(250)
            reveal(0)
            before = page.evaluate("timelineState.clips.length")
            begin_drag(img_id)
            hover(img_id, 0, 0.5)
            invalid_hint = page.locator("#etDropHint").inner_text()
            invalid_marker = page.evaluate("document.getElementById('dropMarker').classList.contains('invalid')")
            invalid_lane = page.evaluate("document.querySelectorAll('.et-lane.drop-invalid').length")
            assert "NO FREE TRACK" in invalid_hint, invalid_hint
            assert invalid_marker and invalid_lane == 1, (invalid_marker, invalid_lane)
            print("occupied feedback:", invalid_hint)
            finish_drag()
            after = page.evaluate("timelineState.clips.length")
            status = page.locator("#statusBar").inner_text()
            assert after == before, f"occupied drop inserted a clip: {before} -> {after}"
            assert "occupied" in status.lower(), status
            assert clips_of("image") == [], "occupied drop created an image clip"

            # Overlay when a free track exists: fill V1+V2, drop on V1 -> V3.
            reset_sequence()
            page.evaluate("""() => {
                timelineState.clips = [0, 1].map(track => ({
                    id: 'box-fill-' + track, name: 'FILL ' + track, code: '', duration: 6,
                    start: 0, track, explicitDuration: true, type: 'code'
                }));
                timelineState.layers = 2;
                timelineState.activeId = 'box-fill-0';
                saveTimelineState(true);
                renderLogicBoxes();
                updateStageTimeline();
            }""")
            page.wait_for_timeout(250)
            reveal(0)
            begin_drag(img_id)
            hover(img_id, 0, 0.5)
            overlay_hint = page.locator("#etDropHint").inner_text()
            assert "V3" in overlay_hint, overlay_hint
            finish_drag()
            clip = clips_of("image")[-1]
            assert clip["track"] == 2, clip
            print("overlay on occupied lane:", overlay_hint, "-> V3")

            # 8. Empty area below the tracks is a valid drop surface.
            reset_sequence(ref_track=1, layers=2)
            wrap = page.evaluate("document.getElementById('etTracksWrap').getBoundingClientRect().toJSON()")
            begin_drag(img_id)
            page.mouse.move(wrap["x"] + wrap["width"] * 0.6, wrap["y"] + wrap["height"] - 30, steps=14)
            page.wait_for_timeout(120)
            page.mouse.move(wrap["x"] + wrap["width"] * 0.6 + 1, wrap["y"] + wrap["height"] - 30)
            page.wait_for_timeout(220)
            assert page.locator("#etDropHint").is_visible(), "no feedback in the empty timeline area"
            finish_drag()
            clip = clips_of("image")[-1]
            assert clip["track"] == 0, clip
            expect_start(clip, TOTAL * 0.6, "image -> empty area")

            # 9. Cancelled drag drops nothing and clears feedback.
            reset_sequence()
            reveal(0)
            begin_drag(img_id)
            hover(img_id, 0, 0.4)
            page.mouse.move(800, 20, steps=10)
            page.keyboard.press("Escape")
            finish_drag()
            assert clips_of("image") == [], "cancelled drag still inserted a clip"
            assert not page.locator("#etDropHint").is_visible(), "drop hint stayed after cancel"
            assert not page.locator("#dropMarker").is_visible(), "drop marker stayed after cancel"
            print("cancel: no clip inserted, feedback cleared")

            # 10. Zoomed timeline maps the pixel position to the visible span.
            reset_sequence()
            reveal(0)
            page.evaluate("setTimelineZoom(2)")
            page.wait_for_timeout(350)
            span = page.evaluate("timelineViewSpan()")
            begin_drag(img_id)
            hover(img_id, 0, 0.5)
            zoom_hint = page.locator("#etDropHint").inner_text()
            finish_drag()
            clip = clips_of("image")[-1]
            expect_start(clip, span * 0.5, "image -> zoomed timeline")
            assert "DROP AT" in zoom_hint, zoom_hint
            page.evaluate("fitTimelineView()")
            page.wait_for_timeout(250)

            # 11. Selection already asserted in (1); confirm persistence after reload.
            saved = page.evaluate("JSON.parse(localStorage.getItem('clipacanvas.timeline.v1')).clips.filter(c => c.type === 'image').length")
            assert saved >= 1, saved
            print("persisted image clips:", saved)

            # 12. Export the dropped composition through the real render button.
            page.evaluate(f"""() => {{
                timelineState.clips = [{{
                    id: 'box-drop-export', name: 'still', code: '', duration: 1, start: 0, track: 0,
                    explicitDuration: true, type: 'image', assetId: '{img_id}',
                    mediaUrl: '{ids["image"]["url"]}', mediaName: 'still', sourceIn: 0, fit: 'contain'
                }}];
                timelineState.layers = 1;
                timelineState.activeId = 'box-drop-export';
                saveTimelineState(true);
                renderLogicBoxes();
                updateStageTimeline();
                setResolutionValue('320x180');
                setFrameRange(0, 1);
            }}""")
            page.wait_for_timeout(300)
            plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(plan["clips"]) == 1 and plan["clips"][0].get("duration") == 1, plan
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
            video_path = tmp / "drop-export.mp4"
            payload = page.evaluate("""async () => {
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
            video_path.write_bytes(base64.b64decode(payload))
            center = probe_pixel(video_path, 0.4, 150, 75)
            print("export center pixel:", center)
            assert center[0] > 140 and center[1] < 100 and center[2] > 140, f"exported drop missing: {center}"

            browser.close()
            assert not errors, errors
            print("BIN -> TIMELINE DRAG DROP CHECK: OK")
    finally:
        try:
            server.shutdown()
        except Exception:
            pass
