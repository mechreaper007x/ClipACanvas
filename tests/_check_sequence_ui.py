import json
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

from serve import server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

CLIP_RED = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#ff2200;overflow:hidden}
.box{width:30px;height:30px;background:#fff;animation:spin 1s linear infinite}
@keyframes spin{to{transform:rotate(360deg)}}
</style></head><body><div class="box"></div></body></html>"""

CLIP_BLUE = """<!doctype html><html><head><style>
html,body{margin:0;width:100%;height:100%;background:#0033ff;overflow:hidden}
</style></head><body></body></html>"""

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
        page.wait_for_timeout(800)
        page.evaluate("""([a, b]) => {
            localStorage.setItem('clipacanvas.timeline.v1', JSON.stringify({
                activeId: 'box-a',
                clips: [
                    { id: 'box-a', name: 'SCENE 01', code: a, duration: 0.5, explicitDuration: true },
                    { id: 'box-b', name: 'SCENE 02', code: b, duration: 0.5, explicitDuration: true }
                ]
            }));
            localStorage.setItem('clipacanvas.settings', JSON.stringify({
                resolution: '320x180', frameRate: '24', bitrate: '2M', codec: 'h264'
            }));
        }""", [CLIP_RED, CLIP_BLUE])
        page.reload(wait_until="load")
        page.wait_for_timeout(1200)

        assert page.locator(".logic-box").count() == 2, "seeded timeline missing"
        assert page.evaluate("document.getElementById('resolution').value") == "320x180"
        print("timeline:", page.locator("#timelineMeta").inner_text())

        page.click("#btnConvert")
        page.wait_for_function(
            "() => !document.getElementById('btnDownload').disabled && document.getElementById('statusBar').textContent.includes('ready')",
            timeout=150000,
        )
        page.wait_for_timeout(500)

        assert render_payloads, "no /render request captured"
        payload = render_payloads[-1]
        print("payload clips:", [(c["duration"], c["code"][:18]) for c in payload.get("clips", [])])
        print("payload range:", payload.get("renderStart"), payload.get("renderEnd"))
        assert len(payload.get("clips", [])) == 2, "render payload missing clips"
        assert abs(payload["renderEnd"] - 1.0) < 0.001, payload.get("renderEnd")
        assert [clip.get("start") for clip in payload["clips"]] == [0, 0.5], payload["clips"]
        assert [clip.get("track") for clip in payload["clips"]] == [0, 0], payload["clips"]

        meta = page.evaluate("window.lastRenderMeta")
        print("render meta:", meta)
        duration = float(meta.get("duration") or 0)
        assert 0.8 <= duration <= 1.1, duration
        dock = page.locator("#dockMeta").inner_text()
        print("dock:", dock)
        assert "2 CLIPS" in dock, dock
        assert "H264" in dock.upper() or "MP4" in dock.upper() or "H264" in dock, dock

        page.screenshot(path=str(ROOT / "output" / "playwright" / "sequence-render.png"), full_page=True)
        browser.close()
finally:
    stop_server(server)

print("console errors:", errors)
assert not errors, errors
print("SEQUENCE UI RENDER OK")
