import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

TEST_DATA_DIR = tempfile.mkdtemp(prefix="clipacanvas_test_")
os.environ["CLIPACANVAS_KEYS_DIR"] = TEST_DATA_DIR

from serve import server_url, start_server, stop_server

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    from patchright.sync_api import sync_playwright

failures = []


def check(name, condition, detail=""):
    print(("PASS  " if condition else "FAIL  ") + name + (f"  :: {detail}" if detail else ""))
    if not condition:
        failures.append(name)


server, thread = start_server()
base = server_url(server)
try:
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        page.on("pageerror", lambda error: failures.append(f"pageerror: {error}"))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(800)
        # Export controls live in the Recipe tab in the Control Room layout.
        page.click("#tabRecipe")
        page.wait_for_timeout(200)

        initial = page.evaluate("""() => ({
            aspect: document.getElementById('aspectRatio').value,
            tier: document.getElementById('resolutionTier').value,
            hidden: document.getElementById('resolution').value,
            label: document.getElementById('resolutionPixels').textContent,
            aspectOptions: [...document.getElementById('aspectRatio').options].map(o => o.value),
            tierOptions: [...document.getElementById('resolutionTier').options].map(o => o.value)
        })""")
        check("initial aspect is 9:16", initial["aspect"] == "9:16", initial["aspect"])
        check("initial tier is 540", initial["tier"] == "540", initial["tier"])
        check("initial pixels 540x960", initial["hidden"] == "540x960", initial["hidden"])
        check("5 aspect ratios offered", len(initial["aspectOptions"]) == 5, initial["aspectOptions"])
        check("8 resolution tiers offered", len(initial["tierOptions"]) == 8, initial["tierOptions"])

        page.select_option("#aspectRatio", "16:9")
        page.select_option("#resolutionTier", "1080")
        state = page.evaluate("""() => ({
            hidden: document.getElementById('resolution').value,
            label: document.getElementById('resolutionPixels').textContent,
            saved: JSON.parse(localStorage.getItem('clipacanvas.settings') || '{}').resolution
        })""")
        check("16:9 + 1080p = 1920x1080", state["hidden"] == "1920x1080", state["hidden"])
        check("label shows 1920 x 1080", "1920 × 1080" in state["label"], state["label"])
        check("choice persisted", state["saved"] == "1920x1080", state["saved"])

        page.select_option("#resolutionTier", "2160")
        check("16:9 + 2160p = 3840x2160",
              page.eval_on_selector("#resolution", "el => el.value") == "3840x2160")

        page.select_option("#aspectRatio", "3:4")
        page.select_option("#resolutionTier", "1080")
        check("3:4 + 1080p = 1080x1440",
              page.eval_on_selector("#resolution", "el => el.value") == "1080x1440")

        page.select_option("#aspectRatio", "1:1")
        page.select_option("#resolutionTier", "720")
        check("1:1 + 720p = 720x720",
              page.eval_on_selector("#resolution", "el => el.value") == "720x720")

        custom = page.evaluate("""() => {
            setResolutionValue('1000x1000');
            return {
                hidden: document.getElementById('resolution').value,
                aspect: document.getElementById('aspectRatio').value,
                tier: document.getElementById('resolutionTier').value,
                label: document.getElementById('resolutionPixels').textContent
            };
        }""")
        check("custom 1000x1000 accepted", custom["hidden"] == "1000x1000", custom["hidden"])
        check("custom keeps nearest controls synced", custom["aspect"] == "1:1" and custom["tier"] == "1080", custom)
        check("custom label flagged", "custom" in custom["label"], custom["label"])

        # The reported bug: user is on 1920x1080 and the model tries 1280x720.
        bug = page.evaluate("""async () => {
            setResolutionValue('1920x1080');
            chatTurnSettings = parseUserSettings('make an animation of a cat');
            const tool = await executeChatTool({
                name: 'set_export_settings',
                args: { resolution: '1280x720', fps: '30', duration: 4, format: 'webm', bitrate: '10M' }
            });
            return {
                applied: tool.applied,
                hidden: document.getElementById('resolution').value,
                fps: document.getElementById('frameRate').value,
                format: document.getElementById('codec').value,
                bitrate: document.getElementById('bitrate').value
            };
        }""")
        check("unrequested resolution change is blocked", bug["hidden"] == "1920x1080", bug)
        check("unrequested fps change is blocked", bug["fps"] == "60", bug["fps"])
        check("unrequested format change is blocked", bug["format"] == "h264", bug["format"])
        check("unrequested bitrate change is blocked", bug["bitrate"] == "5M", bug["bitrate"])
        check("blocked call reports unchanged", "unchanged" in bug["applied"], bug["applied"])

        full_request = page.evaluate("""() => {
            const parsed = parseUserSettings('make it 1280x720, 60fps, 6 seconds, mp4 at 10M bitrate');
            return parsed;
        }""")
        check("full settings request parsed",
              full_request.get("resolution") == "1280x720"
              and full_request.get("fps") == "60"
              and full_request.get("duration") == 6
              and full_request.get("format") == "h264"
              and full_request.get("bitrate") == "10M", full_request)

        landscape = page.evaluate("""async () => {
            setResolutionValue('1920x1080');
            chatTurnSettings = parseUserSettings('make it landscape');
            const requested = chatTurnSettings.resolution;
            const tool = await executeChatTool({
                name: 'set_export_settings',
                args: { resolution: '1280x720' }
            });
            return { requested, hidden: document.getElementById('resolution').value, applied: tool.applied };
        }""")
        check("landscape request keeps 1920x1080", landscape["hidden"] == "1920x1080", landscape)

        flip = page.evaluate("""() => {
            setResolutionValue('1080x1920');
            return parseUserSettings('make it landscape').resolution;
        }""")
        check("portrait 1080p flips to 1920x1080", flip == "1920x1080", flip)

        tier_request = page.evaluate("""() => {
            setResolutionValue('1920x1080');
            return {
                tier720: parseUserSettings('use 720p').resolution,
                fourk: parseUserSettings('make it 4K portrait').resolution,
                combo: parseUserSettings('portrait at 1080p').resolution,
                dims: parseUserSettings('render at 1000x1000').resolution
            };
        }""")
        check("720p request keeps aspect", tier_request["tier720"] == "1280x720", tier_request["tier720"])
        check("4K portrait request = 2160x3840", tier_request["fourk"] == "2160x3840", tier_request["fourk"])
        check("portrait 1080p request = 1080x1920", tier_request["combo"] == "1080x1920", tier_request["combo"])
        check("custom pixel request preserved", tier_request["dims"] == "1000x1000", tier_request["dims"])

        timing = page.evaluate("""async () => {
            setResolutionValue('1280x720');
            chatTurnSettings = parseUserSettings('make it 8 seconds at 30fps');
            const tool = await executeChatTool({
                name: 'set_export_settings',
                args: { fps: '60', duration: 12 }
            });
            return {
                fps: document.getElementById('frameRate').value,
                clip: document.getElementById('clipLength').value,
                applied: tool.applied
            };
        }""")
        check("asked fps/duration win over model values", timing["fps"] == "30" and timing["clip"] == "8", timing)

        interview = page.evaluate("""() => {
            setResolutionValue('960x540');
            const parsed = parseUserSettings('1080');
            const messages = buildChatApiMessages('Choose according to the size of animation');
            const nudge = messages.find(m => m.role === 'system' && m.content.includes('delegated this choice'));
            const session = activeSession();
            const backup = session.messages;
            session.messages = [...backup,
                { role: 'assistant', content: 'What resolution tier would you like?' },
                { role: 'user', content: '1080' }];
            const answered = buildChatApiMessages('1080');
            session.messages = backup;
            return {
                bareTier: parsed.resolution,
                delegation: Boolean(nudge),
                answeredNudge: answered.some(m => m.role === 'system' && m.content.includes('answered your previous question')),
                fixedScript: CHAT_SYSTEM_PROMPT.includes('Start with the aspect ratio'),
                threeFlows: ['Guided:', 'One-shot:', 'Brainstorm:'].every(token => CHAT_SYSTEM_PROMPT.includes(token))
            };
        }""")
        check("bare '1080' answer sets 1080p", interview["bareTier"] == "1920x1080", interview["bareTier"])
        check("delegation ends the interview", interview["delegation"], interview)
        check("answered question forces the next step", interview["answeredNudge"], interview)
        check("prompt covers guided, one-shot and brainstorm flows",
              not interview["fixedScript"] and interview["threeFlows"], interview)

        orchestration = page.evaluate("""async () => {
            setResolutionValue('1920x1080');
            document.getElementById('frameRate').value = '60';
            document.getElementById('codec').value = 'h264';
            document.getElementById('bitrate').value = '5M';
            document.getElementById('clipLength').value = 'auto';
            chatTurnSettings = parseUserSettings('make an animation of a cat');
            const originalFetch = window.fetch;
            let calls = 0;
            window.fetch = async (url, options) => {
                const body = JSON.parse((options && options.body) || '{}');
                calls += 1;
                const hasToolResult = (body.messages || []).some(m => m && m.role === 'tool');
                const payload = hasToolResult
                    ? { ok: true, provider: 'gemini', model: 'models/test', text: 'Done.', toolCalls: [] }
                    : { ok: true, provider: 'gemini', model: 'models/test', text: '', toolCalls: [
                        { id: 'set1', name: 'set_export_settings', args: {
                            resolution: '1280x720', fps: '30', duration: 4, format: 'webm', bitrate: '10M'
                        } },
                        { id: 'insert1', name: 'insert_animation_code', args: {
                            code: '<!DOCTYPE html><html><body><h1>TEST</h1></body></html>'
                        } }
                    ] };
                return { ok: true, status: 200, json: async () => payload };
            };
            await runElephantTurn({
                userText: 'make an animation of a cat',
                provider: 'gemini',
                apiKey: 'test-key',
                resolved: { provider: 'gemini', tier: 'pro', model: { name: 'models/test' } },
                editorCodeBefore: document.getElementById('codeInput').value
            });
            const first = {
                hidden: document.getElementById('resolution').value,
                fps: document.getElementById('frameRate').value,
                codec: document.getElementById('codec').value,
                bitrate: document.getElementById('bitrate').value,
                editor: document.getElementById('codeInput').value
            };
            setResolutionValue('1920x1080');
            chatTurnSettings = parseUserSettings('make it 720p at 30fps, 8 seconds, webm, 2M bitrate');
            calls = 0;
            window.fetch = async (url, options) => {
                const body = JSON.parse((options && options.body) || '{}');
                calls += 1;
                const hasToolResult = (body.messages || []).some(m => m && m.role === 'tool');
                const payload = hasToolResult
                    ? { ok: true, provider: 'gemini', model: 'models/test', text: 'Done.', toolCalls: [] }
                    : { ok: true, provider: 'gemini', model: 'models/test', text: '', toolCalls: [
                        { id: 'set2', name: 'set_export_settings', args: {
                            resolution: '1920x1080', fps: '60', duration: 4, format: 'mp4', bitrate: '10M'
                        } }
                    ] };
                return { ok: true, status: 200, json: async () => payload };
            };
            await runElephantTurn({
                userText: 'make it 720p at 30fps, 8 seconds, webm, 2M bitrate',
                provider: 'gemini',
                apiKey: 'test-key',
                resolved: { provider: 'gemini', tier: 'pro', model: { name: 'models/test' } },
                editorCodeBefore: document.getElementById('codeInput').value
            });
            window.fetch = originalFetch;
            chatTurnSettings = {};
            return {
                first,
                second: {
                    hidden: document.getElementById('resolution').value,
                    fps: document.getElementById('frameRate').value,
                    clip: document.getElementById('clipLength').value,
                    codec: document.getElementById('codec').value,
                    bitrate: document.getElementById('bitrate').value
                },
                notes: document.querySelectorAll('#chatMessages .chat-note').length
            };
        }""")
        check("chat turn keeps 1920x1080 when user asked no settings",
              orchestration["first"]["hidden"] == "1920x1080"
              and orchestration["first"]["fps"] == "60"
              and orchestration["first"]["codec"] == "h264"
              and orchestration["first"]["bitrate"] == "5M", orchestration["first"])
        check("chat turn still inserts code", "TEST" in orchestration["first"]["editor"], orchestration["first"]["editor"][:80])
        check("explicit 720p/30fps/webm/2M request applies exactly",
              orchestration["second"]["hidden"] == "1280x720"
              and orchestration["second"]["fps"] == "30"
              and orchestration["second"]["clip"] == "8"
              and orchestration["second"]["codec"] == "vp9"
              and orchestration["second"]["bitrate"] == "2M", orchestration["second"])
        check("tool replies carry no TOOLS note", orchestration["notes"] == 0, orchestration["notes"])

        flow = page.evaluate("""async () => {
            startNewChat();
            chatState.keys.gemini = 'test-key';
            chatState.models.gemini = [{ name: 'models/test', displayName: 'Test Model' }];
            chatState.modelPrefs.gemini = 'auto';
            saveChatState();
            const statusLog = [];
            const actionLog = [];
            let goldfishRequest = null;
            const realStatus = window.setStatus;
            const realThinking = window.setChatThinking;
            window.setStatus = (msg, type) => { statusLog.push(String(msg)); realStatus(msg, type); };
            window.setChatThinking = (el, text) => { actionLog.push(String(text)); return realThinking(el, text); };
            const originalFetch = window.fetch;
            window.fetch = async (url, options) => {
                const body = JSON.parse((options && options.body) || '{}');
                const messages = body.messages || [];
                const systemText = messages
                    .filter(m => m && m.role === 'system')
                    .map(m => String(m.content || ''))
                    .join(' ');
                let payload;
                if (systemText.includes('You title chat conversations')) {
                    payload = { ok: true, provider: 'gemini', model: 'models/test', text: 'Caterpillar Test' };
                } else if (systemText.includes('Goldfish reviewer')) {
                    goldfishRequest = {
                        count: messages.length,
                        roles: messages.map(m => m.role),
                        tools: body.tools === true,
                        leaked: JSON.stringify(messages).includes('Created the caterpillar animation')
                            || JSON.stringify(messages).includes('Caterpillar Test')
                    };
                    payload = { ok: true, provider: 'gemini', model: 'models/test', text: JSON.stringify({
                        verdict: 'pass', summary: 'Looks fine', findings: []
                    }) };
                } else if (systemText.includes('You are Clipppa')) {
                    const hasToolResult = messages.some(m => m && m.role === 'tool');
                    payload = hasToolResult
                        ? { ok: true, provider: 'gemini', model: 'models/test', text: 'Created the caterpillar animation.', toolCalls: [] }
                        : { ok: true, provider: 'gemini', model: 'models/test', text: 'Writing the caterpillar animation…', toolCalls: [
                            { id: 'ins', name: 'insert_animation_code', args: {
                                code: '<!DOCTYPE html><html><body><h1>FLOW</h1></body></html>'
                            } }
                        ] };
                } else {
                    payload = { ok: true, provider: 'gemini', model: 'models/test', text: 'OK' };
                }
                return { ok: true, status: 200, json: async () => payload };
            };
            const input = document.getElementById('chatInput');
            input.value = 'make a caterpillar animation';
            document.getElementById('statusBar').textContent = 'STANDBY';
            statusLog.length = 0;
            await sendChat();
            await new Promise(resolve => setTimeout(resolve, 150));
            window.fetch = originalFetch;
            window.setStatus = realStatus;
            window.setChatThinking = realThinking;
            chatState.keys.gemini = '';
            chatState.models.gemini = [];
            saveChatState();
            return {
                statuses: statusLog,
                actions: actionLog,
                goldfish: goldfishRequest,
                strictPrompt: GOLDFISH_SYSTEM_PROMPT.includes('Pass bar:')
                    && GOLDFISH_SYSTEM_PROMPT.includes('blocker = it cannot run'),
                reviewNotes: document.querySelectorAll('#chatMessages .chat-review-note').length,
                thinking: document.querySelectorAll('#chatMessages .chat-thinking').length,
                assistants: Array.from(document.querySelectorAll('#chatMessages .chat-msg.assistant'))
                    .map(el => el.textContent)
            };
        }""")
        check("goldfish request is a fresh stateless call",
              flow["goldfish"] is not None
              and flow["goldfish"]["count"] == 2
              and flow["goldfish"]["roles"] == ["system", "user"]
              and flow["goldfish"]["tools"] is False
              and not flow["goldfish"]["leaked"], flow["goldfish"])
        check("goldfish prompt is strict", flow["strictPrompt"], flow["strictPrompt"])
        check("live action line comes from the LLM",
              any("Writing the caterpillar animation" in action for action in flow["actions"]), flow["actions"])
        check("no chat/goldfish status in the status bar",
              not any(("Goldfish" in status or "AI reply ready" in status or "Asking" in status
                       or "routed to" in status) for status in flow["statuses"]), flow["statuses"])
        check("passed review is not shown in the chat flow", flow["reviewNotes"] == 0, flow["reviewNotes"])
        check("thinking bubble is removed when the turn ends", flow["thinking"] == 0, flow["thinking"])
        check("final assistant reply is shown",
              any("Created the caterpillar animation." in text for text in flow["assistants"]), flow["assistants"])

        render_flow = page.evaluate("""async () => {
            startNewChat();
            chatState.keys.gemini = 'test-key';
            chatState.models.gemini = [{ name: 'models/test', displayName: 'Test Model' }];
            saveChatState();
            const BUGGY = '<!DOCTYPE html><html><body><h1>BUGGY</h1></body></html>';
            const FIXED = '<!DOCTYPE html><html><body><h1>FIXED</h1></body></html>';
            let renderCount = 0;
            let renderedCode = '';
            const realRender = window.renderWithPlaywrightBackend;
            const realEnsure = window.ensureBackendReady;
            window.ensureBackendReady = async () => {};
            window.renderWithPlaywrightBackend = async (code, settings) => {
                renderCount += 1;
                renderedCode = code;
                window.lastRenderMeta = { filename: 'test.mp4', duration: '1.0s', frameCount: '60', codec: 'h264', contentHash: 'x' };
                appendRenderNote({
                    status: 'ok', width: 540, height: 960, fps: settings.frameRate,
                    duration: 1, format: 'mp4', bitrate: '5M', elapsedMs: 5, filename: 'test.mp4'
                });
            };
            const statusLog = [];
            const actionLog = [];
            const realStatus = window.setStatus;
            const realThinking = window.setChatThinking;
            window.setStatus = (msg, type) => { statusLog.push(String(msg)); realStatus(msg, type); };
            window.setChatThinking = (el, text) => { actionLog.push(String(text)); return realThinking(el, text); };
            const originalFetch = window.fetch;
            window.fetch = async (url, options) => {
                const body = JSON.parse((options && options.body) || '{}');
                const messages = body.messages || [];
                const systemText = messages.filter(m => m && m.role === 'system')
                    .map(m => String(m.content || '')).join(' ');
                const userTexts = messages.filter(m => m && m.role === 'user')
                    .map(m => String(m.content || ''));
                const hasTool = messages.some(m => m && m.role === 'tool');
                let payload;
                if (systemText.includes('You title chat conversations')) {
                    payload = { ok: true, provider: 'gemini', model: 'models/test', text: 'Batman Test' };
                } else if (systemText.includes('Goldfish reviewer')) {
                    payload = { ok: true, provider: 'gemini', model: 'models/test', text: JSON.stringify({
                        verdict: 'issues', summary: 'depth layering is wrong',
                        findings: [{ severity: 'major', title: 'Depth layering', detail: 'wrong order', fix: 'fix order' }]
                    }) };
                } else if (userTexts.some(t => t.includes('goldfish reviewer examined'))) {
                    payload = hasTool
                        ? { ok: true, provider: 'gemini', model: 'models/test', text: 'Fixed.', toolCalls: [] }
                        : { ok: true, provider: 'gemini', model: 'models/test', text: 'Fixing the depth layering…', toolCalls: [
                            { id: 'fix', name: 'insert_animation_code', args: { code: FIXED } },
                            { id: 'fixrender', name: 'render_video', args: {} }
                        ] };
                } else if (systemText.includes('You are Clipppa')) {
                    payload = hasTool
                        ? { ok: true, provider: 'gemini', model: 'models/test', text: 'The Batman animation is ready.', toolCalls: [] }
                        : { ok: true, provider: 'gemini', model: 'models/test', text: 'Writing the Batman animation…', toolCalls: [
                            { id: 'ins', name: 'insert_animation_code', args: { code: BUGGY } },
                            { id: 'ren', name: 'render_video', args: {} }
                        ] };
                } else {
                    payload = { ok: true, provider: 'gemini', model: 'models/test', text: 'OK' };
                }
                return { ok: true, status: 200, json: async () => payload };
            };
            const input = document.getElementById('chatInput');
            input.value = 'render a video where batman is jumping onto buildings';
            await sendChat();
            await new Promise(resolve => setTimeout(resolve, 150));
            window.fetch = originalFetch;
            window.setStatus = realStatus;
            window.setChatThinking = realThinking;
            window.renderWithPlaywrightBackend = realRender;
            window.ensureBackendReady = realEnsure;
            const session = activeSession();
            const assistants = session.messages.filter(m => m.role === 'assistant');
            const traces = Array.from(document.querySelectorAll('#chatMessages .chat-tool-trace'))
                .map(el => el.textContent);
            chatState.keys.gemini = '';
            chatState.models.gemini = [];
            saveChatState();
            return {
                renderCount,
                renderedFixed: renderedCode.includes('FIXED'),
                editorFixed: document.getElementById('codeInput').value.includes('FIXED'),
                assistantCount: assistants.length,
                lastCodeAfter: assistants.length ? String(assistants[assistants.length - 1].codeAfter || '') : '',
                traces,
                renderNotes: document.querySelectorAll('#chatMessages .chat-render-note').length,
                reviewNotes: document.querySelectorAll('#chatMessages .chat-review-note').length,
                thinking: document.querySelectorAll('#chatMessages .chat-thinking').length,
                actions: actionLog,
                statuses: statusLog
            };
        }""")
        check("code-write render is deferred to one final render",
              render_flow["renderCount"] == 1 and render_flow["renderedFixed"], render_flow)
        check("goldfish fix renders the corrected code only",
              render_flow["editorFixed"] and "FIXED" in render_flow["lastCodeAfter"], render_flow)
        check("fix turn adds no second reply or traces",
              render_flow["assistantCount"] == 1
              and sum("insert_animation_code" in t for t in render_flow["traces"]) == 1
              and sum("render_video" in t for t in render_flow["traces"]) == 1,
              render_flow["traces"])
        check("queued render is labeled and rendered once",
              any("queued until code verification" in t for t in render_flow["traces"])
              and render_flow["renderNotes"] == 1, render_flow["traces"])
        check("fix render flow stays silent",
              render_flow["reviewNotes"] == 0
              and render_flow["thinking"] == 0
              and not any("Goldfish" in s for s in render_flow["statuses"]), render_flow["statuses"])

        review = page.evaluate("""async () => {
            const session = activeSession();
            const backup = session.messages;
            session.messages = [...backup, {
                role: 'review',
                content: JSON.stringify({
                    verdict: 'issues', summary: 'broken',
                    findings: [{ severity: 'blocker', title: 'blank', detail: 'draw never starts', fix: 'start loop' }]
                })
            }];
            renderChat();
            const legacyShown = document.querySelectorAll('.chat-review-note').length;
            const goldfishText = document.getElementById('chatMessages').textContent.includes('GOLDFISH REVIEW');
            session.messages = backup;
            renderChat();
            const baseline = session.messages.length;
            const tracesBefore = document.querySelectorAll('#chatMessages .chat-tool-trace').length;
            const originalFetch = window.fetch;
            window.fetch = async () => ({
                ok: true,
                status: 200,
                json: async () => ({
                    ok: true,
                    text: JSON.stringify({
                        verdict: 'issues', summary: 'broken',
                        findings: [{ severity: 'blocker', title: 'blank', detail: 'draw never starts', fix: 'start loop' }]
                    })
                })
            });
            const result = await runGoldfishReview({
                request: 'test', code: '<html><body></body></html>',
                provider: 'gemini', apiKey: 'test', model: 'test-model', allowFallback: false
            });
            const traceDelta = document.querySelectorAll('#chatMessages .chat-tool-trace').length - tracesBefore;
            window.fetch = originalFetch;
            session.messages = backup;
            renderChat();
            return {
                legacyShown,
                goldfishText,
                stored: session.messages.length - baseline,
                verdict: result && result.verdict,
                traceDelta
            };
        }""")
        check("legacy goldfish messages are invisible",
              review["legacyShown"] == 0 and not review["goldfishText"], review)
        check("goldfish review is not stored or traced",
              review["stored"] == 0 and review["traceDelta"] == 0, review)
        check("goldfish still reviews in the background", review["verdict"] == "issues", review["verdict"])

        page.reload(wait_until="load")
        page.wait_for_timeout(800)
        restored = page.evaluate("""() => ({
            hidden: document.getElementById('resolution').value,
            aspect: document.getElementById('aspectRatio').value,
            tier: document.getElementById('resolutionTier').value
        })""")
        check("resolution persists across reload", restored["hidden"] == "1280x720", restored)
        check("controls resync after reload", restored["aspect"] == "16:9" and restored["tier"] == "720", restored)

        browser.close()
finally:
    stop_server(server)
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)

print()
if failures:
    print("FAILURES:", failures)
    sys.exit(1)
print("All aspect/resolution checks passed.")
