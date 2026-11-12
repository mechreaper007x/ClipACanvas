"""Transition engine: presets, custom code, preview/export parity, persistence."""
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
RED = '<!doctype html><html><body style="margin:0;background:#ff0000"></body></html>'
BLUE = '<!doctype html><html><body style="margin:0;background:#0000ff"></body></html>'


def probe_pixel(path: Path, seconds: float, x: int, y: int) -> tuple[int, int, int]:
    out = subprocess.run(
        [ffmpeg, "-v", "error", "-i", str(path), "-ss", str(seconds),
         "-frames:v", "1", "-vf", f"crop=2:2:{x}:{y},scale=2:2",
         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    if len(out) < 3:
        raise AssertionError(f"no frame decoded at {seconds}s")
    return out[0], out[1], out[2]


def composite_frame(page, predicate: str):
    for frame in page.frames:
        try:
            if frame.evaluate(f"() => Boolean({predicate})"):
                return frame
        except Exception:
            continue
    return None


errors = []
with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(tmp / "appdata")
    video = tmp / "handle.mp4"
    green = tmp / "green.mp4"
    magenta = tmp / "magenta.mp4"
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00aa33:s=320x180:d=2:r=24",
                    "-pix_fmt", "yuv420p", str(video)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0x00c040:s=320x180:d=3:r=24",
                    "-pix_fmt", "yuv420p", str(green)], capture_output=True, check=True)
    subprocess.run([ffmpeg, "-y", "-f", "lavfi", "-i", "color=c=0xff00ff:s=320x180:d=3:r=24",
                    "-pix_fmt", "yuv420p", str(magenta)], capture_output=True, check=True)

    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={"width": 1664, "height": 916})
            page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(f"{base}/clipacanvas.html", wait_until="load")
            page.wait_for_timeout(1400)

            def ops(name, *args):
                return page.evaluate("([name, args]) => projectOps[name](...args)", [name, list(args)])

            def tool(name, args):
                return page.evaluate("async ([name, args]) => executeChatTool({name, args})", [name, args])

            page.evaluate("""() => {
                timelineState.clips = [];
                timelineState.transitions = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                timelineState.selectedAssetId = null;
                saveTimelineState(true);
                renderLogicBoxes(); renderProjectBin(); updateStageTimeline();
            }""")
            a = ops("createComposition", {"name": "RED", "code": RED, "start": 0, "duration": 2, "track": 0})
            b = ops("createComposition", {"name": "BLUE", "code": BLUE, "start": 2, "duration": 2, "track": 0})
            assert a["ok"] and b["ok"], (a, b)
            a_id, b_id = a["clipId"], b["clipId"]

            # 1. Add a centered dissolve through projectOps.
            added = ops("addTransition", {
                "fromClipId": a_id, "toClipId": b_id,
                "type": "dissolve", "duration": 1, "alignment": "center",
            })
            assert added["ok"], added
            transition_id = added["transition"]["id"]
            summary = page.evaluate("transitionSummaryForChat()")
            assert len(summary) == 1, summary
            assert abs(summary[0]["windowStartSeconds"] - 1.5) < 1e-6, summary
            assert abs(summary[0]["windowEndSeconds"] - 2.5) < 1e-6, summary
            assert page.evaluate("timelineState.transitions.length") == 1
            print("dissolve window:", summary[0]["windowStartSeconds"], summary[0]["windowEndSeconds"])

            # 2. Program Monitor scrubbing uses the same engine; at the cut both
            # layers are visible at 50% opacity.
            page.evaluate("setPlayhead(2.0, { preview: true })")
            page.wait_for_timeout(900)
            state = page.evaluate("previewCompositeState")
            assert state["active"] and state["count"] == 2, state
            frame = composite_frame(page, "document.querySelectorAll('.cc-layer').length === 2")
            assert frame is not None, "composite iframe missing"
            layers = frame.evaluate("""() => Array.from(document.querySelectorAll('.cc-layer')).map(el => ({
                opacity: el.style.opacity,
                visibility: el.style.visibility,
                clipPath: el.style.clipPath || '',
                transform: el.style.transform || ''
            }))""")
            print("mid-transition layers:", layers)
            opacities = [layer["opacity"] for layer in layers]
            assert any(value and abs(float(value) - 0.5) < 0.01 for value in opacities), layers
            assert any(value == "" for value in opacities), layers
            assert all(layer["visibility"] == "visible" for layer in layers), layers

            def composite_pixel():
                shot = page.locator("#liveFrame").screenshot()
                png = tmp / "preview.png"
                png.write_bytes(shot)
                box = page.locator("#liveFrame").bounding_box()
                return probe_pixel(png, 0.0, int(box["width"] / 2), int(box["height"] / 2))

            mid_pixel = composite_pixel()
            print("preview pixel at cut:", mid_pixel)
            assert mid_pixel[0] > 100 and mid_pixel[2] > 100 and mid_pixel[1] < 60, mid_pixel

            page.evaluate("setPlayhead(1.55, { preview: true })")
            page.wait_for_timeout(700)
            early = composite_pixel()
            print("preview pixel early:", early)
            assert early[0] > early[2] + 40, early

            page.evaluate("setPlayhead(2.45, { preview: true })")
            page.wait_for_timeout(700)
            late = composite_pixel()
            print("preview pixel late:", late)
            assert late[2] > late[0] + 40, late

            # 3. Playback drives the transition without reloading layers.
            page.evaluate("setPlayhead(1.3, { preview: true })")
            page.wait_for_timeout(500)
            page.evaluate("togglePlayback()")
            page.wait_for_timeout(900)
            assert page.evaluate("previewCompositeState.active") is True
            playing = composite_frame(page, "document.querySelectorAll('.cc-layer').length === 2")
            assert playing is not None
            live_progress = playing.evaluate("""() => {
                const op = Array.from(document.querySelectorAll('.cc-layer')).map(el => Number(el.style.opacity));
                return { visible: op.filter(value => value > 0 && value < 1).length, values: op };
            }""")
            page.evaluate("stopPlayback(false)")
            print("playback opacities:", live_progress)
            assert live_progress["visible"] >= 1, live_progress

            # 4. Every preset validates and can be applied.
            presets = page.evaluate("transitionTypeList().map(item => item.id)")
            assert len(presets) >= 10, presets
            for preset in presets:
                updated = ops("updateTransition", transition_id, {"type": preset, "duration": 1})
                assert updated["ok"], (preset, updated)
            print("presets applied:", presets)

            # 5. Custom transitions follow the renderTransition contract.
            custom_code = """function renderTransition(ctx) {
  const p = ctx.progress;
  return {
    outgoing: { opacity: 1 - p, transform: 'translateX(' + (-100 * p) + '%)' },
    incoming: { opacity: p, transform: 'translateX(' + (100 * (1 - p)) + '%)' }
  };
}"""
            custom = ops("updateTransition", transition_id, {"type": "custom", "code": custom_code})
            assert custom["ok"], custom
            page.evaluate("setPlayhead(2.0, { preview: true })")
            page.wait_for_timeout(900)
            frame = composite_frame(page, "window.__ccSetCompositeTime && document.querySelectorAll('.cc-layer').length === 2")
            transforms = frame.evaluate("""() => Array.from(document.querySelectorAll('.cc-layer')).map(el => el.style.transform)""")
            print("custom transforms:", transforms)
            assert any("translateX" in value for value in transforms), transforms
            blocked = ops("updateTransition", transition_id, {
                "type": "custom",
                "code": "function renderTransition(ctx){ fetch('http://x'); return {}; }",
            })
            assert blocked["ok"] is False and "blocked" in blocked["error"], blocked
            missing = ops("updateTransition", transition_id, {"type": "custom", "code": "const x = 1;"})
            assert missing["ok"] is False and "renderTransition" in missing["error"], missing

            # 6. Wipe uses clip-path; fade-black dips through black.
            wipe = ops("updateTransition", transition_id, {
                "type": "wipe", "duration": 1, "alignment": "center", "params": {"direction": "left"},
            })
            assert wipe["ok"], wipe
            page.evaluate("setPlayhead(2.0, { preview: true })")
            page.wait_for_timeout(800)
            frame = composite_frame(page, "document.querySelectorAll('.cc-layer').length === 2")
            clip_paths = frame.evaluate("""() => Array.from(document.querySelectorAll('.cc-layer')).map(el => el.style.clipPath)""")
            print("wipe clip paths:", clip_paths)
            assert any("inset" in value for value in clip_paths), clip_paths

            fade = ops("updateTransition", transition_id, {"type": "fade-black", "duration": 1, "alignment": "center"})
            assert fade["ok"], fade
            page.evaluate("setPlayhead(2.0, { preview: true })")
            page.wait_for_timeout(900)
            dark = composite_pixel()
            print("fade-black midpoint:", dark)
            assert max(dark) < 40, dark

            # 7. Handle validation: touching gaps, clip length, video handles.
            gap = ops("moveClip", b_id, {"track": 0, "at": 2.5})
            assert gap["ok"], gap
            assert page.evaluate("timelineState.transitions.length") == 0, "transition must prune on a gap"
            gap_add = ops("addTransition", {"fromClipId": a_id, "toClipId": b_id, "type": "dissolve"})
            assert gap_add["ok"] is False, gap_add
            ops("moveClip", b_id, {"track": 0, "at": 2})
            too_long = ops("addTransition", {
                "fromClipId": a_id, "toClipId": b_id, "type": "dissolve", "duration": 3,
            })
            assert too_long["ok"] is False, too_long

            page.set_input_files("#mediaInput", [str(video)])
            page.wait_for_function("() => timelineState.assets.length === 1", timeout=30000)
            page.wait_for_timeout(500)
            asset_id = page.evaluate("timelineState.assets[0].id")
            v1 = ops("insertAsset", asset_id, {"track": 1, "at": 0})
            v2 = ops("insertAsset", asset_id, {"track": 1, "at": 2})
            print("video clips:", v1, v2)
            assert v1["ok"] and v2["ok"], (v1, v2)
            handle_error = ops("addTransition", {
                "fromClipId": v1["clipId"], "toClipId": v2["clipId"], "type": "dissolve", "duration": 1,
            })
            print("handle validation:", handle_error)
            assert handle_error["ok"] is False and ("handle" in handle_error["error"] or "footage" in handle_error["error"]), handle_error

            # 8. Restore a simple dissolve for the export and persistence checks.
            page.evaluate("""([aId]) => {
                timelineState.clips = timelineState.clips.filter(c => c.type === 'code');
                timelineState.transitions = [];
                timelineState.activeId = aId;
                applyActiveClipToEditor({ preview: false });
                saveTimelineState(true); renderLogicBoxes(); updateStageTimeline();
            }""", [a_id])
            final = ops("addTransition", {
                "fromClipId": a_id, "toClipId": b_id, "type": "dissolve", "duration": 1, "alignment": "center",
            })
            assert final["ok"], final
            page.wait_for_timeout(300)

            # 9. Export the transition window; the same engine must render it.
            page.evaluate("setResolutionValue('320x180')")
            page.click("#tabRecipe")
            page.wait_for_timeout(250)
            page.select_option("#frameRate", "24")
            page.evaluate("setFrameRange(1.4, 2.6)")
            page.wait_for_timeout(300)
            plan = page.evaluate("buildTimelineRenderPlan()")
            assert len(plan["clips"]) == 2, plan
            assert len(plan["transitions"]) == 1, plan
            assert all("ff0000" in clip["code"].lower() or "0000ff" in clip["code"].lower() for clip in plan["clips"]), plan
            assert "CCTransitions" in page.evaluate("transitionEngineSource()")
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
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
            video_path = tmp / "transition.mp4"
            video_path.write_bytes(base64.b64decode(payload))
            (OUT / "transition-export.mp4").write_bytes(video_path.read_bytes())
            print("render meta:", page.evaluate("window.lastRenderMeta || {}"))
            start_px = probe_pixel(video_path, 0.02, 160, 90)
            mid_px = probe_pixel(video_path, 0.6, 160, 90)
            end_px = probe_pixel(video_path, 1.18, 160, 90)
            print("export pixels start/mid/end:", start_px, mid_px, end_px)
            assert start_px[0] > start_px[2] + 60, start_px
            assert end_px[2] > end_px[0] + 60, end_px
            assert mid_px[0] > 100 and mid_px[2] > 100, mid_px

            # 10. Persistence and the timeline badge.
            badge = page.locator('.logic-transition').first
            assert badge.count() == 1, badge.count()
            page.reload(wait_until="load")
            page.wait_for_timeout(1600)
            restored = page.evaluate("transitionSummaryForChat()")
            assert len(restored) == 1 and restored[0]["type"] == "dissolve", restored
            assert page.locator(".logic-transition").count() == 1
            print("persisted transition:", restored[0]["type"], restored[0]["durationSeconds"])

            # 11. Agent tool path.
            tool_update = tool("update_transition", {"type": "push", "direction": "up", "duration": 0.8})
            assert tool_update["ok"], tool_update
            tool_remove = tool("remove_transition", {})
            assert tool_remove["ok"], tool_remove
            assert page.evaluate("timelineState.transitions.length") == 0

            # 12. Toolbar dialog: add, edit from the badge, remove.
            ops("selectClip", a_id)
            page.wait_for_timeout(250)
            page.click("#transitionAdd")
            page.wait_for_timeout(250)
            assert page.locator("#transitionModal").is_visible()
            options = page.evaluate("Array.from(document.querySelectorAll('#trType option')).map(o => o.value)")
            assert "custom" in options and "wipe" in options, options
            page.select_option("#trType", "wipe")
            assert page.locator("#trDirectionField").is_visible()
            assert not page.locator("#trColorField").is_visible()
            page.select_option("#trDirection", "right")
            page.fill("#trDuration", "0.8")
            page.click("#trApply")
            page.wait_for_timeout(500)
            assert not page.locator("#transitionModal").is_visible()
            created = page.evaluate("transitionSummaryForChat()")
            assert len(created) == 1 and created[0]["type"] == "wipe", created
            assert abs(page.evaluate("timelineState.playhead") - 2.0) < 0.08
            page.click(".logic-transition")
            page.wait_for_timeout(250)
            assert page.locator("#transitionModal").is_visible()
            assert page.evaluate("document.getElementById('trType').value") == "wipe"
            assert page.locator("#trRemove").is_visible()
            page.fill("#trDuration", "1")
            page.click("#trApply")
            page.wait_for_timeout(400)
            edited = page.evaluate("transitionSummaryForChat()")
            assert edited[0]["durationSeconds"] == 1, edited
            page.click(".logic-transition")
            page.wait_for_timeout(250)
            page.click("#trRemove")
            page.wait_for_timeout(400)
            assert page.evaluate("timelineState.transitions.length") == 0
            assert page.locator(".logic-transition").count() == 0
            print("dialog add/edit/remove: OK")

            # 13. Media transition with real handles: outgoing footage continues
            # past its out point and the incoming clip pre-rolls from its in point.
            page.set_input_files("#mediaInput", [str(green), str(magenta)])
            page.wait_for_function("() => timelineState.assets.length >= 3", timeout=45000)
            page.wait_for_timeout(800)
            media_test = page.evaluate("""() => {
                const greenId = timelineState.assets.find(a => a.name.startsWith('green')).id;
                const magentaId = timelineState.assets.find(a => a.name.startsWith('magenta')).id;
                timelineState.clips = [];
                timelineState.transitions = [];
                timelineState.layers = 1;
                timelineState.activeId = null;
                timelineState.playhead = 0;
                saveTimelineState(true);
                const first = projectOps.insertAsset(greenId, {track: 0, at: 0});
                const second = projectOps.insertAsset(magentaId, {track: 0, at: 3});
                const trimFirst = projectOps.trimClip(first.clipId, {end: 2.5});
                const trimSecond = projectOps.trimClip(second.clipId, {start: 3.5});
                const moved = projectOps.moveClip(second.clipId, {track: 0, at: 2.5});
                const transition = projectOps.addTransition({
                    fromClipId: first.clipId, toClipId: second.clipId,
                    type: 'dissolve', duration: 0.5, alignment: 'center'
                });
                return { trimFirst, trimSecond, moved, transition,
                         sourceIn: timelineState.clips.find(c => c.id === second.clipId).sourceIn };
            }""")
            assert media_test["transition"]["ok"], media_test
            assert abs(media_test["sourceIn"] - 0.5) < 0.01, media_test
            page.evaluate("setResolutionValue('320x180')")
            page.evaluate("setFrameRange(2.4, 2.6)")
            page.wait_for_timeout(300)
            page.click("#btnConvert")
            page.wait_for_function(
                "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
                timeout=180000,
            )
            page.wait_for_timeout(300)
            payload2 = page.evaluate("""async () => {
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
            media_path = tmp / "media-transition.mp4"
            media_path.write_bytes(base64.b64decode(payload2))
            (OUT / "transition-media.mp4").write_bytes(media_path.read_bytes())
            media_start = probe_pixel(media_path, 0.01, 160, 90)
            media_mid = probe_pixel(media_path, 0.1, 160, 90)
            media_end = probe_pixel(media_path, 0.19, 160, 90)
            print("media transition pixels:", media_start, media_mid, media_end)
            assert media_start[1] > 120 and media_start[0] < 90, media_start
            assert media_end[0] > 150 and media_end[1] < 90, media_end
            assert media_mid[0] > 60 and media_mid[1] > 60, media_mid

            browser.close()
            assert not errors, errors
            print("TRANSITIONS: OK")
    finally:
        server.shutdown()
