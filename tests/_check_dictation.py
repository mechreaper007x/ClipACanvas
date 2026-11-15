"""Local dictation: worker boot, model reuse, English accuracy, API shape.

Runs an isolated backend (temp keys dir) against the local faster-whisper
small.en runtime and Windows SAPI audio. Fails when the runtime or model is
missing so accuracy regressions are never silently skipped.
"""
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

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

KEYS = tempfile.mkdtemp(prefix="cc-dictation-")
WORK = Path(tempfile.mkdtemp(prefix="cc-dictation-audio-"))
os.environ["CLIPACANVAS_KEYS_DIR"] = KEYS
os.environ["CLIPACANVAS_STT_ASSETS"] = str(
    Path(os.environ.get("APPDATA", "")) / "ClipACanvas" / "runtimes" / "stt" / "assets"
)

from serve import server_url, start_server, stop_server  # noqa: E402

EN_TEXT = "Create a cinematic title with warm golden light and a slow camera push."
MODEL_ID = "faster-whisper-small.en"


def http_json(base, path, payload=None, method="GET", timeout=120):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(body)
        except ValueError:
            return exc.code, {"ok": False, "error": body[:300]}


def http_upload(base, path, wav_bytes, timeout=600):
    request = urllib.request.Request(
        base + path, data=wav_bytes, headers={"Content-Type": "audio/wav"}, method="POST"
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


def make_english():
    out = WORK / "dictation-en.wav"
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.SetOutputToWaveFile('%s'); $s.Speak('%s'); $s.Dispose()" % (out, EN_TEXT)
    )
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script], check=True)
    return out


server, _thread = start_server()
base = server_url(server)
try:
    status, payload = http_json(base, "/api/stt/status")
    print("status:", {k: payload.get(k) for k in ("ok", "available", "engine", "model", "modelReady", "maxSeconds", "languages")})
    assert status == 200 and payload.get("ok"), payload
    assert payload.get("available"), payload
    assert payload.get("model") == MODEL_ID, payload
    assert "faster-whisper" in str(payload.get("engine") or "").lower(), payload
    assert payload.get("languages") == ["en"], payload
    assert payload.get("maxSeconds") == 120, payload

    status, payload = http_json(base, "/api/stt/stop", {}, method="POST")
    print("stop while idle:", status, payload)
    assert status == 409, (status, payload)

    status, payload = http_json(base, "/api/stt/warm", {}, method="POST")
    print("warm:", status, payload)
    assert status == 200 and payload.get("ok"), payload

    status, payload = http_json(base, "/api/stt/prepare", {}, method="POST")
    print("prepare:", status, payload)
    assert status == 200 and payload.get("ok"), payload

    deadline = time.time() + 300
    while time.time() < deadline:
        status, payload = http_json(base, "/api/stt/status")
        progress = payload.get("progress") or {}
        print("  wait:", payload.get("modelState"), progress.get("stage"), progress.get("pct"), payload.get("modelReady"))
        if payload.get("modelReady"):
            break
        time.sleep(2)
    assert payload.get("modelReady"), payload

    en_wav = make_english()
    status, result = http_upload(base, "/api/stt/transcribe?lang=en", en_wav.read_bytes())
    text_en = (result.get("text") or "").strip()
    wer = word_error_rate(EN_TEXT, text_en)
    print("english:", status, text_en, "| wer %.3f" % wer, "| confidence", result.get("confidence"))
    assert status == 200 and result.get("ok"), result
    assert result.get("language") == "en", result
    assert wer <= 0.10, text_en
    assert text_en[:1].isupper(), text_en
    assert text_en.endswith("."), text_en
    assert "cinematic" in text_en.lower() and "title" in text_en.lower(), text_en

    status, result = http_upload(base, "/api/stt/transcribe?lang=auto", en_wav.read_bytes())
    text_auto = (result.get("text") or "").strip()
    print("auto:", status, text_auto, "| language", result.get("language"))
    assert status == 200 and result.get("ok") and result.get("language") == "en", result
    assert word_error_rate(EN_TEXT, text_auto) <= 0.10, text_auto

    status, result = http_upload(base, "/api/stt/transcribe?lang=hi", en_wav.read_bytes())
    text_legacy = (result.get("text") or "").strip()
    print("legacy hi param:", status, "| language", result.get("language"), "|", text_legacy)
    assert status == 200 and result.get("ok") and result.get("language") == "en", result
    assert not any("\u0900" <= ch <= "\u097f" for ch in text_legacy), text_legacy

    bad = urllib.request.Request(base + "/api/stt/transcribe", data=b"RIFF", method="POST")
    try:
        urllib.request.urlopen(bad, timeout=30)
        raise AssertionError("tiny payload should be rejected")
    except urllib.error.HTTPError as exc:
        print("bad payload:", exc.code)
        assert exc.code == 400

    status, payload = http_json(base, "/api/stt/start", {}, method="POST")
    print("mic start:", status, {k: payload.get(k) for k in ("ok", "recording", "maxSeconds")})
    if status == 200 and payload.get("ok"):
        assert payload.get("recording") is True, payload
        time.sleep(1.2)
        status, payload = http_json(base, "/api/stt/status")
        print("mic status:", payload.get("phase"), payload.get("elapsed"), payload.get("peak"))
        assert payload.get("phase") == "recording", payload
        status, payload = http_json(base, "/api/stt/stop", {"language": "en"}, method="POST", timeout=180)
        print("mic stop:", status, {k: payload.get(k) for k in ("ok", "text", "silent", "duration")})
        assert status in (200, 400), (status, payload)
        if status == 200 and payload.get("text"):
            assert payload.get("language") == "en", payload
    else:
        print("mic unavailable on this machine; recording smoke skipped")

    status, payload = http_json(base, "/api/stt/cancel", {}, method="POST")
    print("cancel:", status, payload)
    assert status == 200 and payload.get("ok"), payload

    status, payload = http_json(base, "/api/stt/status")
    assert payload.get("phase") == "idle", payload
    print("PASS dictation api")
finally:
    stop_server(server)
