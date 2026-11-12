"""Browser smoke test for clipacanvas.html.

Starts the local server, loads the desktop UI in Chromium, captures console and
page errors, exercises core UI wiring, and writes a screenshot for inspection.
"""

from __future__ import annotations

import os
import sys
import time
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Never touch the real %APPDATA% key store during tests; fresh dir per run.
os.environ["CLIPACANVAS_KEYS_DIR"] = os.environ.get("CLIPACANVAS_KEYS_DIR") or tempfile.mkdtemp(prefix="clipacanvas-test-keys-")

from serve import server_url, start_server, stop_server  # noqa: E402


def main() -> int:
    server, thread = start_server()
    base = server_url(server)
    print("base:", base)

    # Seed a legacy chatlog.json so the SQLite migration path is exercised on
    # the first chatlog read (at page load). The assistant message carries a
    # code fence + SETTINGS comment + AUTO-INSERTED note, so the page-load
    # restore path must re-insert it into the editor and preview.
    keys_dir = Path(os.environ["CLIPACANVAS_KEYS_DIR"])
    keys_dir.mkdir(parents=True, exist_ok=True)
    import json as _json
    _restore_code = (
        "```html\n"
        "<!-- SETTINGS resolution=1280x720 fps=60 duration=12 format=mp4 bitrate=5M -->\n"
        "<!DOCTYPE html><html><head><title>RESTORE-MARKER</title></head>\n"
        "<body><canvas id=\"c\"></canvas></body></html>\n"
        "```"
    )
    (keys_dir / "chatlog.json").write_text(_json.dumps({"sessions": [
        {"id": "legacy-1", "title": "Legacy chat", "createdAt": 1, "updatedAt": 2,
         "messages": [
             {"role": "user", "content": "legacy message"},
             {"role": "assistant", "content": _restore_code,
              "modelMeta": {"provider": "gemini", "modelName": "models/gemini-3.6-flash"},
              "note": "AUTO-INSERTED · 1280x720 · 60 FPS · 12s · MP4 · 5M"},
         ]}
    ]}), encoding="utf-8")

    errors: list[str] = []
    console_errors: list[str] = []

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        from patchright.sync_api import sync_playwright  # type: ignore

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1100})
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on(
            "console",
            # The 429 and bad-key health probes intentionally trigger failed
            # requests; Chromium logs the status, which is expected.
            lambda msg: console_errors.append(msg.text)
            if msg.type == "error"
            and "429 (Too Many Requests)" not in msg.text
            and "502 (Bad Gateway)" not in msg.text
            else None,
        )
        page.add_init_script(
            "try { localStorage.setItem('clipacanvas.runHistory', JSON.stringify(["
            "{timestamp: Date.now(), name: 'clipacanvas_20261031_120000.mp4',"
            " duration: '1.2', frameCount: '72', codec: 'h264', format: 'mp4'}]));"
            " } catch (error) {}"
        )

        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_timeout(1200)

        def open_chat_history():
            if not page.locator("#chatHistoryPop").is_visible():
                page.click("#chatHistoryBtn")
                page.wait_for_timeout(150)

        # 1. No raw JS should leak into the rendered document.
        body_text = page.inner_text("body")
        leaked = [
            marker
            for marker in (
                "function runPreview",
                "function startConvert",
                "const DESKTOP_PRESETS",
            )
            if marker in body_text
        ]

        # 2. Core controls must exist.
        controls = {
            "codeInput": page.locator("#codeInput").count(),
            "monacoHost": page.locator("#monacoHost").count(),
            "codec": page.locator("#codec").count(),
            "renderButton": page.locator("button", has_text="Convert").count(),
        }

        # 3. Removed bloat sections must be gone.
        removed = {
            "presetSelect": page.locator("#presetSelect").count(),
            "audioPath": page.locator("#audioPath").count(),
            "recentCodeSelect": page.locator("#recentCodeSelect").count(),
        }

        # 4. Filling the editor still works (Monaco when bundled, plain textarea
        # fallback otherwise) and the two stay in sync.
        page.wait_for_function(
            "window.__monacoEditor != null || document.getElementById('codeInput').style.display !== 'none'",
            timeout=20000,
        )
        monaco_active = page.evaluate("window.__monacoEditor != null")

        # 4a. Restored chat log must re-insert its assistant code into the
        # editor + preview and re-apply its SETTINGS comment (regression: the
        # chat claimed AUTO-INSERTED while the editor sat empty after restart).
        page.wait_for_function(
            "document.getElementById('codeInput').value.indexOf('RESTORE-MARKER') !== -1",
            timeout=15000,
        )
        restore_editor_ok = page.evaluate(
            "document.getElementById('codeInput').value.indexOf('RESTORE-MARKER') !== -1"
        )
        restore_monaco_ok = page.evaluate(
            "(window.__monacoEditor ? window.__monacoEditor.getValue() : document.getElementById('codeInput').value).indexOf('RESTORE-MARKER') !== -1"
        )
        restore_preview_ok = page.evaluate(
            "document.getElementById('liveFrame').srcdoc.indexOf('RESTORE-MARKER') !== -1"
        )
        restore_settings_ok = page.evaluate(
            "document.getElementById('resolution').value === '1280x720'"
            " && document.getElementById('clipLength').value === '12'"
            " && document.getElementById('frameRate').value === '60'"
            " && document.getElementById('codec').value === 'h264'"
        )
        restore_note_ok = page.evaluate(
            "Array.from(document.querySelectorAll('#chatMessages .chat-note')).some(n => n.textContent.includes('AUTO-INSERTED'))"
        )

        page.evaluate(
            "document.getElementById('codeInput').value = '<!DOCTYPE html><html><body><h1>MOTION</h1></body></html>'"
        )
        page.wait_for_timeout(400)
        editor_value = page.input_value("#codeInput")
        editor_filled = "MOTION" in editor_value
        monaco_synced = page.evaluate(
            "(window.__monacoEditor ? window.__monacoEditor.getValue() : document.getElementById('codeInput').value).indexOf('MOTION') !== -1"
        )

        # 5. Shortcut help modal opens with "?" and closes with Escape.
        page.keyboard.press("?")
        page.wait_for_timeout(250)
        help_open = page.locator("#shortcutHelpModal").is_visible()
        page.keyboard.press("Escape")
        page.wait_for_timeout(250)
        help_closed = not page.locator("#shortcutHelpModal").is_visible()

        # 6. Layout sanity: the hero heading and sidebar should be on screen.
        hero_visible = page.locator(".masthead, header").first.is_visible()

        # 7. Control Room layout: code left, stage center, Clipppa right, with
        # the export recipe living in its own tab.
        chat_controls = {
            "controlRoom": page.locator(".control-room").count(),
            "codePane": page.locator(".code-pane").count(),
            "stagePane": page.locator(".stage-pane").count(),
            "dock": page.locator(".transport-dock").count(),
            "recipeTab": page.locator("#tabRecipe").count(),
            "aiChat": page.locator("#aiChat").count(),
            "llmProvider": page.locator("#llmProvider").count(),
            "llmModel": page.locator("#llmModel").count(),
            "keyGemini": page.locator("#keyGemini").count(),
            "keyMistral": page.locator("#keyMistral").count(),
            "settingsBtn": page.locator("#settingsBtn").count(),
            "settingsModal": page.locator("#settingsModal").count(),
            "chatModelBtn": page.locator("#chatModelBtn").count(),
            "chatModelMenu": page.locator("#chatModelMenu").count(),
            "chatInput": page.locator("#chatInput").count(),
            "chatSend": page.locator("#chatSend").count(),
            "chatNew": page.locator("#chatNew").count(),
            "chatHistoryList": page.locator("#chatHistoryList").count(),
        }
        editor_box = page.locator("#monacoHost").bounding_box()
        chat_box = page.locator("#aiChat").bounding_box()
        stage_box = page.locator(".stage-pane").bounding_box()
        side_box = page.locator(".code-pane").bounding_box()
        chat_right_of_editor = bool(editor_box and chat_box and chat_box["x"] >= editor_box["x"] + editor_box["width"] - 1)
        stage_center_between = bool(
            side_box and stage_box and chat_box
            and side_box["x"] + side_box["width"] <= stage_box["x"] + 1
            and stage_box["x"] + stage_box["width"] <= chat_box["x"] + 1
        )

        # Sending without an API key surfaces an inline error bubble and opens
        # Settings. Start a fresh chat first so the migrated legacy session
        # stays untouched.
        open_chat_history()
        page.click("#chatNew")
        page.wait_for_timeout(400)
        page.fill("#chatInput", "make a bouncing ball animation")
        page.click("#chatSend")
        page.wait_for_timeout(400)
        chat_error_visible = page.locator("#chatMessages .chat-msg.error").count() > 0
        chat_user_echo = page.locator("#chatMessages .chat-msg.user").count() > 0
        settings_opened_on_error = page.locator("#settingsModal").is_visible()
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        settings_closed = not page.locator("#settingsModal").is_visible()

        # Composer model selector: closed by default, opens from the pill inside
        # the chat composer, lists both providers, and closes with Escape. With
        # no keys saved it shows an "Add <provider> key" hint per provider.
        composer_gear_absent = (
            page.locator("#chatHeadSettings").count() == 0
            and page.locator("#chatHeadModel").count() == 0
        )
        page.click("#chatModelBtn")
        page.wait_for_timeout(300)
        composer_menu_open = page.locator("#chatModelMenu").is_visible()
        composer_menu_groups = page.locator("#chatModelMenu .chat-model-group").all_inner_texts()
        composer_hints = page.locator("#chatModelMenu .chat-model-hint").all_inner_texts()
        composer_hints_ok = (
            len(composer_hints) == 2
            and all("key in Settings" in hint for hint in composer_hints)
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        composer_menu_closed = not page.locator("#chatModelMenu").is_visible()
        composer_menu_ok = (
            composer_menu_open
            and composer_menu_closed
            and [g.lower() for g in composer_menu_groups] == ["gemini", "mistral"]
            and composer_hints_ok
        )

        # Settings modal: opens from the sidebar button and keeps only the
        # appearance, font, code-color and API-key sections (provider and model
        # controls now live in the chat composer).
        page.click("#settingsBtn")
        page.wait_for_timeout(250)
        settings_opens = page.locator("#settingsModal").is_visible()
        settings_sections = page.locator("#settingsModal .settings-label").all_inner_texts()
        settings_sections_ok = settings_sections == [
            "APPEARANCE", "FONT & TEXT SIZE", "CODE COLORS", "PERFORMANCE", "API KEYS"
        ]
        resolution_count = page.locator("#aspectRatio option").count()
        resolution_tiers = page.locator("#resolutionTier option").count()
        fps_values = page.locator("#frameRate option").evaluate_all("els => els.map(e => e.value)")
        output_options_ok = (
            resolution_count == 5
            and resolution_tiers >= 6
            and fps_values == ["24", "25", "30", "48", "50", "60", "120"]
        )
        gpu_toggle_off = page.get_attribute("#gpuBoostToggle", "aria-pressed") == "false"
        page.click("#gpuBoostToggle")
        page.wait_for_timeout(150)
        gpu_toggle_on = page.get_attribute("#gpuBoostToggle", "aria-pressed") == "true"
        page.click("#gpuBoostToggle")
        page.wait_for_timeout(150)
        gpu_toggle_restored = page.get_attribute("#gpuBoostToggle", "aria-pressed") == "false"
        model_select_auto = page.input_value("#llmModel") == "auto"
        composer_label_auto = page.locator("#chatModelLabel").inner_text() == "AUTO · Gemini"

        # Label contrast: section captions (CHATS, ANIMATION CODE, empty states)
        # must stay readable against whatever panel sits behind them, in both modes.
        label_contrast_js = (
            "(() => {"
            " const lum = c => { const m = c.match(/\\d+/g).map(Number).map(v => { v /= 255;"
            "  return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); });"
            "  return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; };"
            " const bgOf = el => { let n = el;"
            "  while (n) { const c = getComputedStyle(n).backgroundColor;"
            "   if (c && c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c; n = n.parentElement; }"
            "  return 'rgb(0, 0, 0)'; };"
            " const ratio = (a, b) => { const l1 = lum(a), l2 = lum(b);"
            "  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); };"
            " const sels = ['.eyebrow', '.assistant-name', '.chat-empty', '.settings-label'];"
            " return sels.map(s => { const el = document.querySelector(s);"
            "  return el ? Math.round(ratio(getComputedStyle(el).color, bgOf(el)) * 10) / 10 : 99; });"
            "})()"
        )

        # Appearance: dark/light plus six tinted themes. Light flips body.light
        # and swaps the surface palette; each color theme tints the whole panel
        # ramp; Dark restores the defaults.
        theme_cards_total = page.locator("#themeGrid .theme-card").count()
        page.click('#themeGrid .theme-card[data-theme-key="light"]')
        page.wait_for_timeout(300)
        light_theme_ok = page.evaluate(
            "(() => { const s = getComputedStyle(document.documentElement);"
            " return document.body.classList.contains('light')"
            " && s.getPropertyValue('--go-rgb').trim() === '109, 125, 0'"
            " && getComputedStyle(document.body).backgroundColor === 'rgb(242, 243, 237)'"
            " && window.__codeColors.text === '#23272e'"
            " && window.__codeColors.keyword === '#6d7d00'"
            " && document.querySelector('#themeGrid .theme-card[data-theme-key=\"light\"]').classList.contains('active'); })()"
        )
        light_panels_ok = page.evaluate(
            "getComputedStyle(document.querySelector('.right-pane')).backgroundColor === 'rgb(251, 251, 248)'"
        )
        light_labels_ok = all(v >= 4.0 for v in page.evaluate(label_contrast_js))

        tinted_themes = {
            "violet": ("rgb(13, 9, 22)", "rgb(18, 12, 30)", "180, 124, 255"),
            "ember": ("rgb(18, 11, 7)", "rgb(23, 14, 9)", "255, 122, 69"),
            "ocean": ("rgb(5, 18, 16)", "rgb(7, 22, 19)", "47, 227, 196"),
            "rose": ("rgb(18, 7, 13)", "rgb(23, 10, 17)", "255, 95, 162"),
            "mint": ("rgb(7, 18, 10)", "rgb(9, 22, 13)", "110, 231, 135"),
            "gold": ("rgb(16, 14, 6)", "rgb(21, 18, 7)", "245, 197, 66"),
        }
        color_themes_ok = True
        color_labels_ok = True
        for key, (bg_rgb, panel_rgb, go_rgb) in tinted_themes.items():
            page.click(f'#themeGrid .theme-card[data-theme-key="{key}"]')
            page.wait_for_timeout(250)
            color_themes_ok = color_themes_ok and page.evaluate(
                f"""(() => {{
                  const s = getComputedStyle(document.documentElement);
                  const card = document.querySelector('#themeGrid .theme-card[data-theme-key="{key}"]');
                  return document.body.classList.contains('theme-{key}')
                    && !document.body.classList.contains('light')
                    && s.getPropertyValue('--go-rgb').trim() === '{go_rgb}'
                    && getComputedStyle(document.body).backgroundColor === '{bg_rgb}'
                    && getComputedStyle(document.querySelector('.right-pane')).backgroundColor === '{panel_rgb}'
                    && card.classList.contains('active');
                }})()"""
            )
            color_labels_ok = color_labels_ok and all(v >= 4.0 for v in page.evaluate(label_contrast_js))

        page.click('#themeGrid .theme-card[data-theme-key="dark"]')
        page.wait_for_timeout(300)
        theme_ok = page.evaluate(
            "(() => { const s = getComputedStyle(document.documentElement);"
            " return !document.body.classList.contains('light')"
            " && ![...document.body.classList].some(c => c.startsWith('theme-'))"
            " && s.getPropertyValue('--go-rgb').trim() === '200, 255, 0'"
            " && window.__codeColors.text === '#e8e6e0'"
            " && document.querySelector('#themeGrid .theme-card[data-theme-key=\"dark\"]').classList.contains('active'); })()"
        )
        dark_labels_ok = all(v >= 4.0 for v in page.evaluate(label_contrast_js))

        # Font + text size: family swap updates the CSS var and the editor
        # font, the size slider scales the root font, and the label follows.
        page.select_option("#fontFamily", "cascadia-code")
        page.wait_for_timeout(200)
        font_family_applied = page.evaluate(
            "(() => { const s = getComputedStyle(document.documentElement).getPropertyValue('--mono');"
            " return s.indexOf('Cascadia Code') !== -1"
            " && (document.getElementById('codeInput').style.fontFamily || '').indexOf('Cascadia Code') !== -1; })()"
        )
        page.evaluate(
            "() => { const el = document.getElementById('fontSizeRange'); el.value = '115';"
            " el.dispatchEvent(new Event('input', { bubbles: true })); }"
        )
        page.wait_for_timeout(200)
        font_size_applied = page.evaluate(
            "getComputedStyle(document.documentElement).fontSize === '18.4px'"
            " && document.getElementById('fontSizeValue').textContent === '115%'"
        )

        # Code colors: pickers recolor the editor text/keywords live; RESET
        # restores the theme defaults.
        page.evaluate(
            "() => { const el = document.getElementById('colorText'); el.value = '#ff0000';"
            " el.dispatchEvent(new Event('input', { bubbles: true })); }"
        )
        page.evaluate(
            "() => { const el = document.getElementById('colorKeyword'); el.value = '#00aaff';"
            " el.dispatchEvent(new Event('input', { bubbles: true })); }"
        )
        page.wait_for_timeout(200)
        colors_applied = page.evaluate(
            "window.__codeColors.text === '#ff0000' && window.__codeColors.keyword === '#00aaff'"
        )
        page.click("#colorReset")
        page.wait_for_timeout(200)
        colors_reset = page.evaluate(
            "window.__codeColors.text === '#e8e6e0' && window.__codeColors.keyword === '#c8ff00'"
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # Drag splitters: left sidebar +40px, right panel +40px (shrinks it),
        # chat row +60px (shrinks it). The screen must stay fixed: dragging
        # one splitter only resizes its own panel — other panels never move.
        def drag_splitter(selector, dx, dy):
            box = page.locator(selector).bounding_box()
            page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            page.mouse.down()
            page.mouse.move(box["x"] + box["width"] / 2 + dx, box["y"] + box["height"] / 2 + dy, steps=5)
            page.mouse.up()
            page.wait_for_timeout(200)

        def panel_rects():
            return page.evaluate(
                "(() => { const r = s => { const b = document.querySelector(s).getBoundingClientRect();"
                " return [b.left, b.top, b.right, b.bottom]; };"
                " return { side: r('.code-pane'), ctrl: r('.right-pane'), splitR: r('#splitRight') }; })()"
            )

        before_rects = panel_rects()
        drag_splitter("#splitLeft", 40, 0)
        after_left_drag = panel_rects()
        # Dragging the left splitter resizes only the sidebar; the right
        # controls panel and its splitter must not move at all.
        panels_stable_after_left = (
            after_left_drag["ctrl"] == before_rects["ctrl"]
            and after_left_drag["splitR"] == before_rects["splitR"]
            and after_left_drag["side"][0] == before_rects["side"][0]
            and after_left_drag["side"][2] > before_rects["side"][2]
        )
        drag_splitter("#splitRight", 40, 0)
        after_right_drag = panel_rects()
        # Dragging the right splitter resizes only the controls panel; the
        # sidebar must not move, and the panel must stay pinned to the screen's
        # right edge.
        panels_stable_after_right = (
            after_right_drag["side"] == after_left_drag["side"]
            and abs(after_right_drag["ctrl"][2] - before_rects["ctrl"][2]) < 1
        )
        drag_splitter("#splitMid", 0, 60)
        panels_drag_ok = page.evaluate(
            "(() => { const s = getComputedStyle(document.documentElement);"
            " return s.getPropertyValue('--col-left').trim() === '340px'"
            " && s.getPropertyValue('--col-right').trim() === '304px'"
            " && s.getPropertyValue('--row-chat').trim() === '280px'; })()"
        ) and panels_stable_after_left and panels_stable_after_right

        # Growing the chat row must never make the page scrollable. When the
        # shell overflowed, any scroll gesture (wheel/touchpad) shifted the
        # whole app and pushed the header off-screen.
        rects_before_tall = panel_rects()
        drag_splitter("#splitMid", 0, -220)
        layout_fixed_ok = page.evaluate(
            "(() => { const se = document.scrollingElement;"
            " const s = getComputedStyle(document.documentElement);"
            " window.scrollTo(0, 300);"
            " window.dispatchEvent(new Event('resize'));"
            " const headerTop = document.querySelector('header').getBoundingClientRect().top;"
            " const noOverflow = se.scrollHeight - se.clientHeight <= 1;"
            " return window.scrollY === 0 && Math.abs(headerTop) < 1 && noOverflow"
            " && s.getPropertyValue('--row-chat').trim() === '500px'; })()"
        )
        rects_after_tall = panel_rects()
        # The dock spans the full width, so growing it shortens every column;
        # what must never change is their horizontal placement.
        screen_fixed_ok = (
            rects_after_tall["side"][:3] == rects_before_tall["side"][:3]
            and rects_after_tall["ctrl"][0] == rects_before_tall["ctrl"][0]
            and rects_after_tall["ctrl"][2] == rects_before_tall["ctrl"][2]
            and rects_after_tall["splitR"][0] == rects_before_tall["splitR"][0]
        )
        drag_splitter("#splitMid", 0, 220)

        # Shrinking the window must reflow the editor/chat column. Monaco keeps a
        # fixed canvas width, so without a shrinkable grid track the chat
        # composer (textarea + model pill) was clipped behind the right panel.
        page.set_viewport_size({"width": 1280, "height": 800})
        page.wait_for_timeout(600)
        shrink_composer_ok = page.evaluate(
            "(() => { const c = document.getElementById('aiChat').getBoundingClientRect();"
            " const f = document.querySelector('.chat-composer').getBoundingClientRect();"
            " const b = document.getElementById('chatModelBtn').getBoundingClientRect();"
            " return f.width <= c.width + 1 && b.right <= c.right + 1 && b.width > 0; })()"
        )
        page.set_viewport_size({"width": 1600, "height": 1100})
        page.wait_for_timeout(600)

        # Render-history popover: the header HISTORY button opens a hovering
        # box listing rendered videos (name + date + duration + format). The
        # header badge marks unread renders only and clears when the list opens;
        # entries themselves stay until deleted.
        history_badge_idle = page.locator("#historyCount").inner_text() == ""
        fresh_render_badge = page.evaluate(
            "(() => { saveRunHistory({timestamp: Date.now(), name: 'clipacanvas_20261101_090000.mp4',"
            " duration: '0.8', frameCount: '24', codec: 'h264', format: 'mp4'});"
            " renderRunHistory(); return document.getElementById('historyCount').textContent; })()"
        )
        page.click("#historyBtn")
        page.wait_for_timeout(250)
        history_pop_open = page.locator("#historyPop").is_visible()
        history_badge_after_open = page.locator("#historyCount").inner_text()
        history_rows = page.locator("#historyPop .history-row").count()
        history_name = page.locator("#historyPop .history-name").first.inner_text()
        history_meta = page.locator("#historyPop .history-meta").first.inner_text()
        history_entry_ok = (
            history_name == "clipacanvas_20261101_090000.mp4"
            and "0.8s" in history_meta
            and "MP4" in history_meta
        )
        history_badge = (
            history_badge_idle
            and fresh_render_badge == "1"
            and history_badge_after_open == ""
            and history_rows == 2
        )
        history_del_label = page.locator("#historyPop .history-del").first.inner_text() == "DELETE"
        while page.locator("#historyPop .history-del").count():
            if not page.locator("#historyPop").is_visible():
                page.click("#historyBtn")
                page.wait_for_timeout(150)
            page.locator("#historyPop .history-del").first.click()
            page.wait_for_timeout(200)
        history_deleted = (
            page.locator("#historyPop .history-row").count() == 0
            and page.locator("#historyPop .history-empty").count() == 1
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        history_pop_closed = not page.locator("#historyPop").is_visible()

        # 8. Mocked LLM reply: auto-insert into editor + settings applied from SETTINGS tag.
        import json as _json

        fake_reply = (
            "Sure:\n```html\n<!DOCTYPE html><html><body>"
            "<canvas id='c' width='540' height='960'></canvas>"
            "<script>const x=1;<\/script></body></html>\n"
            "<!--SETTINGS resolution=720x720 fps=30 duration=4 format=webm bitrate=2M-->\n```"
        )

        chat_post_bodies = []

        fake_gemini_models = [
            {"name": "models/gemini-2.5-pro", "displayName": "Gemini 2.5 Pro",
             "description": "Flagship model for complex reasoning and long-context code.",
             "inputTokenLimit": 1048576, "outputTokenLimit": 65536},
            {"name": "models/gemini-2.5-flash", "displayName": "Gemini 2.5 Flash",
             "description": "Balanced speed and quality for coding and media tasks.",
             "inputTokenLimit": 1048576, "outputTokenLimit": 65536},
            {"name": "models/gemini-2.5-flash-lite", "displayName": "Gemini 2.5 Flash-Lite",
             "description": "Fastest and cheapest model for simple requests.",
             "inputTokenLimit": 1048576, "outputTokenLimit": 65536},
        ]
        fake_mistral_models = [
            {"name": "mistral-large-latest", "displayName": "Mistral Large",
             "description": "Flagship Mistral model for complex reasoning.",
             "inputTokenLimit": 131072, "outputTokenLimit": 8192},
            {"name": "mistral-small-latest", "displayName": "Mistral Small",
             "description": "Fast, cheap Mistral model for simple requests.",
             "inputTokenLimit": 131072, "outputTokenLimit": 8192},
        ]

        def fake_llm(route):
            if route.request.url.endswith("/api/llm/models"):
                try:
                    req = _json.loads(route.request.post_data or "{}")
                except ValueError:
                    req = {}
                if req.get("apiKey") == "bad-key":
                    route.fulfill(status=502, content_type="application/json", body=_json.dumps({
                        "ok": False,
                        "error": "Gemini API error (400).",
                        "detail": "API key not valid.",
                    }))
                    return
                models = fake_mistral_models if req.get("provider") == "mistral" else fake_gemini_models
                body = _json.dumps({"ok": True, "models": models})
            else:
                post_data = route.request.post_data or ""
                try:
                    chat_body = _json.loads(post_data)
                except ValueError:
                    chat_body = {}
                chat_post_bodies.append(chat_body)
                body_messages = chat_body.get("messages") if isinstance(chat_body.get("messages"), list) else []
                last_user_text = ""
                for message in reversed(body_messages):
                    if isinstance(message, dict) and message.get("role") == "user":
                        last_user_text = str(message.get("content") or "")
                        break
                tool_rounds = sum(
                    1 for message in body_messages
                    if isinstance(message, dict) and message.get("role") == "tool"
                )
                base_reply = {"ok": True, "provider": "gemini", "model": "models/gemini-2.5-flash"}
                sys_text = " ".join(
                    str(message.get("content") or "") for message in body_messages
                    if isinstance(message, dict) and message.get("role") == "system"
                )
                if "You title chat conversations" in sys_text:
                    transcript = " ".join(
                        str(message.get("content") or "") for message in body_messages
                        if isinstance(message, dict)
                    )
                    if "TOOL_FLOW" in transcript:
                        title = "Tool Flow Run"
                    elif "orbits" in transcript:
                        title = "Orbit Question"
                    else:
                        title = "Bouncing Ball Demo"
                    route.fulfill(status=200, content_type="application/json", body=_json.dumps({
                        **base_reply, "text": title,
                    }))
                    return
                if "RATE_LIMIT" in last_user_text:
                    route.fulfill(status=429, content_type="application/json", body=_json.dumps({
                        "ok": False,
                        "error": "Gemini rate limit reached (429) — the API key has used its request quota. "
                                 "Try again in about 7s. Or pick a different model.",
                        "detail": "",
                        "retryAfterSeconds": 7,
                    }))
                    return
                if "STRUCTURED_DUMP" in last_user_text:
                    body = _json.dumps({**base_reply,
                                        "text": "[{\"type\": 'thinking', 'thinking': [{\"type\": 'text', 'text': 'secret reasoning'}]}]"})
                elif "TOOL_RENDER" in last_user_text:
                    has_render = any(
                        isinstance(message, dict) and message.get("name") == "render_video"
                        for message in body_messages
                    )
                    if has_render:
                        body = _json.dumps({**base_reply, "text": "Render complete."})
                    else:
                        body = _json.dumps({**base_reply, "text": "", "toolCalls": [
                            {"id": "call_render", "name": "render_video", "args": {}},
                        ]})
                elif "TOOL_FLOW" in last_user_text:
                    has_insert = any(
                        isinstance(message, dict) and message.get("name") == "insert_animation_code"
                        for message in body_messages
                    )
                    if tool_rounds == 0:
                        body = _json.dumps({**base_reply, "text": "", "toolCalls": [
                            {"id": "call_state", "name": "get_app_state", "args": {}},
                            {"id": "call_settings", "name": "set_export_settings", "args": {
                                "resolution": "1280x720", "fps": 60, "duration": 6,
                                "format": "mp4", "bitrate": "10M"}},
                        ]})
                    elif not has_insert:
                        body = _json.dumps({**base_reply, "text": "", "toolCalls": [
                            {"id": "call_code", "name": "insert_animation_code", "args": {
                                "code": "<!DOCTYPE html><html><body>"
                                        "<canvas id='toolc' width='720' height='1280'></canvas>"
                                        "<script>const TOOL_INSERTED = 1;<\/script>"
                                        "</body></html>"}},
                        ]})
                    else:
                        body = _json.dumps({**base_reply, "text": "Inserted the tool animation and set landscape 60 FPS."})
                else:
                    body = _json.dumps({**base_reply, "text": fake_reply})
            route.fulfill(status=200, content_type="application/json", body=body)

        page.route("**/api/llm/models", fake_llm)
        page.route("**/api/llm/chat", fake_llm)

        # Composer model selector: filling a key refreshes that provider's
        # models; opening the popover lazily loads the other provider too. Rows
        # are ordered AUTO, Gemini models, Mistral models; each model shows its
        # context/output sizes and keeps its description as the tooltip.
        page.click("#settingsBtn")
        page.wait_for_timeout(250)
        page.fill("#keyGemini", "test-key-123")
        page.fill("#keyMistral", "test-key-456")
        page.wait_for_function(
            "document.getElementById('llmModel').options.length >= 4",
            timeout=10000,
        )
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # API health: a rejected key lights the composer "!" and the model menu
        # shows an actionable error; restoring a good key clears both.
        page.click("#settingsBtn")
        page.wait_for_timeout(200)
        page.fill("#keyGemini", "bad-key")
        page.wait_for_function(
            "document.getElementById('chatModelWarn') && !document.getElementById('chatModelWarn').hidden",
            timeout=15000,
        )
        health_warn_visible = not page.locator("#chatModelWarn").is_hidden()
        health_warn_title = page.get_attribute("#chatModelWarn", "title") or ""
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        page.click("#chatModelBtn")
        page.wait_for_timeout(250)
        health_menu_error = page.locator("#chatModelMenu .chat-model-hint.error").count() == 1
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)
        page.click("#settingsBtn")
        page.wait_for_timeout(200)
        page.fill("#keyGemini", "test-key-123")
        page.wait_for_function(
            "document.getElementById('chatModelWarn') && document.getElementById('chatModelWarn').hidden",
            timeout=15000,
        )
        health_cleared = page.locator("#chatModelWarn").is_hidden()
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        provider_health_ok = (
            health_warn_visible
            and "Gemini API error" in health_warn_title
            and health_menu_error
            and health_cleared
        )

        page.click("#chatModelBtn")
        page.wait_for_function(
            "document.querySelectorAll('#chatModelMenu .chat-model-item').length >= 6",
            timeout=10000,
        )
        menu_rows = page.locator("#chatModelMenu .chat-model-item").count()
        menu_groups = page.locator("#chatModelMenu .chat-model-group").all_inner_texts()
        menu_meta = page.locator("#chatModelMenu .chat-model-item").nth(2).locator(".m-meta").inner_text()
        menu_first_title = page.locator("#chatModelMenu .chat-model-item").nth(1).get_attribute("title") or ""
        menu_rows_ok = [g.lower() for g in menu_groups] == ["gemini", "mistral"] and menu_rows >= 6
        menu_meta_ok = "ctx 1M" in menu_meta and "out 65.5K" in menu_meta
        menu_desc_ok = "Flagship" in menu_first_title

        page.locator("#chatModelMenu .chat-model-item").nth(2).click()
        page.wait_for_timeout(200)
        model_pick_ok = page.input_value("#llmModel") == "models/gemini-2.5-flash"
        composer_label_manual = page.locator("#chatModelLabel").inner_text() == "Gemini 2.5 Flash"
        menu_closed_after_pick = not page.locator("#chatModelMenu").is_visible()

        # Selecting a Mistral model switches the hidden provider automatically.
        page.click("#chatModelBtn")
        page.wait_for_timeout(200)
        page.locator("#chatModelMenu .chat-model-item").nth(4).click()
        page.wait_for_timeout(200)
        provider_switch_ok = (
            page.input_value("#llmProvider") == "mistral"
            and page.input_value("#llmModel") == "mistral-large-latest"
            and page.locator("#chatModelLabel").inner_text() == "Mistral Large"
        )

        # AUTO belongs to the active provider, so it reads "AUTO · Mistral" now.
        page.click("#chatModelBtn")
        page.wait_for_timeout(200)
        page.locator("#chatModelMenu .chat-model-item").nth(0).click()
        page.wait_for_timeout(200)
        auto_follows_provider = (
            page.input_value("#llmModel") == "auto"
            and page.locator("#chatModelLabel").inner_text() == "AUTO · Mistral"
        )

        # Back to Gemini + AUTO for the mocked reply below.
        page.click("#chatModelBtn")
        page.wait_for_timeout(200)
        page.locator("#chatModelMenu .chat-model-item").nth(2).click()
        page.wait_for_timeout(150)
        page.click("#chatModelBtn")
        page.wait_for_timeout(150)
        page.locator("#chatModelMenu .chat-model-item").nth(0).click()
        page.wait_for_timeout(200)
        model_back_to_auto = (
            page.input_value("#llmProvider") == "gemini"
            and page.input_value("#llmModel") == "auto"
            and page.locator("#chatModelLabel").inner_text() == "AUTO · Gemini"
        )

        page.evaluate(
            "document.getElementById('codeInput').value = '<!DOCTYPE html><html><body><h1>MOTION</h1></body></html>'"
        )
        page.wait_for_timeout(200)
        page.fill("#chatInput", "make a bouncing ball animation at 720x720, 30fps, 4 seconds, webm, 2M bitrate")
        page.click("#chatSend")
        page.wait_for_selector("#chatMessages .chat-msg.assistant", timeout=10000)
        page.wait_for_selector("#chatMessages .chat-insert", timeout=5000)
        chat_assistant_visible = page.locator("#chatMessages .chat-msg.assistant").count() > 0
        chat_model_label = page.locator("#chatMessages .chat-msg.assistant .chat-model").count() > 0
        model_option_count = page.locator("#llmModel option").count()
        chat_body_has_fallback = bool(chat_post_bodies) and chat_post_bodies[0].get("allowFallback") is True
        chat_request_routing_ok = (
            bool(chat_post_bodies)
            and chat_post_bodies[0].get("provider") == "gemini"
            and chat_post_bodies[0].get("model") == "models/gemini-2.5-flash"
        )
        # Harness: code auto-inserted (before any button click) and settings applied.
        editor_before_click = page.input_value("#codeInput")
        chat_auto_insert = "canvas id='c'" in editor_before_click or "<canvas" in editor_before_click
        chat_note = page.locator("#chatMessages .chat-note").first.inner_text() if page.locator("#chatMessages .chat-note").count() else ""
        chat_settings_applied = (
            page.input_value("#resolution") == "720x720"
            and page.input_value("#frameRate") == "30"
            and page.input_value("#clipLength") == "4"
            and page.input_value("#codec") == "vp9"
            and page.input_value("#bitrate") == "2M"
            and "AUTO-INSERTED" in chat_note
        )
        page.click("#chatMessages .chat-insert")
        page.wait_for_timeout(600)
        editor_after_insert = page.input_value("#codeInput")
        chat_insert_worked = "canvas id='c'" in editor_after_insert or "<canvas" in editor_after_insert

        # The chat title is model-written, not the first user sentence.
        page.wait_for_function(
            "Array.from(document.querySelectorAll('#chatHistoryList .chat-history-title'))"
            ".some(e => e.textContent === 'Bouncing Ball Demo')",
            timeout=15000,
        )
        chat_title_ok = page.locator(
            "#chatHistoryList .chat-history-title", has_text="Bouncing Ball Demo"
        ).count() == 1

        # Reply actions belong to rendered turns only.
        actions_before_render = page.locator("#chatMessages .chat-actions").count()

        # 8a-1. Conversational loop: render notes land in the chat and the
        # latest one is fed back to the model as system context next turn.
        page.evaluate(
            "window.appendRenderNote({status:'ok', width:720, height:720, fps:30,"
            " duration:4, format:'webm', bitrate:'2M', elapsedMs:21400,"
            " filename:'clipacanvas_test.webm'})"
        )
        page.wait_for_selector("#chatMessages .chat-render-note", timeout=5000)
        render_note_text = page.locator("#chatMessages .chat-render-note").last.inner_text()
        render_note_ok = all(
            token in render_note_text
            for token in ("RENDERED", "720x720", "30 FPS", "4.0s", "WEBM", "2M", "21.4s")
        )
        page.evaluate("window.appendRenderNote({status:'error', message:'Render timed out'})")
        render_note_failed_ok = page.locator("#chatMessages .chat-render-note.failed").count() == 1

        chat_actions_ok = page.evaluate(
            "(() => { const actions = document.querySelector('#chatMessages .chat-msg.assistant .chat-actions');"
            " if (!actions) return false;"
            " const labels = Array.from(actions.querySelectorAll('.chat-action')).map(b => b.textContent);"
            " return ['RE-RENDER', 'TWEAK SETTINGS', 'REVERT TO PREVIOUS'].every(l => labels.includes(l)); })()"
        ) and actions_before_render == 0
        revert_enabled = page.evaluate(
            "(() => { const b = Array.from(document.querySelectorAll('#chatMessages .chat-actions .chat-action'))"
            ".find(b => b.textContent === 'REVERT TO PREVIOUS'); return !!b && !b.disabled; })()"
        )
        page.locator("#chatMessages .chat-actions .chat-action", has_text="TWEAK SETTINGS").first.click()
        page.wait_for_timeout(200)
        tweak_focus_ok = page.evaluate("document.activeElement && document.activeElement.id === 'aspectRatio'")
        page.click("#tabAssistant")
        page.wait_for_timeout(200)
        page.evaluate(
            "(() => { window.__renderCalls = 0; window.__realStartConvert = window.startConvert;"
            " window.startConvert = () => { window.__renderCalls += 1; }; return true; })()"
        )
        page.locator("#chatMessages .chat-actions .chat-action", has_text="RE-RENDER").first.click()
        rerender_triggered = page.evaluate("window.__renderCalls === 1")
        page.evaluate("window.startConvert = window.__realStartConvert; delete window.__realStartConvert;")
        page.locator("#chatMessages .chat-actions .chat-action", has_text="REVERT TO PREVIOUS").first.click()
        page.wait_for_timeout(300)
        revert_restored = page.evaluate(
            "document.getElementById('codeInput').value.indexOf('MOTION') !== -1"
        )
        revert_disabled_after = page.evaluate(
            "(() => { const b = Array.from(document.querySelectorAll('#chatMessages .chat-actions .chat-action'))"
            ".find(b => b.textContent === 'REVERT TO PREVIOUS'); return !!b && b.disabled; })()"
        )

        page.fill("#chatInput", "does the render look right")
        page.click("#chatSend")
        page.wait_for_function(
            "document.querySelectorAll('#chatMessages .chat-msg.assistant').length >= 2",
            timeout=10000,
        )
        page.wait_for_timeout(300)
        last_chat_body = next(
            (entry for entry in reversed(chat_post_bodies) if entry.get("tools") is True),
            {},
        )
        render_context_in_request = any(
            m.get("role") == "system"
            and "Latest render result" in str(m.get("content", ""))
            and "RENDER FAILED" in str(m.get("content", ""))
            for m in last_chat_body.get("messages", [])
        )

        # Chat sessions UI: history area lists chats (migrated legacy + new),
        # + NEW CHAT clears the messages box, a second chat becomes its own
        # history row, and the per-row delete button removes it.
        open_chat_history()
        page.wait_for_selector("#chatHistoryList .chat-history-row", timeout=5000)
        chat_history_rows_first = page.locator("#chatHistoryList .chat-history-row").count()
        chat_history_title = page.locator("#chatHistoryList .chat-history-title").first.inner_text()
        chat_title_box = page.locator("#chatHistoryList .chat-history-title").first.bounding_box()
        chat_title_visible = bool(chat_title_box and chat_title_box["width"] >= 90)
        open_chat_history()
        page.click("#chatNew")
        page.wait_for_timeout(400)
        chat_new_clears = page.locator("#chatMessages .chat-empty").count() > 0
        chat_history_rows_after_new = page.locator("#chatHistoryList .chat-history-row").count()
        page.fill("#chatInput", "second question about orbits")
        page.click("#chatSend")
        page.wait_for_selector("#chatMessages .chat-msg.assistant", timeout=10000)
        page.wait_for_function(
            "document.querySelectorAll('#chatHistoryList .chat-history-row').length === 3",
            timeout=10000,
        )
        page.wait_for_function(
            "Array.from(document.querySelectorAll('#chatHistoryList .chat-history-title'))"
            ".some(e => e.textContent === 'Orbit Question')",
            timeout=15000,
        )
        chat_history_rows_second = page.locator("#chatHistoryList .chat-history-row").count()
        chat_history_titles = page.locator("#chatHistoryList .chat-history-title").all_inner_texts()
        page.on("dialog", lambda dialog: dialog.accept())
        open_chat_history()
        page.locator("#chatHistoryList .chat-history-row").first.hover()
        chat_del_label = page.locator("#chatHistoryList .chat-history-row").first.locator(".chat-history-del").text_content() == "DELETE"
        page.locator("#chatHistoryList .chat-history-row").first.locator(".chat-history-del").click()
        page.wait_for_timeout(500)
        chat_history_rows_after_delete = page.locator("#chatHistoryList .chat-history-row").count()
        chat_history_titles_after_delete = page.locator("#chatHistoryList .chat-history-title").all_inner_texts()
        chat_history_ui_ok = (
            chat_history_rows_first == 2
            and chat_history_title == "Bouncing Ball Demo"
            and chat_title_visible
            and chat_new_clears
            and chat_history_rows_after_new == 2
            and chat_history_rows_second == 3
            and "Orbit Question" in chat_history_titles
            and chat_history_rows_after_delete == 2
            and "Orbit Question" not in chat_history_titles_after_delete
        )

        # 8b. A raw structured thinking dump from the provider must never be
        # rendered; the harness shows a clean error bubble instead.
        page.fill("#chatInput", "STRUCTURED_DUMP please")
        page.click("#chatSend")
        page.wait_for_selector("#chatMessages .chat-msg.error", timeout=10000)
        page.wait_for_timeout(300)
        chat_dump_guard_ok = (
            page.locator("#chatMessages .chat-msg.error").count() > 0
            and "secret reasoning" not in page.inner_text("#chatMessages")
            and "thinking" not in page.inner_text("#chatMessages")
        )

        # 8c. Tool loop: the model asks for tools, the app runs them, results go
        # back in the same conversation, and the final reply lands in chat.
        open_chat_history()
        page.click("#chatNew")
        page.wait_for_timeout(300)
        page.fill("#chatInput", "TOOL_FLOW run — make it 1280x720, 60fps, 6 seconds, mp4 at 10M bitrate")
        page.click("#chatSend")
        page.wait_for_function(
            "document.querySelectorAll('#chatMessages .chat-tool-trace').length >= 3"
            " && Array.from(document.querySelectorAll('#chatMessages .chat-msg.assistant'))"
            ".some(m => m.textContent.includes('landscape 60 FPS'))",
            timeout=15000,
        )
        page.wait_for_timeout(300)
        tool_trace_count = page.locator("#chatMessages .chat-tool-trace").count()
        tool_trace_text = " ".join(
            page.locator("#chatMessages .chat-tool-trace").all_inner_texts()
        ).lower()
        tool_editor_code = page.input_value("#codeInput")
        tool_bodies = [
            entry for entry in chat_post_bodies
            if entry.get("tools") is True
            and any(
                isinstance(message, dict)
                and message.get("role") == "user"
                and "TOOL_FLOW" in str(message.get("content", ""))
                for message in entry.get("messages", [])
            )
        ]
        tool_requests_ok = (
            len(tool_bodies) == 3
            and all(entry.get("tools") is True for entry in tool_bodies)
            and any(
                any(isinstance(m, dict) and m.get("name") == "get_app_state"
                    for m in entry.get("messages", []))
                for entry in tool_bodies[1:]
            )
            and any(
                any(isinstance(m, dict) and m.get("name") == "insert_animation_code"
                    for m in entry.get("messages", []))
                for entry in tool_bodies[2:]
            )
        )
        tool_effects_ok = (
            "TOOL_INSERTED" in tool_editor_code
            and page.input_value("#resolution") == "1280x720"
            and page.input_value("#frameRate") == "60"
            and page.input_value("#clipLength") == "6"
            and page.input_value("#codec") == "h264"
            and page.input_value("#bitrate") == "10M"
        )
        tool_flow_ok = (
            tool_requests_ok
            and tool_effects_ok
            and tool_trace_count >= 3
            and all(
                token in tool_trace_text
                for token in ("get_app_state", "set_export_settings", "insert_animation_code")
            )
            and not page.locator("#chatMessages .chat-note").count()
        )

        # 8d. render_video tool: the model asks for a render, the app renders the
        # editor content and the download button ends up ready.
        render_notes_before_tool = page.locator("#chatMessages .chat-render-note").count()
        page.evaluate(
            "(() => { window.__renderTool = null;"
            " window.__realEnsureBackend = window.ensureBackendReady;"
            " window.__realRenderBackend = window.renderWithPlaywrightBackend;"
            " window.ensureBackendReady = async () => {};"
            " window.renderWithPlaywrightBackend = async (code, settings) => {"
            "   window.__renderTool = { code, fps: settings.frameRate, max: settings.maxDuration };"
            "   window.lastRenderMeta = { filename: 'tool-render.mp4', duration: String(settings.maxDuration) };"
            "   appendRenderNote({ status: 'ok', width: 540, height: 960, fps: settings.frameRate,"
            "     duration: settings.maxDuration, format: 'mp4', bitrate: '5M', elapsedMs: 1200 });"
            " }; return true; })()"
        )
        page.fill("#chatInput", "TOOL_RENDER now")
        page.click("#chatSend")
        page.wait_for_function(
            "window.__renderTool != null"
            " && Array.from(document.querySelectorAll('#chatMessages .chat-msg.assistant'))"
            ".some(m => m.textContent.includes('Render complete.'))",
            timeout=15000,
        )
        page.wait_for_timeout(300)
        tool_render_state = page.evaluate(
            "({ code: (window.__renderTool || {}).code || '',"
            "   fps: (window.__renderTool || {}).fps,"
            "   downloadReady: !document.getElementById('btnDownload').disabled })"
        )
        tool_render_traces = [
            text.lower() for text in page.locator("#chatMessages .chat-tool-trace").all_inner_texts()
        ]
        tool_render_notes = page.locator("#chatMessages .chat-render-note").count()
        tool_render_ok = (
            "TOOL_INSERTED" in tool_render_state["code"]
            and tool_render_state["fps"] == 60
            and tool_render_state["downloadReady"]
            and not any("render_video" in text for text in tool_render_traces)
            and tool_render_notes == render_notes_before_tool + 1
        )
        page.evaluate(
            "(() => { window.ensureBackendReady = window.__realEnsureBackend;"
            " window.renderWithPlaywrightBackend = window.__realRenderBackend;"
            " delete window.__realEnsureBackend; delete window.__realRenderBackend; return true; })()"
        )

        # 8e. Switching chats must load that chat's animation into the editor
        # and live preview — including code inserted by the insert_animation_code
        # tool, which never appears in the assistant text as a fenced block.
        open_chat_history()
        page.locator("#chatHistoryList .chat-history-row", has_text="Legacy chat").first.locator(".chat-history-main").click()
        page.wait_for_timeout(600)
        legacy_switch = page.evaluate(
            "({ code: document.getElementById('codeInput').value,"
            "   preview: document.getElementById('liveFrame').srcdoc })"
        )
        page.wait_for_selector("#chatHistoryList .chat-history-row:has-text('Tool Flow Run')", timeout=15000)
        page.locator("#chatHistoryList .chat-history-row", has_text="Tool Flow Run").first.locator(".chat-history-main").click()
        page.wait_for_timeout(600)
        tool_switch = page.evaluate(
            "({ code: document.getElementById('codeInput').value,"
            "   preview: document.getElementById('liveFrame').srcdoc })"
        )
        chat_switch_preview_ok = (
            "RESTORE-MARKER" in legacy_switch["code"]
            and "RESTORE-MARKER" in legacy_switch["preview"]
            and "TOOL_INSERTED" in tool_switch["code"]
            and "TOOL_INSERTED" in tool_switch["preview"]
        )

        # 8f. Chats are stored in SQLite with no message cap, so a long
        # conversation keeps every message.
        open_chat_history()
        page.click("#chatNew")
        page.wait_for_timeout(300)
        page.evaluate(
            "(() => { for (let i = 0; i < 110; i += 1) addChatMessage('user', `history probe ${i}`); return true; })()"
        )
        page.wait_for_timeout(300)
        retention = page.evaluate(
            "({ count: activeSession().messages.length,"
            "   rendered: document.querySelectorAll('#chatMessages .chat-msg').length,"
            "   first: activeSession().messages[0].content,"
            "   last: activeSession().messages[activeSession().messages.length - 1].content })"
        )
        chat_retention_ok = (
            retention["count"] == 110
            and retention["rendered"] == 110
            and retention["first"] == "history probe 0"
            and retention["last"] == "history probe 109"
        )

        # 8g. Scrolling up to read older messages must not be yanked back to
        # the bottom when the view re-renders.
        page.evaluate(
            "(() => { const box = document.getElementById('chatMessages');"
            " box.scrollTop = 0; renderChat(); return true; })()"
        )
        page.wait_for_timeout(200)
        chat_scroll_hold_ok = page.evaluate(
            "document.getElementById('chatMessages').scrollTop < 40"
        )

        # 8h. A provider 429 must surface the readable quota message instead of
        # a bare status code.
        open_chat_history()
        page.click("#chatNew")
        page.wait_for_timeout(300)
        page.fill("#chatInput", "RATE_LIMIT probe")
        page.click("#chatSend")
        page.wait_for_selector("#chatMessages .chat-msg.error", timeout=10000)
        page.wait_for_timeout(300)
        rate_error = page.locator("#chatMessages .chat-msg.error").last.inner_text()
        chat_rate_limit_ok = (
            "rate limit reached (429)" in rate_error
            and "Try again in about 7s" in rate_error
        )

        page.screenshot(
            path=str(ROOT / "output" / "playwright" / "desktop-smoke.png"),
            full_page=False,
        )

        browser.close()

        # 9. Backend proxy rejects a chat call with a missing API key (400 JSON).
        import urllib.request

        llm_missing_key_status = None
        llm_missing_key_body = None
        try:
            request = urllib.request.Request(
                f"{base}/api/llm/chat",
                data=_json.dumps({"provider": "mistral", "apiKey": "", "messages": [{"role": "user", "content": "hi"}]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                llm_missing_key_status = response.status
                llm_missing_key_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            llm_missing_key_status = exc.code
            llm_missing_key_body = exc.read().decode("utf-8")
        except Exception as exc:
            llm_missing_key_body = f"EXC: {exc}"

        try:
            llm_missing_key_payload = _json.loads(llm_missing_key_body or "{}")
        except ValueError:
            llm_missing_key_payload = {}
        llm_missing_key_ok = (
            llm_missing_key_status == 400
            and llm_missing_key_payload.get("ok") is False
            and isinstance(llm_missing_key_payload.get("error"), str)
        )

        # 10. Fallback loop: a bad key fails fast on the first attempt and the
        # models re-fetch, so the endpoint must answer 502 without hanging.
        llm_fallback_status = None
        llm_fallback_body = None
        try:
            request = urllib.request.Request(
                f"{base}/api/llm/chat",
                data=_json.dumps({
                    "provider": "gemini",
                    "apiKey": "bad-key",
                    "model": "models/gemini-2.5-flash",
                    "allowFallback": True,
                    "messages": [{"role": "user", "content": "hi"}],
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                llm_fallback_status = response.status
                llm_fallback_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            llm_fallback_status = exc.code
            llm_fallback_body = exc.read().decode("utf-8")
        except Exception as exc:
            llm_fallback_body = f"EXC: {exc}"

        try:
            llm_fallback_payload = _json.loads(llm_fallback_body or "{}")
        except ValueError:
            llm_fallback_payload = {}
        llm_fallback_ok = (
            llm_fallback_status == 502
            and llm_fallback_payload.get("ok") is False
        )

        # 10b. Structured provider replies: Mistral/Gemini thinking blocks must
        # be stripped server-side so only the assistant's text reaches the chat.
        import serve as serve_mod
        original_http_post = serve_mod.ClipACanvasHandler._llm_http_post

        def fake_http_post(self, url, body, headers, timeout):
            if 'mistral.ai' in url:
                return {'choices': [{'message': {'content': [
                    {'type': 'thinking', 'thinking': 'internal caterpillar reasoning'},
                    {'type': 'text', 'text': 'Portrait 9:16 or landscape 16:9?'},
                ]}}]}
            if 'generativelanguage.googleapis.com' in url:
                return {'candidates': [{'content': {'parts': [
                    {'text': 'internal thought', 'thought': True},
                    {'text': 'Portrait or landscape?'},
                ]}}]}
            return original_http_post(self, url, body, headers, timeout)

        serve_mod.ClipACanvasHandler._llm_http_post = fake_http_post

        def llm_chat_text(provider):
            request = urllib.request.Request(
                f"{base}/api/llm/chat",
                data=_json.dumps({
                    "provider": provider, "apiKey": "k", "model": "x-model",
                    "allowFallback": False,
                    "messages": [{"role": "user", "content": "make a caterpillar"}],
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                return _json.loads(response.read().decode("utf-8"))

        mistral_strip = llm_chat_text("mistral")
        gemini_strip = llm_chat_text("gemini")
        serve_mod.ClipACanvasHandler._llm_http_post = original_http_post
        llm_thinking_stripped_ok = (
            mistral_strip.get("ok") is True
            and mistral_strip.get("text") == "Portrait 9:16 or landscape 16:9?"
            and gemini_strip.get("ok") is True
            and gemini_strip.get("text") == "Portrait or landscape?"
        )

        # 10c. Reasoning-only replies fall back to the next model (AUTO) and
        # fail with a clean message when no fallback is available.
        def fake_http_post_empty(self, url, body, headers, timeout):
            if 'mistral.ai' in url:
                return {'choices': [{'message': {'content': [
                    {'type': 'thinking', 'thinking': 'only reasoning, no text'},
                ]}}]}
            return original_http_post(self, url, body, headers, timeout)

        serve_mod.ClipACanvasHandler._llm_http_post = fake_http_post_empty
        llm_reasoning_only_status = None
        llm_reasoning_only_body = None
        try:
            request = urllib.request.Request(
                f"{base}/api/llm/chat",
                data=_json.dumps({
                    "provider": "mistral", "apiKey": "k", "model": "x-model",
                    "allowFallback": False,
                    "messages": [{"role": "user", "content": "hi"}],
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                llm_reasoning_only_status = response.status
                llm_reasoning_only_body = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            llm_reasoning_only_status = exc.code
            llm_reasoning_only_body = exc.read().decode("utf-8")
        except Exception as exc:
            llm_reasoning_only_body = f"EXC: {exc}"
        serve_mod.ClipACanvasHandler._llm_http_post = original_http_post

        try:
            llm_reasoning_only_payload = _json.loads(llm_reasoning_only_body or "{}")
        except ValueError:
            llm_reasoning_only_payload = {}
        llm_reasoning_only_ok = (
            llm_reasoning_only_status == 502
            and llm_reasoning_only_payload.get("ok") is False
            and "no readable reply" in str(llm_reasoning_only_payload.get("error", ""))
        )

        # 11. Encrypted key store: save keys, load them back, and confirm the
        # on-disk file does not contain the plaintext.
        keys_save_status = None
        try:
            request = urllib.request.Request(
                f"{base}/api/llm/keys",
                data=_json.dumps({"gemini": "k-test-123", "mistral": "m-test-456"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                keys_save_status = response.status
        except urllib.error.HTTPError as exc:
            keys_save_status = exc.code

        keys_get_payload = {}
        try:
            request = urllib.request.Request(f"{base}/api/llm/keys", method="GET")
            with urllib.request.urlopen(request, timeout=10) as response:
                keys_get_payload = _json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            keys_get_payload = {"error": f"EXC: {exc}"}

        keys_roundtrip_ok = (
            keys_save_status == 200
            and keys_get_payload.get("ok") is True
            and keys_get_payload.get("keys", {}).get("gemini") == "k-test-123"
            and keys_get_payload.get("keys", {}).get("mistral") == "m-test-456"
        )

        keys_file = Path(os.environ["CLIPACANVAS_KEYS_DIR"]) / "keys.dat"
        keys_file_plaintext_free = True
        if keys_file.exists():
            disk_raw = keys_file.read_text(encoding="utf-8")
            keys_file_plaintext_free = "k-test-123" not in disk_raw and "m-test-456" not in disk_raw

        # 11b. Chat log store: sessions roundtrip (error roles dropped, modelMeta kept,
        # empty sessions skipped).
        chatlog_save_status = None
        try:
            request = urllib.request.Request(
                f"{base}/api/llm/chatlog",
                data=_json.dumps({"sessions": [
                    {"id": "legacy-1", "title": "Legacy chat", "createdAt": 1, "updatedAt": 2, "messages": [
                        {"role": "user", "content": "legacy message"},
                    ]},
                    {"id": "test-1", "title": "Test chat", "createdAt": 1000, "updatedAt": 2000, "messages": [
                        {"role": "user", "content": "hi there"},
                        {"role": "assistant", "content": "hello!", "modelMeta": {"provider": "gemini", "modelName": "models/gemini-3.6-flash"}, "note": "AUTO-INSERTED", "codeBefore": "<!DOCTYPE html><html></html>"},
                        {"role": "render", "content": "RENDERED · 720x720 · 30 FPS · 4.0s · MP4 · 5M · 21.4s"},
                        {"role": "error", "content": "Chat failed"},
                        {"role": "system", "content": "should be dropped"},
                        "not-a-dict",
                    ]},
                    {"id": "test-empty", "title": "", "messages": []},
                ]}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                chatlog_save_status = response.status
        except urllib.error.HTTPError as exc:
            chatlog_save_status = exc.code

        chatlog_get_payload = {}
        try:
            request = urllib.request.Request(f"{base}/api/llm/chatlog", method="GET")
            with urllib.request.urlopen(request, timeout=10) as response:
                chatlog_get_payload = _json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            chatlog_get_payload = {"error": f"EXC: {exc}"}

        chatlog_sessions = chatlog_get_payload.get("sessions") if isinstance(chatlog_get_payload.get("sessions"), list) else []
        chatlog_sessions_by_id = {s.get("id"): s for s in chatlog_sessions}
        test1 = chatlog_sessions_by_id.get("test-1")
        chatlog_roundtrip_ok = (
            chatlog_save_status == 200
            and chatlog_get_payload.get("ok") is True
            and test1 is not None
            and test1.get("title") == "Test chat"
            and len(test1.get("messages", [])) == 3
            and test1["messages"][0] == {"role": "user", "content": "hi there"}
            and test1["messages"][1].get("modelMeta", {}).get("modelName") == "models/gemini-3.6-flash"
            and test1["messages"][1].get("note") == "AUTO-INSERTED"
            and test1["messages"][1].get("codeBefore") == "<!DOCTYPE html><html></html>"
            and test1["messages"][2].get("role") == "render"
            and "RENDERED" in test1["messages"][2].get("content", "")
            and chatlog_sessions_by_id.get("legacy-1", {}).get("title") == "Legacy chat"
        )

        # DELETE one session via the API, then confirm it is gone and no
        # orphaned messages remain (cascade).
        chatlog_delete_status = None
        chatlog_delete_payload = {}
        try:
            request = urllib.request.Request(f"{base}/api/llm/chatlog?id=test-1", method="DELETE")
            with urllib.request.urlopen(request, timeout=10) as response:
                chatlog_delete_status = response.status
                chatlog_delete_payload = _json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            chatlog_delete_status = exc.code

        chatlog_get_after_delete = {}
        try:
            request = urllib.request.Request(f"{base}/api/llm/chatlog", method="GET")
            with urllib.request.urlopen(request, timeout=10) as response:
                chatlog_get_after_delete = _json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            chatlog_get_after_delete = {"error": f"EXC: {exc}"}
        chatlog_ids_after_delete = [
            s.get("id") for s in chatlog_get_after_delete.get("sessions", [])
        ] if isinstance(chatlog_get_after_delete.get("sessions"), list) else []

        chatlog_db = keys_dir / "chatlog.db"
        chatlog_json = keys_dir / "chatlog.json"
        chatlog_json_backup = keys_dir / "chatlog.json.bak"
        chatlog_db_ok = chatlog_db.exists() and chatlog_db.stat().st_size > 0
        chatlog_migrated = chatlog_json_backup.exists() and not chatlog_json.exists()

        chatlog_cascade_ok = True
        if chatlog_db_ok:
            import sqlite3 as _sqlite3
            conn = _sqlite3.connect(str(chatlog_db))
            orphans = conn.execute("SELECT COUNT(*) FROM messages WHERE session_id = 'test-1'").fetchone()[0]
            conn.close()
            chatlog_cascade_ok = orphans == 0

        chatlog_delete_ok = (
            chatlog_delete_status == 200
            and chatlog_delete_payload.get("ok") is True
            and chatlog_delete_payload.get("deleted") is True
            and "test-1" not in chatlog_ids_after_delete
            and "legacy-1" in chatlog_ids_after_delete
        )

        # An empty full-store save (e.g. a NEW CHAT racing the initial load)
        # must never wipe the stored chats.
        empty_save_status = None
        try:
            request = urllib.request.Request(
                f"{base}/api/llm/chatlog",
                data=_json.dumps({"sessions": []}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                empty_save_status = response.status
        except urllib.error.HTTPError as exc:
            empty_save_status = exc.code
        try:
            request = urllib.request.Request(f"{base}/api/llm/chatlog", method="GET")
            with urllib.request.urlopen(request, timeout=10) as response:
                after_empty_payload = _json.loads(response.read().decode("utf-8"))
        except Exception:
            after_empty_payload = {}
        after_empty_ids = [
            s.get("id") for s in after_empty_payload.get("sessions", [])
        ] if isinstance(after_empty_payload.get("sessions"), list) else []
        chatlog_empty_save_ok = empty_save_status == 200 and "legacy-1" in after_empty_ids

        # 12. Prefs store: theme + panel sizes + fonts + code colors roundtrip,
        # with bounds clamping and invalid-value rejection.
        prefs_post_status = None
        try:
            request = urllib.request.Request(
                f"{base}/api/prefs",
                data=_json.dumps({
                    "theme": "light",
                    "panels": {"colLeft": 9999, "colRight": 300, "rowChat": 10},
                    "fonts": {"family": "fira-code", "sizePct": 999},
                    "codeColors": {"text": "#ff0000", "keyword": "not-a-color", "string": "#00FF00"},
                    "performance": {"gpuBoost": True},
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=10) as response:
                prefs_post_status = response.status
        except urllib.error.HTTPError as exc:
            prefs_post_status = exc.code

        prefs_get_payload = {}
        try:
            request = urllib.request.Request(f"{base}/api/prefs", method="GET")
            with urllib.request.urlopen(request, timeout=10) as response:
                prefs_get_payload = _json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            prefs_get_payload = {"error": f"EXC: {exc}"}

        prefs = prefs_get_payload.get("prefs") if isinstance(prefs_get_payload.get("prefs"), dict) else {}
        prefs_ok = (
            prefs_post_status == 200
            and prefs_get_payload.get("ok") is True
            and prefs.get("theme") == "light"
            and prefs.get("panels", {}).get("colLeft") == 480
            and prefs.get("panels", {}).get("colRight") == 300
            and prefs.get("panels", {}).get("rowChat") == 110
            and prefs.get("fonts", {}).get("family") == "fira-code"
            and prefs.get("fonts", {}).get("sizePct") == 130
            and prefs.get("codeColors", {}).get("text") == "#ff0000"
            and prefs.get("codeColors", {}).get("keyword") == ""
            and prefs.get("codeColors", {}).get("string") == "#00ff00"
            and prefs.get("performance", {}).get("gpuBoost") is True
        )

        # 12b. GPU-boosted render: a tiny direct render must succeed and report
        # which encoder ran (hardware when available, CPU otherwise).
        render_encoder = ""
        render_gpu_status = None
        try:
            render_code = (
                "<!doctype html><html><body style=\"margin:0;background:#000\">"
                "<canvas id=\"c\" width=\"320\" height=\"240\"></canvas>"
                "<script>const c=document.getElementById('c'),x=c.getContext('2d');"
                "function d(){const t=(window.__ccT||0);x.fillStyle='#000';x.fillRect(0,0,320,240);"
                "x.fillStyle='#c8ff00';x.fillRect((t*120)%260,90,60,60);}"
                "let last=0;function loop(ts){if(ts!==last){last=ts;d();}requestAnimationFrame(loop);}"
                "requestAnimationFrame(loop);</script></body></html>"
            )
            request = urllib.request.Request(
                f"{base}/render",
                data=_json.dumps({
                    "code": render_code,
                    "width": 320,
                    "height": 240,
                    "bitrate": "1M",
                    "contentMode": "canvas",
                    "frameRate": 24,
                    "maxDuration": 1.0,
                    "minDuration": 0.7,
                    "settleWindow": 0.4,
                    "codec": "h264",
                    "gpuBoost": True,
                }).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=180) as response:
                render_gpu_status = response.status
                render_encoder = response.headers.get("X-Render-Encoder") or ""
                response.read()
        except urllib.error.HTTPError as exc:
            render_gpu_status = exc.code
        except Exception:
            render_gpu_status = 0
        render_gpu_ok = render_gpu_status == 200 and bool(render_encoder)

    stop_server(server)
    thread.join(timeout=2)

    print("\n--- results ---")
    print("leaked raw JS markers:", leaked or "none")
    print("controls:", controls)
    print("removed sections still present:", removed or "none")
    print("editor filled:", editor_filled, "| monaco active:", monaco_active, "| synced:", monaco_synced)
    print("shortcut modal open/close:", help_open, help_closed)
    print("hero visible:", hero_visible)
    print("chat controls:", chat_controls)
    print("code left of stage:", stage_center_between, "| assistant right of code:", chat_right_of_editor)
    print("chat no-key error bubble:", chat_error_visible, "user echo:", chat_user_echo)
    print("settings opened on error:", settings_opened_on_error, "| closed by Esc:", settings_closed)
    print("settings modal opens:", settings_opens, "| sections:", settings_sections)
    print("composer selector: gear/pill removed:", composer_gear_absent, "| menu:", composer_menu_ok, "| label:", composer_label_auto)
    print("appearance themes:", theme_cards_total, "cards | light:", light_theme_ok, "| panels:", light_panels_ok, "| color themes:", color_themes_ok, "| back to dark:", theme_ok)
    print("label contrast >= 4.0: dark", dark_labels_ok, "| light", light_labels_ok, "| colors", color_labels_ok)
    print("font family applied:", font_family_applied, "| size 115%:", font_size_applied)
    print("code colors applied:", colors_applied, "| reset to defaults:", colors_reset)
    print("panel drags (code 340 / assistant 304 / dock 280):", panels_drag_ok)
    print("document fixed (no page scroll, header pinned, panels still):", layout_fixed_ok, "| screen fixed:", screen_fixed_ok)
    print("chat composer survives window shrink (pill inside column):", shrink_composer_ok)
    print("render history popover:", history_pop_open, "| entry:", history_entry_ok, "| rows:", history_rows, "| unread badge", fresh_render_badge, "->", repr(history_badge_after_open), "| DELETE label:", history_del_label, "| delete:", history_deleted, "| closed:", history_pop_closed)
    print("mocked assistant reply:", chat_assistant_visible, "insert worked:", chat_insert_worked)
    print("chat auto-insert:", chat_auto_insert, "| settings applied:", chat_settings_applied, "| note:", repr(chat_note[:60]))
    print("model-written chat title:", chat_title_ok)
    print("render note:", render_note_ok, "| failure note:", render_note_failed_ok, "| hidden before render:", actions_before_render == 0, "| reply actions:", chat_actions_ok, "| revert enabled:", revert_enabled)
    print("action effects: tweak focus:", tweak_focus_ok, "| re-render:", rerender_triggered, "| revert restored:", revert_restored, "| revert used up:", revert_disabled_after)
    print("render context in next request:", render_context_in_request)
    print("chat history UI:", chat_history_ui_ok, "| rows:", chat_history_rows_first, "->", chat_history_rows_second, "-> deleted:", chat_history_rows_after_delete)
    print("chat DELETE label:", chat_del_label)
    print("structured dump guard:", chat_dump_guard_ok)
    print("tool loop: requests:", tool_requests_ok, "| effects:", tool_effects_ok, "| traces:", tool_trace_count, repr(tool_trace_text[:90]))
    print("render tool:", tool_render_ok, "| fps:", tool_render_state.get("fps"), "| download ready:", tool_render_state.get("downloadReady"), "| traces:", [t.split("\n")[0] for t in tool_render_traces])
    print("chat retention:", chat_retention_ok, "| switch preview:", chat_switch_preview_ok, "| scroll holds:", chat_scroll_hold_ok, "| 429 message:", chat_rate_limit_ok, repr(rate_error[:80]))
    print("assistant model label:", chat_model_label)
    print("model options after refresh:", model_option_count)
    print("menu rows:", menu_rows, "| groups:", menu_rows_ok, "| meta:", menu_meta_ok, "| desc:", menu_desc_ok, "| pick ->", model_pick_ok, "| label:", composer_label_manual, "| closed:", menu_closed_after_pick)
    print("cross-provider switch:", provider_switch_ok, "| AUTO follows provider:", auto_follows_provider, "| back to AUTO:", model_back_to_auto, "| routing:", chat_request_routing_ok)
    print("api health warn:", provider_health_ok, "| warn:", health_warn_visible, "| menu error:", health_menu_error, "| cleared:", health_cleared, "| title:", health_warn_title[:40])
    print("chat body allowFallback:", chat_body_has_fallback)
    print("llm missing-key ->", llm_missing_key_status, llm_missing_key_payload)
    print("llm fallback bad-key ->", llm_fallback_status, llm_fallback_payload)
    print("llm thinking stripped (mistral/gemini):", llm_thinking_stripped_ok, "| reasoning-only 502:", llm_reasoning_only_ok)
    print("keys save/load roundtrip:", keys_roundtrip_ok, "| disk plaintext-free:", keys_file_plaintext_free)
    print("chatlog save/load roundtrip:", chatlog_roundtrip_ok, "| sqlite db:", chatlog_db_ok, "| json migrated:", chatlog_migrated)
    print("chatlog DELETE endpoint:", chatlog_delete_ok, "| cascade no-orphans:", chatlog_cascade_ok, "| empty save protected:", chatlog_empty_save_ok)
    print("prefs roundtrip + clamping:", prefs_ok)
    print("output options:", output_options_ok, f"| aspects: {resolution_count} | tiers: {resolution_tiers} | fps: {fps_values}")
    print("gpu boost toggle:", gpu_toggle_off, "->", gpu_toggle_on, "->", gpu_toggle_restored)
    print("gpu-boosted render:", render_gpu_ok, "| status:", render_gpu_status, "| encoder:", render_encoder)
    print("restored chat re-insert:", restore_editor_ok, "| monaco:", restore_monaco_ok, "| preview:", restore_preview_ok, "| settings:", restore_settings_ok, "| note:", restore_note_ok)
    print("page errors:", errors or "none")
    print("console errors:", console_errors[:5] or "none")

    ok = (
        not leaked
        and all(controls.values())
        and not any(removed.values())
        and editor_filled
        and monaco_synced
        and restore_editor_ok
        and restore_monaco_ok
        and restore_preview_ok
        and restore_settings_ok
        and restore_note_ok
        and help_open
        and help_closed
        and hero_visible
        and all(chat_controls.values())
        and stage_center_between
        and chat_right_of_editor
        and chat_error_visible
        and chat_user_echo
        and settings_opened_on_error
        and settings_closed
        and settings_opens
        and settings_sections_ok
        and output_options_ok
        and gpu_toggle_off
        and gpu_toggle_on
        and gpu_toggle_restored
        and composer_gear_absent
        and composer_menu_ok
        and model_select_auto
        and composer_label_auto
        and theme_ok
        and theme_cards_total == 8
        and light_theme_ok
        and light_panels_ok
        and color_themes_ok
        and dark_labels_ok
        and light_labels_ok
        and color_labels_ok
        and font_family_applied
        and font_size_applied
        and colors_applied
        and colors_reset
        and panels_drag_ok
        and layout_fixed_ok
        and screen_fixed_ok
        and shrink_composer_ok
        and history_pop_open
        and history_rows == 2
        and history_entry_ok
        and history_badge
        and history_del_label
        and history_deleted
        and history_pop_closed
        and chat_assistant_visible
        and chat_insert_worked
        and chat_auto_insert
        and chat_settings_applied
        and chat_title_ok
        and render_note_ok
        and render_note_failed_ok
        and chat_actions_ok
        and revert_enabled
        and tweak_focus_ok
        and rerender_triggered
        and revert_restored
        and revert_disabled_after
        and render_context_in_request
        and chat_history_ui_ok
        and chat_del_label
        and chat_dump_guard_ok
        and tool_flow_ok
        and tool_render_ok
        and chat_retention_ok
        and chat_switch_preview_ok
        and chat_scroll_hold_ok
        and chat_rate_limit_ok
        and chat_model_label
        and model_option_count >= 4
        and menu_rows_ok
        and menu_meta_ok
        and menu_desc_ok
        and model_pick_ok
        and composer_label_manual
        and menu_closed_after_pick
        and provider_switch_ok
        and auto_follows_provider
        and model_back_to_auto
        and chat_request_routing_ok
        and provider_health_ok
        and chat_body_has_fallback
        and llm_missing_key_ok
        and llm_fallback_ok
        and llm_thinking_stripped_ok
        and llm_reasoning_only_ok
        and keys_roundtrip_ok
        and keys_file_plaintext_free
        and chatlog_roundtrip_ok
        and chatlog_db_ok
        and chatlog_migrated
        and chatlog_delete_ok
        and chatlog_cascade_ok
        and chatlog_empty_save_ok
        and prefs_ok
        and render_gpu_ok
        and not errors
    )
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
