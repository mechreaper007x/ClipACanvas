"""Voice gender catalog, male voice routing, and automatic code transitions."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-voices-tr-")
ZONOS_RUNTIME = Path(os.environ["APPDATA"]) / "ClipACanvas" / "runtimes" / "zonos"
if (ZONOS_RUNTIME / "assets" / "model.safetensors").exists():
    os.environ["CLIPACANVAS_ZONOS_ASSETS"] = str(ZONOS_RUNTIME / "assets")
    os.environ["CLIPACANVAS_ZONOS_PYTHON"] = str(
        Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Python" / "Python311" / "python.exe")

import serve
from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server

CUSTOM = (
    "function renderTransition(ctx) {"
    " var p = ctx.progress;"
    " return {"
    " outgoing: { opacity: 1 - p, filter: 'blur(' + (p * 10).toFixed(2) + 'px)' },"
    " incoming: { opacity: p, transform: 'scale(' + (1.06 - p * 0.06).toFixed(3) + ')' }"
    " };"
    " }"
)

registry = serve.tts_provider_registry()
providers = {provider["id"]: provider for provider in registry["providers"]}
gemini = providers["gemini"]
mistral = providers["mistral"]
kokoro = providers["kokoro"]
styletts2 = providers["styletts2"]
zonos = providers["zonos"]
print("gemini voices:", len(gemini["voices"]), "| mistral:", len(mistral["voices"]), "| kokoro:", len(kokoro["voices"]), "| styletts2:", len(styletts2["voices"]), "| zonos:", len(zonos["voices"]))
assert len(gemini["voices"]) == 30
assert next(voice for voice in gemini["voices"] if voice["id"] == "Charon")["gender"] == "male"
assert next(voice for voice in gemini["voices"] if voice["id"] == "Puck")["gender"] == "male"
assert next(voice for voice in gemini["voices"] if voice["id"] == "Kore")["gender"] == "female"
assert len([voice for voice in gemini["voices"] if voice["gender"] == "male"]) >= 12
assert next(voice for voice in mistral["voices"] if voice["id"] == "en_paul_neutral")["gender"] == "male"
assert next(voice for voice in mistral["voices"] if voice["id"] == "gb_jane_neutral")["gender"] == "female"
assert next(voice for voice in kokoro["voices"] if voice["id"] == "am_michael")["gender"] == "male"
assert len([voice for voice in kokoro["voices"] if voice["gender"] == "male"]) >= 8, kokoro["voices"]
sts_ids = [voice["id"] for voice in styletts2["voices"]]
assert len(sts_ids) >= 8, styletts2["voices"]
assert "default" in sts_ids and "libritts-4077" in sts_ids, sts_ids
assert len([voice for voice in styletts2["voices"] if voice["gender"] == "male"]) >= 4, "StyleTTS2 male voices missing"
assert len([voice for voice in styletts2["voices"] if voice["gender"] == "female"]) >= 4, "StyleTTS2 female voices missing"
assert next(voice for voice in styletts2["voices"] if voice["id"] == "libritts-4077")["gender"] == "male"
assert len(zonos["voices"]) == 27, zonos["voices"]
assert len([voice for voice in zonos["voices"] if voice["gender"] == "male"]) >= 12
assert len([voice for voice in zonos["voices"] if voice["gender"] == "female"]) >= 12
assert next(voice for voice in zonos["voices"] if voice["id"] == "Savannah")["gender"] == "female"
assert next(voice for voice in zonos["voices"] if voice["id"] == "Arjun")["language"] == "hi-IN"
assert any(voice["language"] == "te-IN" for voice in zonos["voices"]), "zonos Telugu voices missing"
assert "edge" not in providers, "Edge provider should not be registered"
assert all(voice.get("gender") for provider in registry["providers"] for voice in provider["voices"]), "voice without gender"

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

        # Resolver: gender and names route to a provider that actually has them.
        resolved = page.evaluate("""async () => {
          const provider = (id, voices, kind = 'local') => ({
            id, label: id, kind,
            available: true, models: [{ id: 'm1', label: 'M1' }], formats: ['wav'],
            voices, supports: { speed: true, style: false }
          });
          voiceStudioState.providers = [
            provider('styletts2', [
              { id: 'default', label: 'LJSpeech · female', language: 'en-US', gender: 'female' },
              { id: 'libritts-4077', label: 'LibriTTS 4077 · male', language: 'en-US', gender: 'male' }
            ]),
            provider('kokoro', [
              { id: 'af_heart', label: 'Heart · female', language: 'en-US', gender: 'female' },
              { id: 'am_michael', label: 'Michael · male', language: 'en-US', gender: 'male' },
              { id: 'bm_daniel', label: 'Daniel · male', language: 'en-GB', gender: 'male' }
            ]),
            provider('zonos', [
              { id: 'Savannah', label: 'Savannah · female', language: 'en-US', gender: 'female' },
              { id: 'Arjun', label: 'Arjun · male', language: 'hi-IN', gender: 'male' }
            ]),
            provider('sapi', [{ id: 'Microsoft David Desktop', label: 'David · male', language: 'en-US', gender: 'male' }])
          ];
          voiceStudioState.fetched = true;
          const pick = async args => {
            const value = await resolveSpeechProvider(args);
            return { provider: value.provider.id, voice: value.voice };
          };
          return {
            byGender: await pick({ gender: 'male' }),
            byName: await pick({ voice: 'Michael' }),
            byId: await pick({ voice: 'am_michael' }),
            explicitFemaleEngine: await pick({ provider: 'styletts2', gender: 'male' }),
            sapiName: await pick({ voice: 'Microsoft David Desktop' }),
            female: await pick({ gender: 'female' }),
            defaultVoice: await pick({}),
            stsName: await pick({ voice: 'LibriTTS 4077' }),
            stsId: await pick({ voice: 'libritts-4077' }),
            zonosName: await pick({ voice: 'Savannah' }),
            zonosHindi: await pick({ provider: 'zonos', voice: 'Arjun' }),
            catalog: speechVoiceCatalogForChat()
          };
        }""")
        print("resolver:", resolved)
        assert resolved["byGender"] == {"provider": "styletts2", "voice": "libritts-4077"}, resolved
        assert resolved["byName"] == {"provider": "kokoro", "voice": "am_michael"}, resolved
        assert resolved["byId"] == {"provider": "kokoro", "voice": "am_michael"}, resolved
        assert resolved["explicitFemaleEngine"] == {"provider": "styletts2", "voice": "libritts-4077"}, resolved
        assert resolved["sapiName"] == {"provider": "sapi", "voice": "Microsoft David Desktop"}, resolved
        assert resolved["female"] == {"provider": "styletts2", "voice": "default"}, resolved
        assert resolved["defaultVoice"] == {"provider": "styletts2", "voice": "default"}, resolved
        assert resolved["stsName"] == {"provider": "styletts2", "voice": "libritts-4077"}, resolved
        assert resolved["stsId"] == {"provider": "styletts2", "voice": "libritts-4077"}, resolved
        assert resolved["zonosName"] == {"provider": "zonos", "voice": "Savannah"}, resolved
        assert resolved["zonosHindi"] == {"provider": "zonos", "voice": "Arjun"}, resolved
        assert "am_michael=male" in resolved["catalog"] and "default=female" in resolved["catalog"], resolved["catalog"]
        assert "libritts-4077=male" in resolved["catalog"] and "Savannah=female" in resolved["catalog"], resolved["catalog"]

        # The Voice panel lists the wider catalog with genders visible.
        page.evaluate("async () => { await ensureVoiceStudio(true); }")
        page.click("#tabVoice")
        page.wait_for_timeout(400)
        kokoro_ready = page.evaluate("voiceStudioState.providers.some(provider => provider.id === 'kokoro' && provider.available)")
        if kokoro_ready:
            page.select_option("#voiceProvider", "kokoro")
            page.wait_for_timeout(300)
            voice_options = page.evaluate("Array.from(document.querySelectorAll('#voiceVoice option')).map(option => option.textContent)")
            print("kokoro options:", len(voice_options), voice_options[:6])
            assert len(voice_options) >= 15, voice_options
            for label in ("Michael · male", "Adam · male", "Daniel · male", "Heart · female", "Omega · male"):
                assert any(label in option for option in voice_options), (label, voice_options)
            page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-male-options.png"))
        else:
            print("kokoro runtime unavailable; panel catalog check skipped")
        sts_ready = page.evaluate("voiceStudioState.providers.some(provider => provider.id === 'styletts2' && provider.available)")
        if sts_ready:
            page.select_option("#voiceProvider", "styletts2")
            page.wait_for_timeout(300)
            sts_options = page.evaluate("Array.from(document.querySelectorAll('#voiceVoice option')).map(option => option.textContent)")
            print("styletts2 options:", len(sts_options), sts_options[:8])
            assert len(sts_options) >= 8, sts_options
            assert any("LibriTTS 4077 · male" in option for option in sts_options), sts_options
            assert any("LibriTTS 1221 · female" in option for option in sts_options), sts_options
            assert not page.locator("#voiceSpeedField").is_visible()
            page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-styletts2-options.png"))
        else:
            print("styletts2 runtime unavailable; panel catalog check skipped")
        zonos_ready = page.evaluate("voiceStudioState.providers.some(provider => provider.id === 'zonos' && provider.available)")
        if zonos_ready:
            page.select_option("#voiceProvider", "zonos")
            page.wait_for_timeout(300)
            zonos_options = page.evaluate("Array.from(document.querySelectorAll('#voiceVoice option')).map(option => option.textContent)")
            print("zonos options:", len(zonos_options), zonos_options[:6])
            assert len(zonos_options) == 27, zonos_options
            assert any("Savannah · female · en-US" in option for option in zonos_options), zonos_options
            assert any("Arjun · male · hi-IN" in option for option in zonos_options), zonos_options
            assert not page.locator("#voiceSpeedField").is_visible()
            page.screenshot(path=str(ROOT / "output" / "playwright" / "voice-zonos-options.png"))
        else:
            print("zonos runtime unavailable; panel catalog check skipped")
        page.click("#tabInspector")

        # Automatic transitions: add_scene installs a dissolve, accepts custom
        # code, and transition:false keeps a hard cut.
        page.evaluate("""() => {
          const clip = (name, start, duration) => ({
            id: newClipId(), name, code: '<!doctype html><html><body></body></html>',
            duration, start, track: 0, explicitDuration: true, type: 'code',
            assetId: '', mediaUrl: '', mediaName: '', sourceIn: 0, fit: 'contain',
            parentClipId: '', audioTrack: ''
          });
          timelineState.clips.length = 0;
          timelineState.clips.push(clip('ONE', 0, 2));
          timelineState.layers = 1;
          timelineState.activeId = timelineState.clips[0].id;
          timelineState.selectedIds = [timelineState.clips[0].id];
          timelineState.transitions = [];
          saveTimelineState(true);
          renderLogicBoxes();
          updateStageTimeline();
        }""")
        auto_scene = page.evaluate("""async () => executeChatTool({
            name: 'add_scene',
            args: { name: 'TWO', duration: 2, code: '<!doctype html><html><body>TWO</body></html>' }
        })""")
        print("auto scene:", {key: auto_scene.get(key) for key in ("ok", "transition")})
        assert auto_scene["ok"] and auto_scene["transition"]["ok"], auto_scene
        assert auto_scene["transition"]["type"] == "dissolve" and abs(auto_scene["transition"]["duration"] - 0.4) < 1e-6, auto_scene
        state = page.evaluate("""() => ({
            transitions: timelineState.transitions.map(item => ({ type: item.type, duration: item.duration, from: item.fromClipId, to: item.toClipId })),
            clips: timelineState.clips.length,
            badges: document.querySelectorAll('.logic-transition').length
        })""")
        print("after auto scene:", state)
        assert state["clips"] == 2 and len(state["transitions"]) == 1 and state["badges"] == 1, state

        custom_scene = page.evaluate("""async code => executeChatTool({
            name: 'add_scene',
            args: {
              name: 'THREE', duration: 2,
              code: '<!doctype html><html><body>THREE</body></html>',
              transition: { type: 'custom', duration: 0.6, code }
            }
        })""", CUSTOM)
        print("custom scene:", {key: custom_scene.get(key) for key in ("ok", "transition")})
        assert custom_scene["ok"] and custom_scene["transition"]["ok"], custom_scene
        assert custom_scene["transition"]["type"] == "custom" and abs(custom_scene["transition"]["duration"] - 0.6) < 1e-6, custom_scene

        hard_scene = page.evaluate("""async () => executeChatTool({
            name: 'add_scene',
            args: { name: 'FOUR', duration: 2, code: '<!doctype html><html><body>FOUR</body></html>', transition: false }
        })""")
        print("hard scene:", {key: hard_scene.get(key) for key in ("ok", "transition")})
        assert hard_scene["ok"] and hard_scene["transition"] is None, hard_scene
        assert page.evaluate("timelineState.transitions.length") == 2

        # One all:true call replaces the placeholder and covers every cut,
        # without stacking duplicates on a second pass.
        all_first = page.evaluate("""async code => executeChatTool({
            name: 'add_transition', args: { all: true, type: 'custom', duration: 0.55, code }
        })""", CUSTOM)
        print("all transitions:", {key: all_first.get(key) for key in ("ok", "count", "type", "failed")})
        assert all_first["ok"] and all_first["count"] == 3 and all_first["type"] == "custom", all_first
        assert not all_first.get("failed"), all_first
        assert page.evaluate("timelineState.transitions.length") == 3, "all:true duplicated a cut transition"
        assert page.evaluate("timelineState.transitions.every(item => item.type === 'custom')")
        assert page.locator('.logic-transition').count() == 3
        assert page.locator('.logic-transition', has_text="CODE").count() == 3

        all_second = page.evaluate("""async code => executeChatTool({
            name: 'add_transition', args: { all: true, type: 'custom', duration: 0.7, code }
        })""", CUSTOM)
        print("all transitions again:", {key: all_second.get(key) for key in ("ok", "count")})
        assert all_second["ok"] and all_second["count"] == 3
        assert page.evaluate("timelineState.transitions.length") == 3
        assert abs(page.evaluate("timelineState.transitions[0].duration") - 0.7) < 1e-6

        verified = page.evaluate("() => executeChatTool({ name: 'verify_timeline', args: {} })")
        print("verify:", verified.get("passed"), verified.get("problems"))
        assert verified.get("passed"), verified
        assert not errors, errors
        page.screenshot(path=str(ROOT / "output" / "playwright" / "auto-code-transitions.png"))
        browser.close()
finally:
    stop_server(server)
print("PASS voice genders and auto transitions")
