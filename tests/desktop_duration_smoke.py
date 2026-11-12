"""Duration classification smoke test for clipacanvas.html.

Starts the local server, loads the desktop UI in Chromium, and verifies the
/render payload duration logic for JS-cycle canvas pages, CSS-loop DOM pages,
plain rAF canvas pages, and manual clip-length overrides.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from serve import server_url, start_server, stop_server  # noqa: E402

GOTHAM = (
    Path(
        r"C:\Users\Savyasachi Mishra\.qoder\tmp\C--Users-Savyasachi-Mishra-Desktop-clipacanvas"
        r"\attachments\39ca18d3-3ff4-4fc1-b47e-af5498e45cee\6baf62f6-4672-4214-b913-af472c5bbf4e.txt"
    )
    .read_text(encoding="utf-8")
    .strip()
)

CSS_LOOP = """<!DOCTYPE html><html><head><style>
@keyframes spin { to { transform: rotate(360deg); } }
.box { animation: spin 8s linear infinite; width: 200px; height: 200px; background: #c8ff00; }
</style></head><body><div class="box"></div></body></html>"""

RAF_CANVAS = """<!DOCTYPE html><html><body><canvas id="c"></canvas><script>
const ctx = document.getElementById('c').getContext('2d');
let x = 0;
function loop() { x += 1; ctx.clearRect(0, 0, 300, 150); ctx.fillRect(x % 300, 0, 10, 10); requestAnimationFrame(loop); }
loop();
</script></body></html>"""


def main() -> int:
    server, thread = start_server()
    base = server_url(server)
    print("base:", base)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        from patchright.sync_api import sync_playwright  # type: ignore

    errors: list[str] = []
    payloads: list[dict] = []
    results: dict[str, dict] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.on("pageerror", lambda exc: errors.append(str(exc)))

        def capture(route):
            if route.request.method == "POST" and route.request.url.endswith("/render"):
                try:
                    payloads.append(json.loads(route.request.post_data or "{}"))
                except Exception as exc:  # noqa: BLE001
                    errors.append(f"payload parse: {exc}")
            route.fulfill(
                status=200,
                headers={
                    "Content-Type": "video/mp4",
                    "X-Render-Duration": "1.0",
                    "X-Render-Frame-Count": "60",
                    "X-Render-Codec": "h264",
                    "X-Render-Content-Hash": "test",
                    "X-Render-Filename": "test.mp4",
                },
                body=b"fakevideo",
            )

        page.route("**/render", capture)

        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)

        def click_convert() -> None:
            # The result panel can overlay the Convert button after a render,
            # so trigger it directly instead of using pointer events.
            page.evaluate("() => document.getElementById('btnConvert').click()")

        def set_code(code: str) -> None:
            page.evaluate("""code => {
                const editor = document.getElementById('codeInput');
                editor.value = code;
                editor.dispatchEvent(new Event('input', { bubbles: true }));
            }""", code)

        def set_select(element_id: str, value: str) -> None:
            page.evaluate("""([elementId, next]) => {
                const el = document.getElementById(elementId);
                el.value = next;
                el.dispatchEvent(new Event('change', { bubbles: true }));
            }""", [element_id, value])

        def convert(code: str) -> dict:
            set_code(code)
            page.wait_for_timeout(200)
            click_convert()
            deadline = time.time() + 15
            while time.time() < deadline:
                if "ready" in page.locator("#statusBar").inner_text().lower():
                    break
                page.wait_for_timeout(300)
            return payloads[-1] if payloads else {}

        # 1. Canvas page with a JS cycle: duration should come from the loop.
        results["js-cycle"] = convert(GOTHAM)

        # 2. DOM page with an 8s CSS loop: duration should be 8.25.
        results["css-loop"] = convert(CSS_LOOP)

        # 3. Canvas page without a detectable cycle: default 12s cap, and the
        #    frame-rate select must actually feed the render payload.
        page.wait_for_timeout(200)
        set_select("frameRate", "30")
        results["raf-canvas"] = convert(RAF_CANVAS)
        set_select("frameRate", "60")

        # 4. Manual clip length wins over classification.
        set_code(GOTHAM)
        page.wait_for_timeout(200)
        set_select("clipLength", "4")
        click_convert()
        deadline = time.time() + 15
        while time.time() < deadline:
            if len(payloads) == 4:
                break
            page.wait_for_timeout(300)
        results["manual-4s"] = payloads[-1] if len(payloads) == 4 else {}
        set_select("clipLength", "auto")

        browser.close()

    stop_server(server)
    thread.join(timeout=2)

    def close(value: float) -> float:
        return round(value, 2)

    print("\n--- payloads ---")
    for name, payload in results.items():
        compact = {k: payload.get(k) for k in ("maxDuration", "minDuration", "renderEnd", "contentMode", "frameRate")}
        print(f"{name}:", compact)

    checks = []
    checks.append(("js-cycle maxDuration", close(results["js-cycle"].get("maxDuration", 0)) == 14.25))
    checks.append(("js-cycle minDuration", close(results["js-cycle"].get("minDuration", 0)) == 14.25))
    checks.append(("js-cycle contentMode", results["js-cycle"].get("contentMode") == "canvas"))
    checks.append(("css-loop maxDuration", close(results["css-loop"].get("maxDuration", 0)) == 8.25))
    checks.append(("css-loop contentMode", results["css-loop"].get("contentMode") == "dom"))
    checks.append(("raf-canvas maxDuration", close(results["raf-canvas"].get("maxDuration", 0)) == 12.0))
    checks.append(("raf-canvas frameRate 30 wired", results["raf-canvas"].get("frameRate") == 30))
    checks.append(("manual-4s maxDuration", close(results["manual-4s"].get("maxDuration", 0)) == 4.0))
    checks.append(("manual-4s minDuration", close(results["manual-4s"].get("minDuration", 0)) == 4.0))
    checks.append(("no page errors", not errors))

    print("\n--- results ---")
    for name, payload in results.items():
        compact = {k: payload.get(k) for k in ("maxDuration", "minDuration", "renderEnd", "contentMode", "frameRate")}
        print(f"{name}:", compact)
    print("page errors:", errors or "none")
    for name, passed in checks:
        print(("PASS" if passed else "FAIL"), name)

    ok = all(passed for _, passed in checks)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
