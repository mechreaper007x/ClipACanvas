"""Scenes and the timeline are not capped at 40 clips or 60 seconds."""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-unlimited-")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1664, "height": 916})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)
        page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
        page.wait_for_timeout(300)

        created = page.evaluate("""() => {
          timelineState.clips.length = 0;
          timelineState.transitions.length = 0;
          timelineState.layers = 1;
          const code = '<!doctype html><html><body style="margin:0;background:#101010"></body></html>';
          const failures = [];
          for (let i = 0; i < 45; i += 1) {
            const result = createSceneClip({ name: `S${i + 1}`, code, duration: 4 });
            if (result.error) failures.push(`${i + 1}: ${result.error}`);
          }
          return {
            failures,
            count: timelineState.clips.length,
            total: timelineTotalSeconds(),
            lastStart: timelineState.clips[timelineState.clips.length - 1]?.start ?? null
          };
        }""")
        print("45 scenes:", created)
        assert not created["failures"], created
        assert created["count"] == 45, created
        assert created["total"] == 180, created
        assert created["lastStart"] == 176, created

        duplicated = page.evaluate("""() => {
          const last = timelineState.clips[timelineState.clips.length - 1];
          const result = projectOps.duplicateClip(last.id);
          return { result, count: timelineState.clips.length, total: timelineTotalSeconds() };
        }""")
        print("duplicate at 45:", duplicated["count"], duplicated["total"], duplicated["result"])
        assert duplicated["result"]["ok"], duplicated
        assert duplicated["count"] == 46, duplicated

        transitions = page.evaluate("""() => {
          const track = timelineState.clips.filter(clip => clip.track === 0)
            .slice().sort((a, b) => a.start - b.start);
          const results = [];
          for (let i = 0; i < track.length - 1; i += 1) {
            if (i >= 44) break;
            results.push(projectOps.addTransition({ fromClipId: track[i].id, toClipId: track[i + 1].id, type: 'dissolve' }));
          }
          return { count: timelineState.transitions.length, failures: results.filter(item => !item.ok).map(item => item.error) };
        }""")
        print("transitions:", transitions["count"], transitions["failures"][:3])
        assert not transitions["failures"], transitions
        assert transitions["count"] >= 44, transitions

        plan = page.evaluate("""() => {
          saveTimelineState(true);
          renderLogicBoxes();
          updateStageTimeline();
          const plan = buildTimelineRenderPlan();
          setPlayhead(170, { preview: false });
          return {
            clips: plan?.clips?.length ?? 0,
            total: plan?.total ?? 0,
            end: plan?.end ?? 0,
            maxStart: Math.max(...(plan?.clips || []).map(clip => Number(clip.start) || 0)),
            ruler: [...document.querySelectorAll('#timelineRuler span')].map(span => span.textContent),
            playhead: timelineState.playhead,
            playheadLabel: document.getElementById('timelineTime')?.textContent,
            payload: buildProjectFilePayload()
          };
        }""")
        print("plan:", {key: plan[key] for key in ("clips", "total", "end", "maxStart", "ruler", "playhead", "playheadLabel")})
        assert plan["clips"] == 46, plan["clips"]
        assert plan["total"] >= 184 and plan["end"] >= 184, plan
        assert plan["maxStart"] >= 180, plan
        assert any(':' in label for label in plan["ruler"]), plan["ruler"]
        assert plan["playhead"] == 170, plan
        assert plan["playheadLabel"].startswith("2:50"), plan["playheadLabel"]

        saved = page.evaluate("""async (payload) => {
          const response = await fetch(buildApiUrl('/api/project'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
          });
          return { status: response.status, body: await response.json() };
        }""", plan["payload"])
        print("backend save:", saved["status"], saved["body"].get("bytes"))
        assert saved["status"] == 200 and saved["body"].get("ok"), saved

        page.reload(wait_until="load")
        page.wait_for_timeout(1400)
        page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
        page.wait_for_selector('.logic-box', timeout=20000)
        restored = page.evaluate("""() => ({
          count: timelineState.clips.length,
          total: timelineTotalSeconds(),
          transitions: timelineState.transitions.length,
          lastStart: Math.max(...timelineState.clips.map(clip => Number(clip.start) || 0))
        })""")
        print("after reload:", restored)
        assert restored["count"] == 46, restored
        assert restored["total"] >= 184, restored
        assert restored["transitions"] >= 44, restored
        assert not errors, errors

        page.screenshot(path=str(ROOT / "output" / "playwright" / "timeline-unlimited.png"), full_page=True)
        browser.close()
finally:
    stop_server(server)

# The deterministic renderer must also accept clips past 60s.
import playwright_render
from serve import resolve_ffmpeg_exe

ffmpeg = resolve_ffmpeg_exe()
sequence_html = playwright_render.build_sequence_document([
    {"id": "a", "code": "<html><body style='background:#f00'></body></html>", "duration": 4, "start": 0, "track": 0},
    {"id": "b", "code": "<html><body style='background:#00f'></body></html>", "duration": 4, "start": 60, "track": 0},
])
assert 'data-start="60000"' in sequence_html, "clip start past 60s was clamped"

with tempfile.TemporaryDirectory() as tmp:
    output = Path(tmp) / "past-sixty.mp4"
    result = playwright_render.render_payload({
        "width": 320,
        "height": 240,
        "frameRate": 24,
        "maxDuration": 64,
        "minDuration": 1,
        "codec": "h264",
        "bitrate": "2M",
        "renderStart": 61,
        "renderEnd": 61.5,
        "clips": [
            {"code": "<!doctype html><html><body style='margin:0;background:#ff2200'></body></html>", "duration": 4, "start": 0},
            {"code": "<!doctype html><html><body style='margin:0;background:#0033ff'></body></html>", "duration": 4, "start": 60},
        ],
    }, output, ffmpeg_exe=ffmpeg)
    duration = float(result.get("duration") or 0)
    info = subprocess.run([ffmpeg, "-i", str(output)], capture_output=True).stderr.decode("utf-8", "replace")
    match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", info)
    assert match, info[-400:]
    file_duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
    raw = subprocess.run(
        [ffmpeg, "-v", "error", "-ss", "0.2", "-i", str(output),
         "-frames:v", "1", "-vf", "scale=2:2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
        capture_output=True, check=True,
    ).stdout
    pixel = (raw[0], raw[1], raw[2])
    print("past-60 render:", {key: result[key] for key in ("duration", "frameCount", "renderStart", "renderEnd")}, "file:", file_duration, "pixel:", pixel)
    assert 61 <= duration <= 61.5, duration
    assert 0.35 <= file_duration <= 0.7, file_duration
    assert pixel[2] > 140 and pixel[0] < 90, pixel

print("PASS unlimited scenes")
