"""Opening a project must restore its newest autosave, never the stale library copy."""
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.environ["CLIPACANVAS_KEYS_DIR"] = tempfile.mkdtemp(prefix="cc-recovery-")

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server


def scene_clip(name, start):
    return {
        "id": f"clip-{name.lower().replace(' ', '-')}",
        "name": name, "code": "<!doctype html><html><body></body></html>",
        "duration": 4, "start": start, "track": 0, "explicitDuration": True,
        "type": "code", "assetId": "", "mediaUrl": "", "mediaName": "",
        "sourceIn": 0, "fit": "contain", "parentClipId": "", "audioTrack": ""
    }


def project_doc(name, clips, saved_at, project_id=""):
    doc = {
        "format": "clipacanvas-project", "version": 1, "savedAt": saved_at,
        "projectName": name,
        "timeline": {
            "clips": clips, "transitions": [], "audioTracks": [], "layers": 1,
            "playhead": 0, "assets": []
        }
    }
    if project_id:
        doc["projectId"] = project_id
    return doc


def api(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base + path, data=data,
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


server, thread = start_server()
base = server_url(server)
try:
    created = api(base, "/api/projects", {
        "name": "Recover Test",
        "project": project_doc("RECOVER TEST", [scene_clip("SCENE 01", 0)], "2026-01-01T00:00:00.000Z")
    })
    project_id = created["project"]["id"]
    autosave = project_doc("RECOVER TEST", [scene_clip(f"SCENE 0{i}", (i - 1) * 4) for i in range(1, 6)],
                           "2099-01-01T00:00:00.000Z", project_id)
    api(base, "/api/project", autosave)

    opened = api(base, f"/api/projects/open?id={project_id}")
    print("open with newer autosave:", opened["recovered"], len(opened["project"]["timeline"]["clips"]), "clips")
    assert opened["recovered"] is True, opened
    assert len(opened["project"]["timeline"]["clips"]) == 5, opened

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1664, "height": 916})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html?home=1", wait_until="load")
        card = page.locator(f'.home-card[data-project-id="{project_id}"]')
        card.wait_for(timeout=20000)
        assert card.locator(".home-badge.recover").count() == 1
        card.click()
        page.wait_for_function("() => timelineState.clips.length === 5", timeout=20000)
        names = page.evaluate("() => timelineState.clips.map(clip => clip.name)")
        print("opened in UI:", names)
        assert names == ["SCENE 01", "SCENE 02", "SCENE 03", "SCENE 04", "SCENE 05"], names
        status = page.locator("#statusBar").inner_text()
        assert "AUTOSAVE RESTORED" in status, status
        page.click("#boxAdd")
        page.wait_for_timeout(1600)
        stored = api(base, f"/api/projects/recover?id={project_id}")
        print("autosave after edit:", len(stored["project"]["timeline"]["clips"]), "clips")
        assert len(stored["project"]["timeline"]["clips"]) == 6, stored
        assert not errors, errors
        browser.close()

    older = api(base, "/api/projects", {
        "name": "Older Autosave",
        "project": project_doc("OLDER AUTOSAVE", [scene_clip("SCENE 01", 0), scene_clip("SCENE 02", 4)],
                               "2099-02-01T00:00:00.000Z")
    })
    older_id = older["project"]["id"]
    api(base, "/api/project", project_doc("OLDER AUTOSAVE", [scene_clip("STALE", 0)],
                                          "2000-01-01T00:00:00.000Z", older_id))
    opened = api(base, f"/api/projects/open?id={older_id}")
    print("open with older autosave:", opened["recovered"], len(opened["project"]["timeline"]["clips"]), "clips")
    assert opened["recovered"] is False, opened
    assert len(opened["project"]["timeline"]["clips"]) == 2, opened
finally:
    stop_server(server)
print("PASS project open recovery")
