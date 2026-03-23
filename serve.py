#!/usr/bin/env python3
"""
CODE2VIDEO Backend Assistant
- Serves the frontend
- Handles Playwright + FFmpeg video rendering
- Auto-opens the tool in your browser
"""

import os
import time
import json
import webbrowser
import subprocess
import sys
import tempfile
import threading
import platform
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ALLOWED_ORIGINS = [origin.strip() for origin in os.environ.get("CODE2VIDEO_CORS_ORIGIN", "*").split(",") if origin.strip()]


def resolve_app_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


APP_DIR = resolve_app_dir()
IS_WINDOWS = platform.system() == "Windows"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"


def resolve_ffmpeg_exe() -> str:
    env_ffmpeg = os.environ.get("FFMPEG_EXE")
    if env_ffmpeg:
        return env_ffmpeg

    bundled_ffmpeg = APP_DIR / "bin" / FFMPEG_NAME
    if bundled_ffmpeg.exists():
        return str(bundled_ffmpeg)

    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        print("ERROR: imageio-ffmpeg is required.")
        print("Please run: pip install imageio-ffmpeg")
        raise SystemExit(1)


FFMPEG_EXE = resolve_ffmpeg_exe()


class CODE2VIDEOServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

class CODE2VIDEOHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(APP_DIR), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        cors_origin = self._cors_origin()
        if cors_origin:
            self.send_header("Access-Control-Allow-Origin", cors_origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            if cors_origin != "*":
                self.send_header("Vary", "Origin")
        super().end_headers()

    def do_OPTIONS(self):
        if self._origin_forbidden():
            self.send_error(403, "Origin not allowed")
            return
        self.send_response(204)
        self.send_header("Access-Control-Max-Age", "86400")
        self.end_headers()

    def do_GET(self):
        try:
            if self.path == '/':
                self.send_response(301)
                self.send_header('Location', '/code2video.html')
                self.end_headers()
                return
            if self.path == '/api/config.js':
                return self._send_runtime_config()
            if self.path == '/health':
                return self._send_json({'ok': True})
            return super().do_GET()
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            print(f"  [SERVER] GET error: {exc}")
            self._safe_text_error('Backend request failed.', 500)

    def do_POST(self):
        try:
            if self._origin_forbidden():
                self.send_error(403, "Origin not allowed")
                return
            if self.path == '/render':
                self._handle_render()
            else:
                self.send_error(404)
        except (BrokenPipeError, ConnectionResetError):
            return
        except Exception as exc:
            print(f"  [SERVER] POST error: {exc}")
            self._safe_text_error('Backend render failed.', 500)

    def _handle_render(self):
        content_length = int(self.headers['Content-Length'])
        payload = json.loads(self.rfile.read(content_length).decode('utf-8'))
        node_renderer = APP_DIR / 'playwright_render.mjs'

        if not node_renderer.exists():
            node_renderer = None

        if node_renderer is None:
            try:
                import playwright_render  # noqa: F401
            except Exception:
                self._send_text_error('No Playwright renderer script is available.', 500)
                return

        if node_renderer is None and 'playwright_render' not in sys.modules:
            self._send_text_error('No Playwright renderer script is available.', 500)
            return

        with tempfile.TemporaryDirectory() as tmpdir:
            out_filepath = os.path.join(tmpdir, 'output.mp4')

            env = os.environ.copy()
            env['FFMPEG_EXE'] = resolve_ffmpeg_exe()
            result = None
            render_errors = []

            try:
                import playwright_render
                result_payload = playwright_render.render_payload(payload, out_filepath, ffmpeg_exe=env['FFMPEG_EXE'])
                result = subprocess.CompletedProcess(args=['python', 'playwright_render'], returncode=0, stderr=json.dumps(result_payload))
            except Exception as exc:
                render_errors.append(str(exc).strip() or 'Python renderer failed.')

            fallback_commands = []
            if node_renderer is not None:
                input_path = os.path.join(tmpdir, 'render-input.json')
                with open(input_path, 'w', encoding='utf-8') as f:
                    json.dump(payload, f)
                fallback_commands.append(['node', str(node_renderer), input_path, out_filepath])

            for cmd in fallback_commands:
                if result and result.returncode == 0 and os.path.exists(out_filepath):
                    break
                try:
                    result = subprocess.run(
                        cmd,
                        cwd=APP_DIR,
                        env=env,
                        capture_output=True,
                        text=True,
                        timeout=600
                    )
                except FileNotFoundError:
                    render_errors.append(f'Missing runtime for command: {" ".join(cmd[:2])}')
                    continue
                except subprocess.TimeoutExpired:
                    self._send_text_error('Playwright render timed out.', 504)
                    return

                if result.stderr.strip():
                    print(result.stderr.strip())

                if result.returncode == 0 and os.path.exists(out_filepath):
                    break

                render_errors.append(result.stderr.strip() or f'Renderer failed for command: {" ".join(cmd[:2])}')

            if not result or result.returncode != 0 or not os.path.exists(out_filepath):
                message = '\n'.join(err for err in render_errors if err) or 'Playwright rendering failed.'
                self._send_text_error(message, 500)
                return

            self._send_file(out_filepath)

    def _send_file(self, filepath):
        mime = 'video/mp4'
        filename = f'code2video_{int(time.time())}.mp4'

        with open(filepath, 'rb') as f:
            data = f.read()

        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Disposition', f'inline; filename="{filename}"')
        self.send_header('X-Render-Filename', filename)
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return
        print(f"  [SERVER] OK Sent temporary render: {filename}")

    def _send_json(self, payload, status=200):
        data = json.dumps(payload).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_text_error(self, message, status=500):
        data = message.encode('utf-8', errors='replace')
        self.send_response(status)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _safe_text_error(self, message, status=500):
        try:
            self._send_text_error(message, status)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _send_runtime_config(self):
        api_base = os.environ.get("CODE2VIDEO_API_BASE", "").rstrip("/")
        payload = f"window.CODE2VIDEO_API_BASE = {json.dumps(api_base)};\n".encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/javascript; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            return

    def _cors_origin(self):
        request_origin = self.headers.get("Origin")
        if "*" in ALLOWED_ORIGINS:
            return "*"
        if request_origin and request_origin in ALLOWED_ORIGINS:
            return request_origin
        return None

    def _origin_forbidden(self):
        request_origin = self.headers.get("Origin")
        return bool(request_origin and "*" not in ALLOWED_ORIGINS and request_origin not in ALLOWED_ORIGINS)

    def log_message(self, fmt, *args):
        if "200 -" in fmt % args: return 
        print(f"  {self.address_string()} -> {fmt % args}")


def build_server(host: str = "0.0.0.0", port: int = 3000) -> CODE2VIDEOServer:
    return CODE2VIDEOServer((host, port), CODE2VIDEOHandler)


def server_url(server: CODE2VIDEOServer, public_host: str | None = None) -> str:
    bound_host, bound_port = server.server_address[:2]
    host = public_host or bound_host
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{bound_port}"


def start_server(host: str = "127.0.0.1", port: int = 0) -> tuple[CODE2VIDEOServer, threading.Thread]:
    server = build_server(host=host, port=port)
    thread = threading.Thread(target=server.serve_forever, name="code2video-server", daemon=True)
    thread.start()
    return server, thread


def stop_server(server: CODE2VIDEOServer) -> None:
    server.shutdown()
    server.server_close()


def main() -> int:
    port = int(os.environ.get("PORT", "3000"))
    host = os.environ.get("HOST", "0.0.0.0")
    server = build_server(host=host, port=port)
    url = server_url(server)
    
    print(f"\n  CODE2VIDEO ENGINE ACTIVE (Backend FFmpeg Mode)")
    print(f"  ----------------------------------------------")
    print(f"  URL -> {url}")
    print(f"  Renders are streamed to the browser and discarded after response.")
    
    if os.environ.get("CODE2VIDEO_NO_BROWSER") != "1":
        webbrowser.open(url)
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
