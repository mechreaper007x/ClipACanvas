"""Local browser preview server for the Clip.A.Canvas TUI."""

from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


EMPTY_PREVIEW_DOC = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<style>
html, body {
  margin: 0;
  width: 100%;
  height: 100%;
  display: grid;
  place-items: center;
  background: radial-gradient(circle at top, #122033 0%, #060a12 58%, #020305 100%);
  color: #d8fff4;
  font: 500 18px/1.5 "Segoe UI", sans-serif;
}

.message {
  padding: 16px 20px;
  border: 1px solid rgba(170, 255, 230, 0.2);
  border-radius: 16px;
  background: rgba(6, 10, 18, 0.78);
}
</style>
</head>
<body>
  <div class="message">Edit HTML in Clip.A.Canvas TUI to see the preview update here.</div>
</body>
</html>"""


def build_preview_page() -> str:
    """Return the static browser shell that live-updates the iframe preview."""

    empty_doc = json.dumps(EMPTY_PREVIEW_DOC)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Clip.A.Canvas Live Preview</title>
<style>
html, body {{
  margin: 0;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #03050a;
  color: #d8fff4;
  font-family: "Segoe UI", sans-serif;
}}

body {{
  display: grid;
  grid-template-rows: auto 1fr;
}}

.topbar {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(170, 255, 230, 0.14);
  background: rgba(4, 8, 14, 0.94);
}}

.brand {{
  font-weight: 700;
  letter-spacing: 0.04em;
}}

.meta {{
  color: rgba(216, 255, 244, 0.72);
  font-size: 13px;
}}

iframe {{
  width: 100%;
  height: 100%;
  border: 0;
  background: #000;
}}
</style>
</head>
<body>
  <div class="topbar">
    <div class="brand">Clip.A.Canvas Live Preview</div>
    <div class="meta" id="meta">Waiting for editor updates…</div>
  </div>
  <iframe id="preview" title="Clip.A.Canvas Preview"></iframe>
  <script>
    const emptyDoc = {empty_doc};
    const frame = document.getElementById("preview");
    const meta = document.getElementById("meta");
    let currentVersion = -1;

    async function syncPreview() {{
      try {{
        const response = await fetch("/state", {{ cache: "no-store" }});
        if (!response.ok) throw new Error(`HTTP ${{response.status}}`);

        const data = await response.json();
        if (data.version !== currentVersion) {{
          currentVersion = data.version;
          frame.srcdoc = data.code || emptyDoc;
          meta.textContent = `Live preview connected · revision ${{data.version}}`;
        }}
      }} catch (error) {{
        meta.textContent = `Preview disconnected: ${{error.message}}`;
      }}
    }}

    syncPreview();
    window.setInterval(syncPreview, 350);
  </script>
</body>
</html>"""


class _PreviewState:
    def __init__(self, code: str) -> None:
        self._lock = threading.Lock()
        self._code = code
        self._version = 1

    def snapshot(self) -> dict[str, str | int]:
        with self._lock:
            return {"version": self._version, "code": self._code}

    def update(self, code: str) -> None:
        with self._lock:
            if code != self._code:
                self._code = code
                self._version += 1


class PreviewServer:
    """Tiny local HTTP server that exposes the current editor HTML to a browser."""

    def __init__(self, initial_code: str = "") -> None:
        self._state = _PreviewState(initial_code)
        self._server: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._server is not None:
            return

        state = self._state

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802 - stdlib HTTP handler naming
                if self.path in {"/", "/index.html"}:
                    body = build_preview_page().encode("utf-8")
                    self._respond(200, body, "text/html; charset=utf-8")
                    return

                if self.path == "/state":
                    body = json.dumps(state.snapshot()).encode("utf-8")
                    self._respond(200, body, "application/json; charset=utf-8")
                    return

                if self.path == "/health":
                    body = json.dumps({"ok": True}).encode("utf-8")
                    self._respond(200, body, "application/json; charset=utf-8")
                    return

                message = html.escape(self.path)
                body = f"Not found: {message}".encode("utf-8")
                self._respond(404, body, "text/plain; charset=utf-8")

            def log_message(self, format: str, *args) -> None:  # noqa: A003
                return

            def _respond(self, status: int, body: bytes, content_type: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
                self.end_headers()
                self.wfile.write(body)

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(
            target=self._server.serve_forever, name="clipacanvas-preview", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._server is None:
            return

        self._server.shutdown()
        self._server.server_close()
        if self._thread is not None:
            self._thread.join(timeout=1)
        self._server = None
        self._thread = None

    def update_code(self, code: str) -> None:
        self.start()
        self._state.update(code)

    @property
    def url(self) -> str:
        self.start()
        assert self._server is not None
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}/"
