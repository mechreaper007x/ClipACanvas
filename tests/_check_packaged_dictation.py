"""Packaged exe: local faster-whisper small.en transcribes through the app API."""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright  # noqa: E402

DEBUG_PORT = 9434
EXE = ROOT / "dist" / "ClipACanvas.exe"
EN_TEXT = "Create a cinematic title with warm golden light and a slow camera push."
MODEL_ID = "faster-whisper-small.en"
REAL_APPDATA = Path(os.environ.get("APPDATA", ""))

assert EXE.exists(), "build dist/ClipACanvas.exe first"


def http_json(base, path, payload=None, method="GET", timeout=120):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def http_upload(base, path, blob, timeout=600):
    request = urllib.request.Request(
        base + path, data=blob, headers={"Content-Type": "audio/wav"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def words_of(text):
    return re.sub(r"[^a-z0-9' ]+", " ", text.lower()).split()


def word_error_rate(reference, hypothesis):
    ref = words_of(reference)
    hyp = words_of(hypothesis)
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, 1):
        current = [i]
        for j, hyp_word in enumerate(hyp, 1):
            current.append(min(
                previous[j] + 1,
                current[j - 1] + 1,
                previous[j - 1] + (ref_word != hyp_word),
            ))
        previous = current
    return previous[-1] / max(1, len(ref))


with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_name:
    tmp = Path(tmp_name)
    appdata = tmp / "appdata"
    appdata.mkdir(parents=True)
    wav_path = tmp / "packaged-en.wav"
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SetOutputToWaveFile('%s'); $s.Speak('%s'); $s.Dispose()" % (wav_path, EN_TEXT)
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)

    env = dict(os.environ)
    env["CLIPACANVAS_KEYS_DIR"] = str(appdata)
    env["CLIPACANVAS_NO_BROWSER"] = "1"
    env["CLIPACANVAS_STT_ASSETS"] = str(REAL_APPDATA / "ClipACanvas" / "runtimes" / "stt" / "assets")
    env["APPDATA"] = str(tmp / "appdata-webview")
    env["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = f"--remote-debugging-port={DEBUG_PORT}"
    log_path = tmp / "packaged.log"
    log = open(log_path, "wb")
    proc = subprocess.Popen([str(EXE)], cwd=str(ROOT), env=env, stdout=log, stderr=subprocess.STDOUT)
    try:
        for _ in range(360):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).read()
                break
            except Exception:
                time.sleep(0.5)
        else:
            raise AssertionError("packaged app did not expose the CDP port")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
            page = None
            for _ in range(120):
                for context in browser.contexts:
                    for candidate in context.pages:
                        if "clipacanvas.html" in (candidate.url or ""):
                            page = candidate
                if page:
                    break
                time.sleep(0.5)
            assert page is not None, "packaged page not found"
            errors = []
            page.on("pageerror", lambda exc: errors.append(str(exc)))
            page.wait_for_function("() => typeof timelineState !== 'undefined'", timeout=60000)

            ui = page.evaluate("""() => {
              switchRightTab('assistant');
              const mic = document.getElementById('chatMic');
              const lang = document.getElementById('chatMicLang');
              const strip = document.getElementById('chatDictation');
              return {
                mic: Boolean(mic), lang: Boolean(lang && lang.textContent.trim()),
                langText: lang ? lang.textContent.trim() : '',
                langTag: lang ? lang.tagName : '',
                stripHidden: Boolean(strip && strip.hidden),
                panelVisible: !document.getElementById('aiChat').hidden
              };
            }""")
            print("dictation ui:", ui)
            assert ui["mic"] and ui["lang"] and ui["panelVisible"] and ui["stripHidden"], ui
            assert ui["langText"] == "EN" and ui["langTag"] == "SPAN", ui
            assert not errors, errors

            origin = page.evaluate("() => location.origin")
            print("backend origin:", origin)

            status_code, payload = http_json(origin, "/api/stt/status")
            print("status:", {k: payload.get(k) for k in ("ok", "available", "engine", "model", "modelReady", "languages")})
            assert status_code == 200 and payload.get("ok") and payload.get("available"), payload
            assert payload.get("model") == MODEL_ID, payload
            assert "faster-whisper" in str(payload.get("engine") or "").lower(), payload
            assert payload.get("languages") == ["en"], payload

            status_code, payload = http_json(origin, "/api/stt/prepare", {}, method="POST")
            assert status_code == 200 and payload.get("ok"), payload

            deadline = time.time() + 300
            while time.time() < deadline:
                status_code, payload = http_json(origin, "/api/stt/status")
                state = payload.get("modelState")
                if payload.get("modelReady") or state == "ready":
                    break
                if state == "error":
                    raise AssertionError(payload.get("modelError") or "model load failed")
                time.sleep(2)
            print("model state:", payload.get("modelState"), "ready:", payload.get("modelReady"))
            assert payload.get("modelReady") or payload.get("modelState") == "ready", payload

            status_code, result = http_upload(origin, "/api/stt/transcribe?lang=en", wav_path.read_bytes())
            text = (result.get("text") or "").strip()
            wer = word_error_rate(EN_TEXT, text)
            print("packaged english:", status_code, text, "| wer %.3f" % wer)
            assert status_code == 200 and result.get("ok"), result
            assert result.get("language") == "en", result
            assert wer <= 0.10, text
            assert text[:1].isupper() and text.endswith("."), text
        print("PASS packaged dictation")
    finally:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True)
        log.close()
