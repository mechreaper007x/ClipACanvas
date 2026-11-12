"""Unsaved-work guard, in-app dialogs and sequenced default project names.

WebView2 does not render native confirm/alert dialogs, so every project-flow
confirmation must use the in-app #appDialog. This suite also proves that an
external project file cannot silently replace unsaved editor work.
"""
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from serve import start_server, stop_server, server_url

SHOTS = ROOT / "output" / "playwright"
SHOTS.mkdir(parents=True, exist_ok=True)


def api(base, path):
    with urllib.request.urlopen(base + path, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_home(page, timeout=15000):
    page.wait_for_function("() => document.getElementById('projectHome').hidden === false", timeout=timeout)


def wait_editor(page, timeout=15000):
    page.wait_for_function("() => document.getElementById('projectHome').hidden === true", timeout=timeout)
    page.wait_for_timeout(450)


def create_project(page, name):
    page.click("#homeNew")
    page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
    page.fill("#homeDialogInput", name)
    page.click("#homeDialogConfirm")
    wait_editor(page)
    page.wait_for_function("(n) => document.getElementById('projectName').value === n", arg=name.upper())
    page.wait_for_timeout(400)


def go_home(page, expected_cards=None):
    page.click("#projectHomeBtn")
    wait_home(page)
    if expected_cards is not None:
        page.wait_for_function("(n) => document.querySelectorAll('.home-card').length === n",
                               arg=expected_cards, timeout=15000)
    page.wait_for_timeout(500)


def card(page, project_id):
    return page.locator(f'.home-card[data-project-id="{project_id}"]')


def set_editor_code(page, marker):
    page.evaluate("""(marker) => {
        const input = document.getElementById('codeInput');
        input.value = `<div>${marker}</div>`;
        syncActiveClipFromEditor(true);
    }""", marker)


def external_payload(name, marker):
    return {
        "format": "clipacanvas-project",
        "version": 1,
        "savedAt": "2026-02-01T00:00:00.000Z",
        "projectName": name,
        "timeline": {
            "clips": [{
                "id": "external-clip",
                "name": "EXTERNAL SCENE",
                "code": f"<div>{marker}</div>",
                "duration": 1.5,
                "start": 0,
                "track": 0,
                "explicitDuration": True,
                "type": "code",
                "assetId": "",
                "mediaUrl": "",
                "mediaName": "",
                "sourceIn": 0,
                "fit": "contain",
                "parentClipId": "",
                "audioTrack": "",
            }],
            "transitions": [],
            "audioTracks": [],
            "layers": 1,
            "playhead": 0,
            "assets": [],
        },
    }


def open_external(page, payload, label):
    # applyExternalProject is async; do not await it here because a guard
    # dialog blocks until the test clicks a button.
    page.evaluate("""([payload, label]) => { applyExternalProject(payload, label); }""",
                  [payload, label])


def wait_app_dialog(page, title, timeout=10000):
    page.wait_for_function(
        "(t) => { const d = document.getElementById('appDialog');"
        " return d && !d.hidden && document.getElementById('appDialogTitle').textContent === t; }",
        arg=title, timeout=timeout,
    )


def wait_app_dialog_closed(page, timeout=10000):
    page.wait_for_function("() => document.getElementById('appDialog').hidden === true", timeout=timeout)
    page.wait_for_timeout(300)


with tempfile.TemporaryDirectory() as tmp_name:
    tmp = Path(tmp_name)
    data_dir = tmp / "appdata"
    projects = data_dir / "projects"
    os.environ["CLIPACANVAS_KEYS_DIR"] = str(data_dir)
    server, _thread = start_server()
    base = server_url(server)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1664, "height": 1000})
            page = context.new_page()
            page_errors = []
            page.on("pageerror", lambda exc: page_errors.append(f"pageerror: {exc}"))
            page.goto(f"{base}/clipacanvas.html?home=1", wait_until="load")
            wait_home(page)
            page.evaluate("""() => {
                window.__nativeConfirms = 0;
                window.confirm = () => { window.__nativeConfirms += 1; return false; };
            }""")

            # ── 1. Default project names are sequenced ──────────────────
            page.click("#homeNew")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            assert page.input_value("#homeDialogInput") == "UNTITLED PROJECT"
            page.click("#homeDialogConfirm")
            wait_editor(page)
            page.wait_for_timeout(500)
            go_home(page, expected_cards=1)
            page.click("#homeNew")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            assert page.input_value("#homeDialogInput") == "UNTITLED PROJECT 2", \
                page.input_value("#homeDialogInput")
            page.click("#homeDialogConfirm")
            wait_editor(page)
            page.wait_for_timeout(500)
            go_home(page, expected_cards=2)
            page.click("#homeNew")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            assert page.input_value("#homeDialogInput") == "UNTITLED PROJECT 3", \
                page.input_value("#homeDialogInput")
            page.click("#homeDialogCancel")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === true")
            print("PASS 1 default names sequence without collisions")

            # ── 2. Unsaved work guards an external project open ─────────
            create_project(page, "Guard A")
            set_editor_code(page, "GUARD A UNSAVED")
            open_external(page, external_payload("External B", "EXTERNAL B MARKER"), "external-b.ccproj.json")
            wait_app_dialog(page, "UNSAVED CHANGES")
            page.screenshot(path=str(SHOTS / "project-guard-unsaved.png"))

            page.click("#appDialogCancel")
            wait_app_dialog_closed(page)
            assert page.evaluate("activeProject.id") == "guard-a", "cancel must keep the current project"
            assert "GUARD A UNSAVED" in page.evaluate("document.getElementById('codeInput').value")
            names = [entry["name"] for entry in api(base, "/api/projects")["projects"]]
            assert "EXTERNAL B" not in names, "cancel still imported the external project"
            guard_file = projects / "guard-a.ccproj.json"
            guard_doc = json.loads(guard_file.read_text(encoding="utf-8"))
            assert not any("GUARD A UNSAVED" in (c.get("code") or "") for c in guard_doc["timeline"]["clips"]), \
                "cancel must not save the pending edit either"
            print("PASS 2 unsaved guard cancel keeps the current project")

            # ── 3. Don't Save opens the external project ────────────────
            open_external(page, external_payload("External B", "EXTERNAL B MARKER"), "external-b.ccproj.json")
            wait_app_dialog(page, "UNSAVED CHANGES")
            page.click("#appDialogAlt")
            wait_editor(page)
            page.wait_for_function("() => document.getElementById('projectName').value === 'EXTERNAL B'", timeout=10000)
            assert page.evaluate("activeProject.id") == "external-b"
            guard_doc = json.loads(guard_file.read_text(encoding="utf-8"))
            assert not any("GUARD A UNSAVED" in (c.get("code") or "") for c in guard_doc["timeline"]["clips"]), \
                "don't save still wrote the pending edit to the library"
            print("PASS 3 don't-save replaces the editor without saving")

            # ── 4. Save and Continue saves before replacing ─────────────
            set_editor_code(page, "B UNSAVED WORK")
            open_external(page, external_payload("External C", "EXTERNAL C MARKER"), "external-c.ccproj.json")
            wait_app_dialog(page, "UNSAVED CHANGES")
            page.click("#appDialogConfirm")
            wait_editor(page)
            page.wait_for_function("() => document.getElementById('projectName').value === 'EXTERNAL C'", timeout=10000)
            b_file = projects / "external-b.ccproj.json"
            deadline = time.time() + 10
            saved_b = {}
            while time.time() < deadline:
                saved_b = json.loads(b_file.read_text(encoding="utf-8"))
                if any("B UNSAVED WORK" in (c.get("code") or "") for c in saved_b["timeline"]["clips"]):
                    break
                time.sleep(0.2)
            assert any("B UNSAVED WORK" in (c.get("code") or "") for c in saved_b["timeline"]["clips"]), \
                "save-and-continue did not persist the current project"
            print("PASS 4 save-and-continue persists before replacing")

            # ── 5. In-editor library open uses the in-app dialog ────────
            page.evaluate("() => { openLibraryProject('guard-a'); }")
            wait_app_dialog(page, "OPEN PROJECT")
            page.screenshot(path=str(SHOTS / "project-guard-open.png"))
            page.click("#appDialogCancel")
            wait_app_dialog_closed(page)
            assert page.evaluate("document.getElementById('projectName').value") == "EXTERNAL C", \
                "cancel opened the library project anyway"
            page.evaluate("() => { openLibraryProject('guard-a'); }")
            wait_app_dialog(page, "OPEN PROJECT")
            page.click("#appDialogConfirm")
            wait_editor(page)
            page.wait_for_function("() => document.getElementById('projectName').value === 'GUARD A'", timeout=10000)
            assert "GUARD A UNSAVED" not in page.evaluate("document.getElementById('codeInput').value"), \
                "library open restored unsaved editor code instead of the project copy"
            print("PASS 5 in-editor library open uses the in-app dialog")

            # ── 6. Escape cancels the guard ─────────────────────────────
            set_editor_code(page, "ESCAPE UNSAVED")
            open_external(page, external_payload("External D", "EXTERNAL D MARKER"), "external-d.ccproj.json")
            wait_app_dialog(page, "UNSAVED CHANGES")
            page.keyboard.press("Escape")
            wait_app_dialog_closed(page)
            assert page.evaluate("activeProject.id") == "guard-a", "escape still replaced the project"
            assert "ESCAPE UNSAVED" in page.evaluate("document.getElementById('codeInput').value")
            assert "EXTERNAL D" not in [entry["name"] for entry in api(base, "/api/projects")["projects"]]
            print("PASS 6 escape cancels the unsaved guard")

            # Clear the pending edit so Home flushes cleanly.
            set_editor_code(page, "")
            go_home(page, expected_cards=5)

            # ── 7. Nested card keys do not open the project ────────────
            rename = card(page, "guard-a").locator(".home-mini", has_text="RENAME")
            rename.focus()
            page.keyboard.press("Enter")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            assert page.evaluate("document.getElementById('homeDialogTitle').textContent") == "RENAME PROJECT", \
                "Enter on a nested button opened the project instead of its action"
            assert page.evaluate("document.getElementById('projectHome').hidden === false")
            page.click("#homeDialogCancel")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === true")
            card(page, "guard-a").focus()
            page.keyboard.press("Enter")
            wait_editor(page)
            assert page.evaluate("activeProject.id") == "guard-a", "card Enter should still open the project"
            print("PASS 7 nested card buttons keep keyboard events")

            assert page.evaluate("window.__nativeConfirms") == 0, "a project flow used a native confirm dialog"
            assert not page_errors, page_errors
            browser.close()
    finally:
        stop_server(server)

print("PASS project guard")
