"""Project Home: launcher, project management, autosave isolation, recovery.

Runs the real server with an isolated data dir and drives the real page in
Chromium (?home=1 forces the desktop launcher surface). Every project file,
autosave file and index mutation is asserted on disk, not in the UI alone.
"""
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))

from playwright.sync_api import sync_playwright

from serve import start_server, stop_server, server_url

SHOTS = ROOT / "output" / "playwright"
SHOTS.mkdir(parents=True, exist_ok=True)


def api(base, path, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        base + path,
        data=data,
        method="POST" if data else "GET",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        return exc.code, json.loads(raw or "{}")


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
    page.wait_for_timeout(500)


def go_home(page):
    page.click("#projectHomeBtn")
    wait_home(page)
    page.wait_for_timeout(900)


def card(page, project_id):
    return page.locator(f'.home-card[data-project-id="{project_id}"]')


def wait_file(path: Path, predicate=lambda doc: True, timeout=15):
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if predicate(doc):
                return doc
            last = doc
        except (OSError, ValueError):
            pass
        time.sleep(0.15)
    raise AssertionError(f"timed out waiting for {path.name}: {last}")


def clip(code, name="SCENE", clip_id="seed-clip"):
    return {
        "id": clip_id,
        "name": name,
        "code": code,
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
    }


def project_doc(name, clips, assets=None):
    return {
        "format": "clipacanvas-project",
        "version": 1,
        "savedAt": "2026-01-02T03:04:05.000Z",
        "projectName": name,
        "timeline": {
            "clips": clips,
            "transitions": [],
            "audioTracks": [],
            "layers": 1,
            "playhead": 0,
            "assets": assets or [],
        },
    }


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


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
            console_errors = []
            page.on("pageerror", lambda exc: console_errors.append(f"pageerror: {exc}"))
            page.goto(f"{base}/clipacanvas.html?home=1", wait_until="load")

            # ── 1. First launch: no projects ────────────────────────────
            wait_home(page)
            page.wait_for_function("() => document.getElementById('homeEmpty').hidden === false", timeout=15000)
            assert page.evaluate("document.getElementById('homeProjectCount').textContent") == "0"
            assert page.evaluate("document.getElementById('homeRecover').hidden"), "recovery card should be hidden"
            assert page.evaluate("!document.getElementById('projectHomeBtn').hidden"), "HOME button missing"
            assert page.evaluate("activeProject === null"), "no project should be active at boot"
            assert api(base, "/api/projects")[1]["projects"] == [], "store should start empty"
            page.screenshot(path=str(SHOTS / "project-home-empty.png"))
            print("PASS 1 first launch empty")

            # ── 2. Create a project ─────────────────────────────────────
            page.click("#homeNew")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            assert page.evaluate("document.querySelectorAll('#homeDialog select').length") == 0, \
                "no resolution/fps options should be exposed"
            page.fill("#homeDialogInput", "Alpha")
            page.click("#homeDialogConfirm")
            wait_editor(page)
            page.wait_for_timeout(900)
            assert page.evaluate("document.getElementById('projectName').value") == "ALPHA"
            assert page.evaluate("timelineState.clips.length") == 1, "starter timeline missing"
            assert page.evaluate("timelineState.assets.length") == 0, "new project must not inherit assets"
            active_id = page.evaluate("activeProject && activeProject.id")
            assert active_id == "alpha", active_id
            status, listing = api(base, "/api/projects")
            assert status == 200 and len(listing["projects"]) == 1, listing
            entry = listing["projects"][0]
            assert entry["id"] == "alpha" and entry["name"] == "ALPHA", entry
            assert entry["recoverable"] is False, entry
            alpha_file = projects / "alpha.ccproj.json"
            saved_doc = json.loads(alpha_file.read_text(encoding="utf-8"))
            assert saved_doc["projectId"] == "alpha", saved_doc.get("projectId")
            assert len(saved_doc["timeline"]["clips"]) == 1, saved_doc["timeline"]["clips"]
            assert not (projects / "alpha.autosave.ccproj.json").exists(), "creation must not write an autosave"
            page.screenshot(path=str(SHOTS / "project-home-editor.png"))
            print("PASS 2 create project")

            # ── 3. Multiple independent projects, autosave isolation ────
            page.click("#boxAdd")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=10000)
            alpha_auto = projects / "alpha.autosave.ccproj.json"
            wait_file(alpha_auto, lambda doc: len(doc["timeline"]["clips"]) == 2)
            still_saved = json.loads(alpha_file.read_text(encoding="utf-8"))
            assert len(still_saved["timeline"]["clips"]) == 1, "autosave must not rewrite the library file"
            go_home(page)
            assert card(page, "alpha").count() == 1
            assert page.evaluate("document.querySelectorAll('.home-card .home-badge.recover').length") == 0, \
                "returning home must persist the project, not leave it recoverable"
            wait_file(alpha_file, lambda doc: len(doc["timeline"]["clips"]) == 2)
            assert api(base, "/api/projects")[1]["projects"][0]["recoverable"] is False

            create_project(page, "Beta")
            assert page.evaluate("timelineState.clips.length") == 1, "new project inherited the previous timeline"
            assert page.evaluate("activeProject.id") == "beta"
            page.click("#boxAdd")
            page.click("#boxAdd")
            page.wait_for_function("() => timelineState.clips.length === 3", timeout=10000)
            wait_file(projects / "beta.autosave.ccproj.json", lambda doc: len(doc["timeline"]["clips"]) == 3)
            alpha_auto_doc = json.loads(alpha_auto.read_text(encoding="utf-8"))
            assert len(alpha_auto_doc["timeline"]["clips"]) == 2, "beta autosave overwrote alpha autosave"
            go_home(page)
            wait_file(projects / "beta.ccproj.json", lambda doc: len(doc["timeline"]["clips"]) == 3)
            assert json.loads(alpha_file.read_text(encoding="utf-8"))["timeline"]["clips"].__len__() == 2
            autosaves = sorted(p.name for p in projects.glob("*.autosave.ccproj.json"))
            assert autosaves == ["alpha.autosave.ccproj.json", "beta.autosave.ccproj.json"], autosaves
            assert page.evaluate("document.querySelectorAll('.home-card').length") == 2
            page.screenshot(path=str(SHOTS / "project-home-list.png"))
            print("PASS 3 independent projects + autosave isolation")

            # ── 4. Open an existing project ─────────────────────────────
            card(page, "beta").click()
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 3", timeout=10000)
            assert page.evaluate("document.getElementById('projectName').value") == "BETA"
            go_home(page)
            card(page, "alpha").click()
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=10000)
            assert page.evaluate("document.getElementById('projectName').value") == "ALPHA"
            print("PASS 4 open existing project")

            # ── 5. Rename + duplicate ───────────────────────────────────
            go_home(page)
            card(page, "alpha").locator(".home-mini", has_text="RENAME").click()
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            page.fill("#homeDialogInput", "Alpha Renamed")
            page.click("#homeDialogConfirm")
            page.wait_for_function(
                "() => [...document.querySelectorAll('.home-card-name')].some(n => n.textContent === 'ALPHA RENAMED')",
                timeout=10000,
            )
            renamed = {entry["id"]: entry for entry in api(base, "/api/projects")[1]["projects"]}
            assert renamed["alpha"]["name"] == "ALPHA RENAMED", renamed["alpha"]
            assert renamed["alpha"]["file"] == "alpha.ccproj.json", "rename must keep the project file"
            assert json.loads(alpha_file.read_text(encoding="utf-8"))["projectName"] == "Alpha Renamed"
            assert "RENAMED" in page.evaluate("document.getElementById('homeStatus').textContent")

            card(page, "alpha").locator(".home-mini", has_text="DUPLICATE").click()
            page.wait_for_function(
                "() => document.querySelectorAll('.home-card').length === 3", timeout=15000
            )
            listing = {entry["id"]: entry for entry in api(base, "/api/projects")[1]["projects"]}
            copy_id = "alpha-renamed-copy"
            assert copy_id in listing, listing.keys()
            copy_file = projects / listing[copy_id]["file"]
            assert copy_file.exists(), copy_file
            copy_doc = json.loads(copy_file.read_text(encoding="utf-8"))
            assert copy_doc["projectId"] == copy_id
            assert len(copy_doc["timeline"]["clips"]) == 2
            card(page, copy_id).click()
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=10000)
            page.click("#boxAdd")
            page.wait_for_function("() => timelineState.clips.length === 3", timeout=10000)
            wait_file(projects / f"{copy_id}.autosave.ccproj.json", lambda doc: len(doc["timeline"]["clips"]) == 3)
            go_home(page)
            wait_file(projects / f"{copy_id}.ccproj.json", lambda doc: len(doc["timeline"]["clips"]) == 3)
            assert len(json.loads(alpha_file.read_text(encoding="utf-8"))["timeline"]["clips"]) == 2, \
                "editing the copy changed the original"
            assert not (projects / "alpha.autosave.ccproj.json").exists() or \
                len(json.loads((projects / "alpha.autosave.ccproj.json").read_text())["timeline"]["clips"]) == 2
            page.screenshot(path=str(SHOTS / "project-home-managed.png"))
            print("PASS 5 rename + duplicate")

            # ── 6. Delete with confirmation ─────────────────────────────
            card(page, copy_id).locator(".home-mini", has_text="DELETE").click()
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            page.click("#homeDialogCancel")
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === true")
            assert card(page, copy_id).count() == 1 and copy_file.exists(), "cancel deleted the project"
            card(page, copy_id).locator(".home-mini", has_text="DELETE").click()
            page.wait_for_function("() => document.getElementById('homeDialog').hidden === false")
            page.click("#homeDialogConfirm")
            page.wait_for_function(
                "() => document.querySelectorAll('.home-card').length === 2", timeout=15000
            )
            assert not copy_file.exists(), "project file not deleted"
            assert not (projects / f"{copy_id}.autosave.ccproj.json").exists(), "autosave not deleted"
            assert copy_id not in {entry["id"] for entry in api(base, "/api/projects")[1]["projects"]}
            print("PASS 6 delete with confirmation")

            # ── 8. Recover an interrupted session ───────────────────────
            card(page, "alpha").click()
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=10000)
            page.click("#boxAdd")
            page.wait_for_function("() => timelineState.clips.length === 3", timeout=10000)
            wait_file(projects / "alpha.autosave.ccproj.json", lambda doc: len(doc["timeline"]["clips"]) == 3)
            page.reload(wait_until="load")
            wait_home(page)
            page.wait_for_timeout(900)
            assert page.evaluate("!document.getElementById('homeRecover').hidden"), "recovery card missing"
            assert page.evaluate("document.getElementById('homeRecoverName').textContent").strip() == "ALPHA RENAMED"
            page.screenshot(path=str(SHOTS / "project-home-recover.png"))
            page.click("#homeRecoverBtn")
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 3", timeout=10000)
            assert page.evaluate("document.getElementById('projectName').value") == "ALPHA RENAMED"
            print("PASS 8 recover interrupted session")

            # ── 9. Restart returns to Home; project data intact ─────────
            go_home(page)
            page.reload(wait_until="load")
            wait_home(page)
            page.wait_for_timeout(800)
            assert page.evaluate("localStorage.getItem('clipacanvas.timeline.v1') !== null"), \
                "test should restart with persisted browser storage"
            card(page, "beta").click()
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 3", timeout=10000)
            print("PASS 9 restart returns to Home")

            # ── 10. Existing project compatibility + invalid files ──────
            go_home(page)
            index = json.loads((projects / "index.json").read_text(encoding="utf-8"))
            old_doc = project_doc("Old Project", [clip(
                '<div style="width:100%;height:100%;background:#123"></div>',
                name="LEGACY CLIP", clip_id="legacy-clip-1",
            )])
            old_doc.pop("projectId", None)
            (projects / "old-project.ccproj.json").write_text(json.dumps(old_doc), encoding="utf-8")
            index.append({"id": "old-project", "name": "OLD PROJECT", "file": "old-project.ccproj.json",
                          "savedAt": "2026-01-02T03:04:05.000Z"})
            (projects / "broken.ccproj.json").write_text("{ this is not json", encoding="utf-8")
            index.append({"id": "broken", "name": "BROKEN PROJECT", "file": "broken.ccproj.json",
                          "savedAt": "2026-01-03T03:04:05.000Z"})
            legacy_doc = project_doc("Legacy Session", [clip(
                '<div style="width:100%;height:100%;background:#321"></div>',
                name="LEGACY SESSION CLIP", clip_id="legacy-session-1",
            )])
            # Newer than every library file, but imported "now" will supersede it.
            legacy_doc["savedAt"] = now_iso()
            (projects / "autosave.ccproj.json").write_text(json.dumps(legacy_doc), encoding="utf-8")
            (projects / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

            page.reload(wait_until="load")
            wait_home(page)
            page.wait_for_timeout(900)
            assert card(page, "old-project").count() == 1, "legacy project not listed"
            assert page.evaluate("!document.getElementById('homeRecover').hidden"), "legacy recovery missing"
            assert page.evaluate("document.getElementById('homeRecoverName').textContent").strip() == "LEGACY SESSION"

            # Recover the legacy session first; importing it supersedes the slot.
            page.click("#homeRecoverBtn")
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 1 && timelineState.clips[0].name === 'LEGACY SESSION CLIP'",
                                   timeout=10000)
            assert page.evaluate("document.getElementById('projectName').value") == "LEGACY SESSION"
            go_home(page)
            page.wait_for_timeout(800)
            names = page.evaluate("() => [...document.querySelectorAll('.home-card-name')].map(n => n.textContent)")
            assert "LEGACY SESSION" in names, names
            assert page.evaluate("document.getElementById('homeRecover').hidden"), \
                "legacy recovery must disappear after it is imported"

            # Invalid project: stay on Home with an error, no crash.
            card(page, "broken").click()
            page.wait_for_function(
                "() => document.getElementById('homeStatus').textContent.includes('could not be read')",
                timeout=10000,
            )
            assert page.evaluate("document.getElementById('projectHome').hidden === false"), \
                "invalid project must not open the editor"
            assert card(page, "broken").locator(".home-badge.broken").count() == 1, "missing-file badge absent"

            # Existing v1 project without a projectId still opens and autosaves.
            card(page, "old-project").click()
            wait_editor(page)
            page.wait_for_function("() => timelineState.clips.length === 1", timeout=10000)
            assert page.evaluate("document.getElementById('projectName').value") == "OLD PROJECT"
            page.click("#boxAdd")
            page.wait_for_function("() => timelineState.clips.length === 2", timeout=10000)
            wait_file(projects / "old-project.autosave.ccproj.json",
                      lambda doc: len(doc["timeline"]["clips"]) == 2)
            print("      legacy project autosaved under its own id")
            go_home(page)
            print("PASS 10 compatibility + invalid project handling")

            # ── Missing media degrades gracefully ───────────────────────
            asset = {"id": "ghost-asset", "name": "ghost.png", "kind": "image",
                     "url": "/media/ghost-does-not-exist.png", "duration": None, "addedAt": 0}
            ghost_clip = clip('<div style="width:100%;height:100%;background:#222"></div>',
                              name="GHOST SCENE", clip_id="ghost-clip")
            ghost_clip.update({"type": "image", "assetId": "ghost-asset",
                               "mediaUrl": "/media/ghost-does-not-exist.png", "mediaName": "ghost.png"})
            missing_doc = project_doc("Missing Media", [ghost_clip], [asset])
            (projects / "missing-media.ccproj.json").write_text(json.dumps(missing_doc), encoding="utf-8")
            index = json.loads((projects / "index.json").read_text(encoding="utf-8"))
            index.append({"id": "missing-media", "name": "MISSING MEDIA", "file": "missing-media.ccproj.json",
                          "savedAt": "2026-01-04T03:04:05.000Z"})
            (projects / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")

            page.reload(wait_until="load")
            wait_home(page)
            page.wait_for_timeout(800)
            card(page, "missing-media").click()
            wait_editor(page)
            page.wait_for_function(
                "() => document.getElementById('statusBar').textContent.includes('MISSING FROM DISK')",
                timeout=15000,
            )
            assert page.evaluate("document.getElementById('projectHome').hidden === true")
            print("PASS missing media is reported without breaking the editor")

            assert not console_errors, console_errors
            page.screenshot(path=str(SHOTS / "project-home-final.png"))
            browser.close()
    finally:
        stop_server(server)

print("PASS project home")
