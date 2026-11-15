"""Manual model pick: a 429 switches to a sibling model of the same provider only."""
import io
import json
import os
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["CLIPACANVAS_KEYS_DIR"] = str(Path(tmp.name) / "appdata")
sys.path.insert(0, str(ROOT))

import serve  # noqa: E402

CALLS = []
MODELS = ["fake-medium", "fake-large", "fake-small"]


def fake_models(self, api_key):
    return [{"name": name, "displayName": name} for name in MODELS]


def fake_chat(self, api_key, messages, model, tools=False):
    CALLS.append(model)
    if model == "fake-medium":
        body = b'{"message":"You exceeded your current quota."}'
        raise urllib.error.HTTPError("https://api.mistral.ai/v1/chat", 429, "Too Many Requests", {}, io.BytesIO(body))
    if model == "fake-large":
        body = b'{"message":"Model not available on this plan."}'
        raise urllib.error.HTTPError("https://api.mistral.ai/v1/chat", 403, "Forbidden", {}, io.BytesIO(body))
    return {"text": f"reply from {model}", "toolCalls": []}


serve.ClipACanvasHandler._mistral_models = fake_models
serve.ClipACanvasHandler._mistral_chat = fake_chat

assert serve._retry_delay_seconds("", {"Retry-After": "120"}) == 120
assert serve._retry_delay_seconds('{"retry_after": 45}') == 45
assert serve._retry_delay_seconds('"retryDelay": "30s"') == 30

server, _thread = serve.start_server()
base = serve.server_url(server)


def chat(payload):
    request = urllib.request.Request(
        base + "/api/llm/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


try:
    status, payload = chat({
        "provider": "mistral",
        "apiKey": "test-key",
        "model": "fake-medium",
        "allowFallback": False,
        "fallbackOnQuota": True,
        "tools": False,
        "messages": [{"role": "user", "content": "hi"}],
    })
    print("manual quota fallback:", status, payload.get("model"), payload.get("fallbackFrom"), CALLS)
    assert status == 200 and payload["ok"], payload
    assert payload["model"] == "fake-small", payload
    assert payload["fallbackFrom"] == "fake-medium", payload
    assert CALLS == ["fake-medium", "fake-large", "fake-small"], CALLS
    assert serve._model_cooldown_remaining("mistral", "fake-medium") > 0
    quota_file = Path(os.environ["CLIPACANVAS_KEYS_DIR"]) / "llm-quota.json"
    assert quota_file.exists(), quota_file
    assert "fake-medium" in quota_file.read_text(encoding="utf-8")

    status, payload = chat({
        "provider": "mistral",
        "apiKey": "test-key",
        "model": "fake-medium",
        "allowFallback": False,
        "fallbackOnQuota": False,
        "tools": False,
        "messages": [{"role": "user", "content": "hi"}],
    })
    print("manual without quota fallback:", status, payload.get("error", "")[:80])
    assert status == 429, (status, payload)
    assert CALLS[-1] == "fake-medium", CALLS

    serve._MODEL_COOLDOWNS.clear()
    serve._load_model_cooldowns()
    assert serve._model_cooldown_remaining("mistral", "fake-medium") > 0

    request = urllib.request.Request(
        base + "/api/llm/models",
        data=json.dumps({"provider": "mistral", "apiKey": "test-key"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        models = json.loads(response.read().decode("utf-8"))["models"]
    cooled = {model["name"]: model.get("cooldownSeconds", 0) for model in models}
    print("model list cooldowns:", cooled)
    assert cooled.get("fake-medium", 0) > 0, cooled
    assert cooled.get("fake-small", 0) == 0, cooled
    print("QUOTA FALLBACK CHECK: OK")
finally:
    serve.stop_server(server)
    tmp.cleanup()
