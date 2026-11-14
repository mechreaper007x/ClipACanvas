"""Chat sessions are scoped per project and legacy chats bind to the last project."""
import json
import os
import sqlite3
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(r"C:\Users\Savyasachi Mishra\Desktop\clipacanvas")
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

appdata = Path(tempfile.mkdtemp(prefix="cc-chats-"))
projects = appdata / "projects"
projects.mkdir(parents=True)
(projects / "session.json").write_text(json.dumps({
    "projectId": "film-a", "name": "FILM A", "savedAt": "2026-01-01T00:00:00.000Z"
}), encoding="utf-8")

conn = sqlite3.connect(str(appdata / "chatlog.db"))
conn.executescript("""
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL DEFAULT '',
    created_at INTEGER NOT NULL DEFAULT 0,
    updated_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    model_meta TEXT,
    note TEXT,
    created_at INTEGER NOT NULL DEFAULT 0
);
""")
conn.execute("INSERT INTO sessions (id, title, created_at, updated_at) VALUES ('legacy-1', 'Old film chat', 1000, 2000)")
conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES ('legacy-1', 'user', 'hello old film', 1000)")
conn.commit()
conn.close()

os.environ["CLIPACANVAS_KEYS_DIR"] = str(appdata)

from playwright.sync_api import sync_playwright
from serve import server_url, start_server, stop_server


def api(base, path, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def contents(payload):
    return [m["content"] for s in payload["sessions"] for m in s["messages"]]


server, thread = start_server()
base = server_url(server)
try:
    migrated = api(base, "/api/llm/chatlog?projectId=film-a")
    print("migrated:", contents(migrated))
    assert contents(migrated) == ["hello old film"], migrated
    assert api(base, "/api/llm/chatlog?projectId=film-b")["sessions"] == []
    assert len(api(base, "/api/llm/chatlog")["sessions"]) == 1

    api(base, "/api/llm/chatlog", {"projectId": "film-b", "sessions": [{
        "id": "beta-seed", "title": "B seed", "createdAt": 1, "updatedAt": 2,
        "messages": [{"role": "user", "content": "seed for beta"}]
    }]})
    assert contents(api(base, "/api/llm/chatlog?projectId=film-a")) == ["hello old film"]
    assert contents(api(base, "/api/llm/chatlog?projectId=film-b")) == ["seed for beta"]

    api(base, "/api/llm/chatlog", {"projectId": "film-b", "sessions": [{
        "id": "beta-new", "title": "B new", "createdAt": 3, "updatedAt": 4,
        "messages": [{"role": "user", "content": "fresh beta"}]
    }]})
    assert contents(api(base, "/api/llm/chatlog?projectId=film-b")) == ["fresh beta"]
    assert contents(api(base, "/api/llm/chatlog?projectId=film-a")) == ["hello old film"]

    api(base, "/api/llm/chatlog", {"projectId": "film-b", "sessions": []})
    assert contents(api(base, "/api/llm/chatlog?projectId=film-b")) == ["fresh beta"], "empty scoped save wiped chats"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1480, "height": 960})
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto(f"{base}/clipacanvas.html", wait_until="load")
        page.wait_for_function("() => typeof timelineState !== 'undefined' && typeof chatState === 'object'", timeout=30000)

        first = page.evaluate("""async () => {
            setChatProjectScope('film-a');
            for (let i = 0; i < 60 && !chatLogReady; i += 1) await new Promise(r => setTimeout(r, 100));
            const loaded = { scope: chatProjectScope, sessions: chatState.sessions.map(s => s.title) };
            addChatMessage('user', 'alpha project note');
            await new Promise(r => setTimeout(r, 1500));
            return loaded;
        }""")
        print("film-a load:", first)
        assert first["scope"] == "film-a", first
        assert first["sessions"] == ["Old film chat"], first

        second = page.evaluate("""async () => {
            setChatProjectScope('film-b');
            for (let i = 0; i < 60 && !chatLogReady; i += 1) await new Promise(r => setTimeout(r, 100));
            const loaded = { scope: chatProjectScope, sessions: chatState.sessions.map(s => s.title) };
            addChatMessage('user', 'beta project note');
            await new Promise(r => setTimeout(r, 1500));
            return loaded;
        }""")
        print("film-b load:", second)
        assert second["scope"] == "film-b", second
        assert second["sessions"] == ["B new"], second

        back = page.evaluate("""async () => {
            setChatProjectScope('film-a');
            for (let i = 0; i < 60 && !chatLogReady; i += 1) await new Promise(r => setTimeout(r, 100));
            renderChatHistory();
            return { sessions: chatState.sessions.map(s => ({ title: s.title, messages: s.messages.map(m => m.content) })),
                     active: localStorage.getItem('clipacanvas.chatActive.film-a'),
                     history: [...document.querySelectorAll('#chatHistoryList .chat-history-title')].map(el => el.textContent),
                     scopeLabel: document.getElementById('chatScopeLabel').textContent };
        }""")
        print("film-a again:", back)
        texts = [m for s in back["sessions"] for m in s["messages"]]
        assert "alpha project note" in texts, back
        assert "beta project note" not in texts, back
        assert back["active"], back
        assert back["history"] == ["Old film chat"], back
        assert "THIS PROJECT" in back["scopeLabel"], back
        assert not errors, errors
        browser.close()

    assert "alpha project note" in contents(api(base, "/api/llm/chatlog?projectId=film-a"))
    assert "beta project note" in contents(api(base, "/api/llm/chatlog?projectId=film-b"))
finally:
    stop_server(server)
print("PASS project chats")
