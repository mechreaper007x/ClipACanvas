"""Usage ledger: count real provider requests per purpose/model and show them in the picker."""
import io
import json
import os
import sys
import tempfile
import time
import types
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
os.environ["CLIPACANVAS_KEYS_DIR"] = str(Path(tmp.name) / "appdata")
sys.path.insert(0, str(ROOT))

import serve  # noqa: E402

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

MODELS = ["fake-gemini-a", "fake-gemini-b", "fake-gemini-tiny"]
RECORDED = []
CHAT_CALLS = []

_original_record = serve._record_llm_usage


def spy_record(*args, **kwargs):
    provider, model, purpose = args[:3]
    status = args[4] if len(args) > 4 else kwargs.get("status", 200)
    RECORDED.append((provider, model, purpose, status))
    return _original_record(*args, **kwargs)


serve._record_llm_usage = spy_record


def fake_models(self, api_key):
    limits = {"fake-gemini-a": 1000000, "fake-gemini-b": 1000000, "fake-gemini-tiny": 1000}
    return [
        {"name": name, "displayName": name, "inputTokenLimit": limits[name], "outputTokenLimit": 65536, "supportsTools": True}
        for name in MODELS
    ]


def fake_chat(self, api_key, messages, model, tools=False):
    CHAT_CALLS.append(model)
    if model == "fake-gemini-b":
        body = json.dumps({
            "error": {
                "code": 429,
                "message": "You exceeded your current quota.",
                "details": [
                    {
                        "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                        "violations": [
                            {
                                "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                                "quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
                                "quotaDimensions": {"model": "fake-gemini-b"},
                                "quotaValue": "10",
                            },
                            {
                                "quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
                                "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
                                "quotaDimensions": {"model": "fake-gemini-b"},
                                "quotaValue": "20",
                            },
                        ],
                    },
                    {
                        "@type": "type.googleapis.com/google.rpc.RetryInfo",
                        "retryDelay": "54372s",
                    },
                ],
            }
        }).encode("utf-8")
        raise urllib.error.HTTPError("https://generativelanguage.googleapis.com", 429, "Too Many Requests", {}, io.BytesIO(body))
    return {"text": "hello back", "toolCalls": [], "usage": {"prompt": 120, "completion": 30, "total": 150}}


_real_gemini_models = serve.ClipACanvasHandler._gemini_models
_real_mistral_models = serve.ClipACanvasHandler._mistral_models
serve.ClipACanvasHandler._gemini_models = fake_models
serve.ClipACanvasHandler._gemini_chat = fake_chat

# Pure parsers: Gemini 429 quota details, Mistral rate-limit headers and the
# real model metadata mapping (context length + tool capability).
sample_error = json.dumps({"error": {"code": 429, "details": [
    {"@type": "type.googleapis.com/google.rpc.QuotaFailure", "violations": [
        {"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
         "quotaId": "GenerateRequestsPerMinutePerProjectPerModel-FreeTier",
         "quotaValue": "10"},
        {"quotaMetric": "generativelanguage.googleapis.com/generate_content_free_tier_requests",
         "quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier",
         "quotaValue": "20"},
    ]},
    {"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "54372s"},
]}})
details = serve._quota_details_from_error(sample_error)
print("quota details:", details)
assert details["limit"] == 20 and details["window"] == "day", details
assert details["type"] == "requests" and details["retrySeconds"] == 54372, details

message = Message()
message["x-ratelimit-limit-req-minute"] = "2"
message["x-ratelimit-remaining-req-minute"] = "1"
message["x-ratelimit-limit-tokens-minute"] = "40000"
message["x-ratelimit-remaining-tokens-minute"] = "39990"
rate = serve._rate_limits_from_headers(message)
print("rate headers:", rate)
assert rate["x-ratelimit-limit-req-minute"] == 2 and rate["x-ratelimit-remaining-req-minute"] == 1, rate
assert rate["x-ratelimit-limit-tokens-minute"] == 40000 and rate["updatedAt"] > 0, rate
serve._MODEL_RATE_STATE.clear()
merged = serve._record_rate_limits("mistral", "fake-medium", rate)
assert merged["x-ratelimit-limit-req-minute"] == 2, merged

fake_mistral_self = types.SimpleNamespace(_llm_http_get=lambda url, headers, timeout=30: {"data": [{
    "id": "ministral-3b-latest",
    "max_context_length": 131072,
    "capabilities": {"function_calling": True},
}]})
mapped = _real_mistral_models(fake_mistral_self, "key")
print("mapped mistral model:", mapped[0])
assert mapped[0]["inputTokenLimit"] == 131072 and mapped[0]["supportsTools"] is True, mapped

fake_gemini_self = types.SimpleNamespace(_llm_http_get=lambda url, headers, timeout=30: {"models": [{
    "name": "models/gemini-test",
    "displayName": "Test",
    "inputTokenLimit": 1048576,
    "outputTokenLimit": 65536,
    "supportedGenerationMethods": ["generateContent"],
}]})
mapped_gemini = _real_gemini_models(fake_gemini_self, "key")
assert mapped_gemini[0]["inputTokenLimit"] == 1048576 and mapped_gemini[0]["outputTokenLimit"] == 65536, mapped_gemini
assert mapped_gemini[0]["supportsTools"] is True, mapped_gemini

# The AI Studio free-tier table drives Gemini RPM/TPM/RPD, and a model with
# 0 RPD (pro tier on this key) must never be selected.
assert serve._free_tier_limits("gemini", "models/gemini-3.6-flash") == {"rpm": 5, "tpm": 250000, "rpd": 20}
assert serve._free_tier_limits("gemini", "models/gemini-3.5-flash-lite")["rpm"] == 15
assert serve._free_tier_limits("gemini", "models/gemini-2.5-pro")["rpd"] == 0
assert serve._headroom_blocked("gemini", "models/gemini-2.5-pro", {}) is True

serve._MODEL_MINUTE_EVENTS[("gemini", "gemini-3.6-flash")] = [(time.time(), 10)] * 5
flash_info = serve._model_headroom("gemini", "models/gemini-3.6-flash", {"ok": 2})
print("flash headroom:", flash_info)
assert flash_info["remaining"]["rpm"] == 0 and flash_info["remaining"]["rpd"] == 18, flash_info
assert flash_info["remaining"]["tpm"] == 249950, flash_info

class CapacitySelf:
    def _catalog_models(self, provider, api_key):
        return [
            {"name": "models/gemini-3.6-flash", "supportsTools": True},
            {"name": "models/gemini-3.5-flash-lite", "supportsTools": True},
            {"name": "models/gemini-2.5-pro", "supportsTools": True},
        ]

sibling = serve.ClipACanvasHandler._capacity_sibling(
    CapacitySelf(), "gemini", "key", "models/gemini-3.6-flash", [], True
)
print("capacity sibling:", sibling)
assert sibling == "models/gemini-3.5-flash-lite", sibling

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


def usage():
    with urllib.request.urlopen(base + "/api/llm/usage", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))["usage"]["gemini"]


try:
    status, payload = chat({
        "provider": "gemini",
        "apiKey": "test-key",
        "model": "fake-gemini-a",
        "purpose": "chat",
        "fallbackOnQuota": False,
        "tools": False,
        "messages": [{"role": "user", "content": "hi"}],
    })
    assert status == 200 and payload["ok"], payload

    status, payload = chat({
        "provider": "gemini",
        "apiKey": "test-key",
        "model": "fake-gemini-b",
        "purpose": "review",
        "fallbackOnQuota": False,
        "tools": False,
        "messages": [{"role": "user", "content": "review"}],
    })
    assert status == 429, (status, payload)

    ledger = usage()
    print("ledger after backend calls:", json.dumps(ledger))
    assert ledger["calls"] == 2, ledger
    assert ledger["purposes"] == {"chat": 1, "review": 1}, ledger
    assert ledger["promptTokens"] == 120, ledger
    assert ledger["completionTokens"] == 30, ledger
    model_a = ledger["models"]["fake-gemini-a"]
    assert model_a["calls"] == 1 and model_a["ok"] == 1, model_a
    model_b = ledger["models"]["fake-gemini-b"]
    assert model_b["calls"] == 1 and model_b["ok"] == 0, model_b
    assert model_b["limit"] == 20 and model_b["remaining"] == 20, model_b
    assert model_b["limitWindow"] == "day" and "PerDay" in model_b["limitId"], model_b
    assert model_b["limitType"] == "requests", model_b
    assert model_b.get("cooldownSeconds", 0) > 0, model_b
    assert Path(os.environ["CLIPACANVAS_KEYS_DIR"], "llm-usage.json").exists()

    guard_calls = len(CHAT_CALLS)
    status, payload = chat({
        "provider": "gemini",
        "apiKey": "test-key",
        "model": "fake-gemini-tiny",
        "purpose": "chat",
        "fallbackOnQuota": False,
        "tools": False,
        "messages": [{"role": "user", "content": "x" * 20000}],
    })
    print("context guard:", status, payload.get("error", "")[:100])
    assert status == 400 and "context" in payload["error"], payload
    assert len(CHAT_CALLS) == guard_calls, "the over-limit request must not reach the provider"

    RECORDED.clear()
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1000)
        page.evaluate("""() => {
            chatState.keys.gemini = 'fake-key';
            chatState.models.gemini = [];
            chatState.knownGood.gemini = { flash: 'fake-gemini-a' };
            chatState.modelPrefs.gemini = 'fake-gemini-a';
            document.getElementById('llmProvider').value = 'gemini';
            document.getElementById('llmModel').value = 'fake-gemini-a';
        }""")
        page.evaluate("async () => { await refreshModels('gemini'); await refreshLlmUsage(); }")
        page.wait_for_timeout(300)

        page.evaluate("() => openComposerModelMenu()")
        page.wait_for_timeout(400)
        usage_text = page.locator(".chat-usage").inner_text()
        print("usage block:", usage_text.replace("\n", " | "))
        assert "Gemini" in usage_text and "2 calls" in usage_text, usage_text
        assert "chat 1" in usage_text and "review 1" in usage_text, usage_text
        assert "150 tokens" in usage_text, usage_text
        model_row = page.locator(".chat-model-item", has_text="fake-gemini-a").first
        assert "1 call" in model_row.inner_text(), model_row.inner_text()
        cooled_row = page.locator(".chat-model-item.cooled").first
        assert "quota ~" in cooled_row.inner_text(), cooled_row.inner_text()
        page.evaluate("() => closeComposerModelMenu()")

        page.evaluate("""async () => {
            document.getElementById('chatInput').value = 'say hello';
            await sendChat();
        }""")
        page.wait_for_timeout(1200)
        purposes = [row[2] for row in RECORDED]
        print("recorded purposes:", RECORDED)
        assert "chat" in purposes, RECORDED
        assert "title" in purposes, RECORDED
        assert all(row[3] == 200 for row in RECORDED if row[2] in ("chat", "title")), RECORDED

        ledger = usage()
        print("ledger after UI chat:", json.dumps(ledger))
        assert ledger["purposes"]["chat"] >= 2, ledger
        assert ledger["purposes"]["title"] >= 1, ledger

        page.evaluate("() => openComposerModelMenu()")
        page.wait_for_timeout(300)
        usage_text = page.locator(".chat-usage").inner_text()
        assert "title 1" in usage_text, usage_text

        page.evaluate("""() => {
            chatState.keys.mistral = 'fake-key';
            chatState.models.mistral = [{
                name: 'fake-medium', displayName: 'Fake Medium', inputTokenLimit: 262144,
                supportsTools: true, callsToday: 1,
                limits: { rpm: 2, tpm: 40000, rpd: 20 },
                headroom: { rpm: 2, tpm: 40000, rpd: 18 },
                limitsSource: 'headers'
            }];
            renderComposerMenu();
        }""")
        page.wait_for_timeout(200)
        mistral_row = page.locator(".chat-model-item", has_text="Fake Medium").first
        mistral_text = mistral_row.inner_text()
        print("mistral row:", mistral_text)
        assert "ctx 262.1K" in mistral_text, mistral_text
        assert "0/2 rpm" in mistral_text, mistral_text
        assert "2/20 day" in mistral_text, mistral_text
        assert page.evaluate("() => modelBlocked({limits:{rpd:0}, headroom:{rpd:0, rpm:0, tpm:0}})"), "pro models with 0 RPD must be blocked"
        assert page.evaluate("() => modelBlocked({limits:{rpm:5, tpm:250000, rpd:20}, headroom:{rpm:0, tpm:1000, rpd:10}})"), "models with no RPM headroom must be blocked"
        assert not errors, errors

    mistral_models = ["fake-medium", "fake-small", "fake-notools"]
    mistral_calls = []

    def fake_mistral_models(self, api_key):
        limits = {"fake-medium": 262144, "fake-small": 131072, "fake-notools": 131072}
        tools = {"fake-medium": True, "fake-small": True, "fake-notools": False}
        return [
            {"name": name, "displayName": name, "inputTokenLimit": limits[name], "supportsTools": tools[name]}
            for name in mistral_models
        ]

    def fake_mistral_chat(self, api_key, messages, model, tools=False):
        mistral_calls.append(model)
        if model == "fake-medium":
            headers = Message()
            headers["x-ratelimit-limit-req-minute"] = "2"
            headers["x-ratelimit-remaining-req-minute"] = "0"
            headers["Retry-After"] = "30"
            body = b'{"message":"Rate limit exceeded","type":"rate_limited","code":"1300"}'
            raise urllib.error.HTTPError("https://api.mistral.ai/v1/chat", 429, "Too Many Requests", headers, io.BytesIO(body))
        return {
            "text": f"reply from {model}",
            "toolCalls": [],
            "usage": {"prompt": 10, "completion": 2, "total": 12},
            "rateLimit": {
                "x-ratelimit-limit-req-minute": 2,
                "x-ratelimit-remaining-req-minute": 1,
                "updatedAt": int(time.time()),
            },
        }

    serve.ClipACanvasHandler._mistral_models = fake_mistral_models
    serve.ClipACanvasHandler._mistral_chat = fake_mistral_chat
    serve._MODEL_CATALOG.clear()
    serve._MODEL_COOLDOWNS.clear()
    serve._MODEL_RATE_STATE[("mistral", "fake-medium")] = {
        "x-ratelimit-limit-req-minute": 2,
        "x-ratelimit-remaining-req-minute": 0,
        "updatedAt": int(time.time()),
    }
    status, payload = chat({
        "provider": "mistral",
        "apiKey": "test-key",
        "model": "fake-medium",
        "allowFallback": False,
        "fallbackOnQuota": True,
        "tools": True,
        "messages": [{"role": "user", "content": "hi"}],
    })
    print("per-minute switch:", status, payload.get("model"), mistral_calls)
    assert status == 200 and payload["model"] == "fake-small", payload
    assert mistral_calls == ["fake-small"], mistral_calls
    assert payload["rateLimit"]["x-ratelimit-remaining-req-minute"] == 1, payload

    status, payload = chat({
        "provider": "mistral",
        "apiKey": "test-key",
        "model": "fake-medium",
        "allowFallback": False,
        "fallbackOnQuota": False,
        "tools": True,
        "messages": [{"role": "user", "content": "hi"}],
    })
    print("mistral 429 headers:", status, payload.get("quotaLimit"))
    assert status == 429, payload
    assert payload["quotaLimit"]["limit"] == 2 and payload["quotaLimit"]["window"] == "minute", payload
    assert payload["rateLimit"]["x-ratelimit-remaining-req-minute"] == 0, payload

    request = urllib.request.Request(
        base + "/api/llm/models",
        data=json.dumps({"provider": "mistral", "apiKey": "test-key"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        models = json.loads(response.read().decode("utf-8"))["models"]
    medium = next(model for model in models if model["name"] == "fake-medium")
    small = next(model for model in models if model["name"] == "fake-small")
    print("mistral models:", medium, small)
    assert medium["inputTokenLimit"] == 262144 and medium["supportsTools"] is True, medium
    assert medium["callsToday"] == 1 and medium["cooldownSeconds"] > 0, medium
    assert medium["quotaLimit"]["limit"] == 2 and medium["quotaLimit"]["window"] == "minute", medium
    assert medium["limits"]["rpm"] == 2 and medium["headroom"]["rpm"] == 0, medium
    assert small["callsToday"] == 1 and small["rateLimit"]["x-ratelimit-remaining-req-minute"] == 1, small
    assert small["limits"]["rpm"] == 2 and small["headroom"]["rpm"] == 1, small
    assert small["limitsSource"] == "headers", small

    with urllib.request.urlopen(base + "/api/llm/usage", timeout=30) as response:
        mistral_usage = json.loads(response.read().decode("utf-8"))["usage"]["mistral"]
    print("mistral usage:", json.dumps(mistral_usage))
    assert mistral_usage["models"]["fake-medium"]["limitWindow"] == "minute", mistral_usage
    assert mistral_usage["models"]["fake-medium"]["remaining"] is None, mistral_usage
    assert mistral_usage["models"]["fake-medium"]["limits"]["rpm"] == 2, mistral_usage
    assert mistral_usage["models"]["fake-medium"]["headroom"]["rpm"] == 0, mistral_usage

    print("LLM USAGE CHECK: OK")
finally:
    serve.stop_server(server)
    tmp.cleanup()
