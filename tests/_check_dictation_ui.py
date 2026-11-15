"""Dictation UI: mic state machine, English-only badge, insertion, cancel, no console errors."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-dictation-ui-")

from playwright.sync_api import sync_playwright  # noqa: E402
from serve import server_url, start_server, stop_server  # noqa: E402

STUB = r"""
(() => {
  const calls = [];
  window.__sttCalls = calls;
  const realFetch = window.fetch.bind(window);
  let recording = false;
  let startedAt = 0;
  const reply = (payload, status = 200) => new Response(JSON.stringify(payload), {
    status, headers: { 'Content-Type': 'application/json' }
  });
  window.fetch = async (url, options = {}) => {
    const target = typeof url === 'string' ? url : (url && url.url) || '';
    if (!target.includes('/api/stt/')) return realFetch(url, options);
    const method = (options.method || 'GET').toUpperCase();
    calls.push({ target, method, body: options.body || '' });
    if (target.includes('/api/stt/start')) {
      recording = true;
      startedAt = Date.now();
      return reply({ ok: true, recording: true, maxSeconds: 120, input: 'Test Microphone' });
    }
    if (target.includes('/api/stt/stop')) {
      recording = false;
      return reply({
        ok: true, duration: 2.4, language: 'en', confidence: 0.91,
        model: 'faster-whisper-small.en', device: 'cpu',
        text: 'Make a cinematic title'
      });
    }
    if (target.includes('/api/stt/cancel')) {
      recording = false;
      return reply({ ok: true });
    }
    if (target.includes('/api/stt/status')) {
      const elapsed = recording ? (Date.now() - startedAt) / 1000 : 0;
      return reply({
        ok: true, available: true, phase: recording ? 'recording' : 'idle', recording,
        peak: recording ? 0.18 : 0, elapsed, modelReady: true, device: 'cpu',
        progress: { stage: 'ready', pct: 100, detail: 'Ready' },
        languages: ['en'], maxSeconds: 120
      });
    }
    return reply({ ok: true });
  };
})();
"""

server, _thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1664, "height": 916})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.add_init_script(STUB)
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1000)
        page.evaluate("() => { if (typeof hideProjectHome === 'function') hideProjectHome(); }")
        page.evaluate("() => { switchRightTab('assistant'); }")
        page.wait_for_timeout(300)

        lang_label = page.eval_on_selector("#chatMicLang", "el => el.textContent.trim()")
        lang_tag = page.eval_on_selector("#chatMicLang", "el => el.tagName")
        lang_title = page.eval_on_selector("#chatMicLang", "el => el.title")
        print("language badge:", lang_label, lang_tag, "|", lang_title)
        assert lang_label == "EN", lang_label
        assert lang_tag == "SPAN", lang_tag
        assert "English" in lang_title, lang_title

        page.click("#chatMic")
        page.wait_for_selector("#chatMic.recording", timeout=5000)
        page.wait_for_selector("#chatDictation:not([hidden])", timeout=5000)
        page.wait_for_timeout(900)
        strip = page.eval_on_selector("#chatDictationText", "el => el.textContent")
        mic_style = page.eval_on_selector("#chatMic", "el => el.getAttribute('style') || ''")
        print("recording strip:", strip, "| style:", mic_style)
        assert "Listening" in strip, strip
        assert "speak English" in strip, strip
        assert "--mic-level" in mic_style, mic_style

        page.click("#chatMic")
        page.wait_for_function("() => !document.getElementById('chatMic').classList.contains('recording')", timeout=10000)
        page.wait_for_function("() => document.getElementById('chatInput').value.includes('Make a cinematic title')", timeout=10000)
        value_en = page.eval_on_selector("#chatInput", "el => el.value")
        first_stop = [call for call in page.evaluate("() => window.__sttCalls") if "stop" in call["target"]][-1]
        print("english inserted:", value_en, "| stop body:", first_stop["body"])
        assert '"language":"en"' in first_stop["body"].replace(" ", ""), first_stop

        page.evaluate("() => { document.getElementById('chatInput').value = ''; }")
        page.click("#chatMicLang")
        page.wait_for_timeout(150)
        label_after_click = page.eval_on_selector("#chatMicLang", "el => el.textContent.trim()")
        assert label_after_click == "EN", label_after_click

        page.click("#chatMic")
        page.wait_for_selector("#chatMic.recording", timeout=5000)
        page.click("#chatDictationCancel")
        page.wait_for_timeout(300)
        hidden = page.eval_on_selector("#chatDictation", "el => el.hidden")
        value_after_cancel = page.eval_on_selector("#chatInput", "el => el.value")
        cancelled = any("cancel" in call["target"] for call in page.evaluate("() => window.__sttCalls"))
        mic_recording = page.eval_on_selector("#chatMic", "el => el.classList.contains('recording')")
        print("cancel:", {"hidden": hidden, "value": value_after_cancel, "cancelSent": cancelled, "recording": mic_recording})
        assert hidden is True, hidden
        assert value_after_cancel == "", value_after_cancel
        assert cancelled, "cancel request missing"
        assert mic_recording is False, "mic still recording"

        assert not errors, errors
        browser.close()
    print("PASS dictation ui")
finally:
    stop_server(server)
