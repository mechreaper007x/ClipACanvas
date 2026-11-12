"""Provider retries: transient 5xx is retried with backoff before failing."""
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

with tempfile.TemporaryDirectory() as tmp_name:
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(Path(tmp_name) / "appdata")
    import serve


def post(base, path, payload):
    request = urllib.request.Request(
        base + path,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def chat(base, allow_fallback=False):
    return post(base, "/api/llm/chat", {
        "provider": "gemini",
        "apiKey": "fake-key",
        "model": "mock-model",
        "allowFallback": allow_fallback,
        "tools": False,
        "messages": [{"role": "user", "content": "Say OK"}],
    })


server, thread = serve.start_server()
base = serve.server_url(server)
original = serve.ClipACanvasHandler._gemini_chat
try:
    calls = {"n": 0}

    def flaky(self, api_key, messages, model, use_tools):
        calls["n"] += 1
        if calls["n"] < 3:
            raise urllib.error.HTTPError("https://example.invalid", 503, "Service Unavailable", {}, None)
        return {"text": "OK", "toolCalls": []}

    serve.ClipACanvasHandler._gemini_chat = flaky
    started = time.time()
    status, payload = chat(base)
    elapsed = time.time() - started
    print("transient:", status, payload, f"calls={calls['n']}", f"{elapsed:.1f}s")
    assert status == 200 and payload.get("ok") and payload.get("text") == "OK", payload
    assert calls["n"] == 3, calls
    assert 4.0 <= elapsed < 12.0, elapsed

    def always_locked(self, api_key, messages, model, use_tools):
        raise urllib.error.HTTPError("https://example.invalid", 423, "Locked", {}, None)

    serve.ClipACanvasHandler._gemini_chat = always_locked
    status, payload = chat(base)
    print("locked:", status, payload)
    assert status == 502 and "locked this request (423)" in payload.get("error", ""), payload
finally:
    serve.ClipACanvasHandler._gemini_chat = original
    serve.stop_server(server)

print("PASS provider retries")
