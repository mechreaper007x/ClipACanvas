#!/usr/bin/env python3

import json
import sys
import time
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from serve import server_url, start_server, stop_server


OUTPUT_DIR = Path("output") / "matrix"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


TEST_CASES = [
    {
        "name": "showcase_dom_marketing",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>
body{margin:0;height:100vh;overflow:hidden;background:
radial-gradient(circle at 20% 20%,rgba(34,211,238,.25),transparent 28%),
radial-gradient(circle at 80% 15%,rgba(168,85,247,.18),transparent 30%),
linear-gradient(160deg,#020617 0%,#0f172a 45%,#111827 100%);
font-family:Inter,system-ui,sans-serif;color:#e5f3ff}
.grid{position:absolute;inset:-20%;background-image:linear-gradient(rgba(148,163,184,.08) 1px,transparent 1px),linear-gradient(90deg,rgba(148,163,184,.08) 1px,transparent 1px);background-size:42px 42px;transform:perspective(900px) rotateX(72deg) translateY(18%);transform-origin:top center;animation:gridDrift 6s linear infinite}
.orb{position:absolute;width:320px;height:320px;border-radius:50%;filter:blur(70px);background:rgba(56,189,248,.24);top:12%;left:-8%;animation:orbFloat 3.6s ease-in-out infinite alternate}
.shell{position:relative;z-index:2;height:100%;display:flex;align-items:center;justify-content:center;padding:42px}
.panel{width:min(86vw,430px);padding:26px;border:1px solid rgba(148,163,184,.16);background:rgba(15,23,42,.72);backdrop-filter:blur(18px);border-radius:28px;box-shadow:0 20px 60px rgba(0,0,0,.35);animation:panelRise .9s cubic-bezier(.2,.9,.2,1) forwards}
.kicker,.title,.meta,.cards{opacity:0;transform:translateY(18px);animation:fadeUp .8s ease forwards}
.kicker{font-size:12px;letter-spacing:.26em;text-transform:uppercase;color:#7dd3fc;animation-delay:.15s}
.title{font-size:46px;line-height:.94;font-weight:900;margin:14px 0 12px;animation-delay:.28s}
.meta{font-size:14px;line-height:1.6;color:#a8bbcf;animation-delay:.42s}
.cards{display:grid;gap:12px;margin-top:24px;animation-delay:.55s}
.card{padding:14px 16px;border-radius:18px;background:linear-gradient(135deg,rgba(15,23,42,.9),rgba(30,41,59,.8));border:1px solid rgba(148,163,184,.14);display:flex;justify-content:space-between;align-items:center;animation:cardPulse 1.8s ease-in-out infinite}
.card:nth-child(2){animation-delay:.25s}.card:nth-child(3){animation-delay:.5s}
.dot{width:10px;height:10px;border-radius:50%;background:#c8ff00;box-shadow:0 0 18px rgba(200,255,0,.85)}
@keyframes panelRise{from{opacity:0;transform:translateY(32px) scale(.96)}to{opacity:1;transform:translateY(0) scale(1)}}
@keyframes fadeUp{to{opacity:1;transform:translateY(0)}}
@keyframes gridDrift{from{transform:perspective(900px) rotateX(72deg) translateY(18%) translateX(0)}to{transform:perspective(900px) rotateX(72deg) translateY(18%) translateX(-24px)}}
@keyframes orbFloat{from{transform:translateY(0) translateX(0) scale(1)}to{transform:translateY(20px) translateX(24px) scale(1.12)}}
@keyframes cardPulse{0%,100%{transform:translateX(0)}50%{transform:translateX(4px)}}
</style></head><body><div class="grid"></div><div class="orb"></div><div class="shell"><section class="panel"><div class="kicker">Desktop Renderer</div><h1 class="title">Turn Front-End Motion Into Video</h1><p class="meta">CODE2VIDEO renders HTML, CSS, JavaScript, SVG, and canvas ideas into MP4 from a local desktop workflow.</p><div class="cards"><div class="card"><span>Chromium render path</span><span class="dot"></span></div><div class="card"><span>Editor-ready MP4 export</span><span class="dot"></span></div><div class="card"><span>Consumer-safe timings</span><span class="dot"></span></div></div></section></div></body></html>""",
    },
    {
        "name": "static_html",
        "resolution": "540x960",
        "bitrate": "1M",
        "code": """<!DOCTYPE html><html><body style="margin:0;background:#111;display:grid;place-items:center;height:100vh;color:#c8ff00;font:700 42px monospace;">STATIC FRAME</body></html>""",
    },
    {
        "name": "dom_finite_css",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><head><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#0f172a;overflow:hidden}
.card{width:220px;height:220px;border-radius:28px;background:linear-gradient(135deg,#22d3ee,#2563eb);animation:rise 1.8s ease forwards}
@keyframes rise{0%{transform:translateY(140px) scale(.7);opacity:0}100%{transform:translateY(0) scale(1);opacity:1}}
</style></head><body><div class="card"></div></body></html>""",
    },
    {
        "name": "dom_infinite_css",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><head><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#020617}
.pulse{width:180px;height:180px;border-radius:999px;background:#f43f5e;animation:pulse 1s ease-in-out infinite}
@keyframes pulse{0%,100%{transform:scale(.9);opacity:.6}50%{transform:scale(1.08);opacity:1}}
</style></head><body><div class="pulse"></div></body></html>""",
    },
    {
        "name": "svg_finite_draw",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><head><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:#0a0a0a}
svg{width:300px}
path{fill:none;stroke:#c8ff00;stroke-width:3;stroke-dasharray:420;stroke-dashoffset:420;animation:draw 2s ease forwards}
@keyframes draw{to{stroke-dashoffset:0}}
</style></head><body><svg viewBox="0 0 160 120"><path d="M10 100 C40 10 120 10 150 100" /></svg></body></html>""",
    },
    {
        "name": "svg_looping_motion",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><head><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:linear-gradient(#bae6fd 0%,#15803d 75%)}
.ball{animation:bounce 1s ease-in-out infinite;transform-origin:200px 200px}
@keyframes bounce{0%,100%{transform:translateY(0)}50%{transform:translateY(-90px)}}
</style></head><body><svg viewBox="0 0 400 400" width="300" height="300"><circle cx="200" cy="350" r="90" fill="rgba(0,0,0,.1)"/><g class="ball"><circle cx="200" cy="260" r="30" fill="white" stroke="#111"/><path d="M185 250 L200 240 L215 250 L210 270 L190 270 Z" fill="#111"/></g></svg></body></html>""",
    },
    {
        "name": "svg_neon_signal_stress",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><head><style>
body{margin:0;height:100vh;display:grid;place-items:center;background:radial-gradient(circle at 50% 20%,#1f2937,#020617 78%);overflow:hidden}
svg{width:86vw;max-width:420px;filter:drop-shadow(0 0 18px rgba(253,224,71,.25))}
.beam{animation:beam 2.6s ease-in-out infinite alternate}
.logo{animation:logoFloat 2.2s ease-in-out infinite alternate;transform-origin:center}
.stroke{stroke-dasharray:320;stroke-dashoffset:320;animation:draw 2.2s ease forwards, glow 1.2s ease-in-out infinite alternate 2.2s}
@keyframes draw{to{stroke-dashoffset:0}}
@keyframes glow{from{filter:drop-shadow(0 0 0 rgba(253,224,71,.1))}to{filter:drop-shadow(0 0 20px rgba(253,224,71,.8))}}
@keyframes beam{from{opacity:.35;transform:scale(1)}to{opacity:.72;transform:scale(1.05)}}
@keyframes logoFloat{from{transform:translateY(0)}to{transform:translateY(-8px)}}
</style></head><body><svg viewBox="0 0 300 220" xmlns="http://www.w3.org/2000/svg"><defs><radialGradient id="g" cx="50%" cy="50%"><stop offset="0%" stop-color="#fde047" stop-opacity=".75"/><stop offset="100%" stop-color="#fde047" stop-opacity="0"/></radialGradient></defs><ellipse class="beam" cx="150" cy="110" rx="110" ry="70" fill="url(#g)"/><g class="logo"><path class="stroke" d="M70 150 C90 118 120 105 150 110 C180 105 210 118 230 150 C202 145 182 134 170 122 C164 138 157 148 150 150 C143 148 136 138 130 122 C118 134 98 145 70 150 Z" fill="#000" stroke="#fde047" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></g></svg></body></html>""",
    },
    {
        "name": "waapi_infinite",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#111827"><div id="box" style="width:180px;height:180px;border-radius:28px;background:#22c55e"></div><script>box.animate([{transform:'rotate(0deg) scale(.85)'},{transform:'rotate(180deg) scale(1.1)'},{transform:'rotate(360deg) scale(.85)'}],{duration:1200,iterations:Infinity,easing:'ease-in-out'});</script></body></html>""",
    },
    {
        "name": "timer_driven_dom",
        "resolution": "540x960",
        "bitrate": "1M",
        "code": """<!DOCTYPE html><html><body style="margin:0;height:100vh;display:grid;place-items:center;background:#111;color:#fff;font:700 64px monospace"><div id="n">0</div><script>let i=0;const el=document.getElementById('n');const t=setInterval(()=>{i+=1;el.textContent=i;if(i>=5) clearInterval(t);},300);</script></body></html>""",
    },
    {
        "name": "canvas_raf_loop",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><body style="margin:0;background:#020617;overflow:hidden"><canvas id="c" width="540" height="960"></canvas><script>const ctx=c.getContext('2d');let t=0;function draw(now){t=now/1000;ctx.fillStyle='#020617';ctx.fillRect(0,0,c.width,c.height);ctx.fillStyle='#c8ff00';const y=480+Math.sin(t*2)*220;ctx.beginPath();ctx.arc(270,y,48,0,Math.PI*2);ctx.fill();requestAnimationFrame(draw)}requestAnimationFrame(draw);</script></body></html>""",
    },
    {
        "name": "canvas_particle_stress",
        "resolution": "540x960",
        "bitrate": "2M",
        "code": """<!DOCTYPE html><html><body style="margin:0;background:#020617;overflow:hidden"><canvas id="c" width="540" height="960"></canvas><script>const ctx=c.getContext('2d');const pts=Array.from({length:110},(_,i)=>({x:Math.random()*540,y:Math.random()*960,vx:(Math.random()-.5)*1.4,vy:(Math.random()-.5)*1.4,r:1+Math.random()*2,h:180+Math.random()*80}));function draw(now){ctx.fillStyle='rgba(2,6,23,.28)';ctx.fillRect(0,0,540,960);for(const p of pts){p.x+=p.vx;p.y+=p.vy;if(p.x<0||p.x>540)p.vx*=-1;if(p.y<0||p.y>960)p.vy*=-1;}for(let i=0;i<pts.length;i++){const a=pts[i];for(let j=i+1;j<pts.length;j++){const b=pts[j];const dx=a.x-b.x,dy=a.y-b.y,d=Math.hypot(dx,dy);if(d<90){ctx.strokeStyle=`hsla(${(a.h+b.h)/2},100%,70%,${1-d/90})`;ctx.lineWidth=.8;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();}}}for(const p of pts){ctx.fillStyle=`hsl(${p.h} 100% 70%)`;ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,Math.PI*2);ctx.fill();}requestAnimationFrame(draw)}requestAnimationFrame(draw);</script></body></html>""",
    },
]


def set_code(page, code: str) -> None:
    page.evaluate(
        """(value) => {
            const input = document.getElementById('codeInput');
            input.value = value;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }""",
        code,
    )


def configure_case(page, resolution: str, bitrate: str) -> None:
    page.select_option("#resolution", resolution)
    page.select_option("#bitrate", bitrate)
    page.evaluate(
        """() => {
            if (typeof clearResultVideo === 'function') clearResultVideo();
            const panel = document.getElementById('dl-panel');
            if (panel) panel.remove();
                    const btn = document.getElementById('btnDownload');
                    if (btn) {
                      btn.disabled = true;
                      btn.classList.remove('blink');
                    }
                    const convert = document.getElementById('btnConvert');
                    if (convert) convert.disabled = false;
                    const status = document.getElementById('statusBar');
                    if (status) {
                      status.className = '';
                      status.textContent = 'READY';
                    }
                }"""
    )


def wait_for_result(page, timeout_ms: int = 180000) -> dict:
    deadline = time.time() + timeout_ms / 1000.0
    last_status = ""
    while time.time() < deadline:
      status = page.locator("#statusBar").inner_text().strip()
      last_status = status or last_status
      if "ERROR:" in status:
          return {"ok": False, "status": status}
      if "Video ready" in status or page.locator("#dl-panel").count() > 0:
          return {"ok": True, "status": status}
      page.wait_for_timeout(500)
    return {"ok": False, "status": last_status or "Timed out waiting for frontend result"}


def run_matrix() -> list[dict]:
    server, _thread = start_server(host="127.0.0.1", port=0)
    url = f"{server_url(server, public_host='127.0.0.1')}/code2video.html"
    results: list[dict] = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1100})
            page.goto(url, wait_until="networkidle")
            page.locator("#codeInput").wait_for(timeout=15000)

            for case in TEST_CASES:
                started = time.time()
                configure_case(page, case["resolution"], case["bitrate"])
                set_code(page, case["code"])
                page.evaluate("document.getElementById('btnConvert').click()")
                outcome = wait_for_result(page)
                elapsed = round(time.time() - started, 2)
                result = {
                    "name": case["name"],
                    "ok": outcome["ok"],
                    "status": outcome["status"],
                    "elapsedSeconds": elapsed,
                    "resolution": case["resolution"],
                    "bitrate": case["bitrate"],
                }
                if outcome["ok"]:
                    result["modeSummary"] = page.locator("#timingSummary").inner_text().strip()
                    result["downloadEnabled"] = page.locator("#btnDownload").is_enabled()
                else:
                    screenshot_path = OUTPUT_DIR / f"{case['name']}-failure.png"
                    page.screenshot(path=str(screenshot_path), full_page=True)
                    result["screenshot"] = str(screenshot_path)

                results.append(result)
                if outcome["ok"]:
                    page.evaluate(
                        """() => {
                            if (typeof clearResultVideo === 'function') clearResultVideo();
                            const panel = document.getElementById('dl-panel');
                            if (panel) panel.remove();
                        }"""
                    )
                    page.wait_for_timeout(300)

            browser.close()
    finally:
        stop_server(server)

    report_path = OUTPUT_DIR / "frontend-render-report.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


if __name__ == "__main__":
    matrix_results = run_matrix()
    failures = [r for r in matrix_results if not r["ok"]]
    print(json.dumps(matrix_results, indent=2))
    raise SystemExit(1 if failures else 0)
