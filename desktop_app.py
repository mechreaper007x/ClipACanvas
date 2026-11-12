#!/usr/bin/env python3

import base64
import os
import sys
import json
import platform
from pathlib import Path

from serve import server_url, start_server, stop_server

IS_WINDOWS = platform.system() == "Windows"
FFMPEG_NAME = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"

def _resource_candidates(relative_path: str) -> list[Path]:
    relative = Path(relative_path)
    candidates: list[Path] = []

    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / relative)

        executable_path = Path(sys.executable).resolve()
        contents_dir = executable_path.parent.parent
        candidates.extend([
            contents_dir / "Resources" / relative,
            contents_dir / "Frameworks" / relative,
            executable_path.parent / relative,
        ])

    candidates.append(Path(__file__).resolve().parent / relative)
    return candidates


def resolve_resource_path(relative_path: str) -> Path:
    """Get absolute path to resource, works for dev and packaged app bundles."""
    for candidate in _resource_candidates(relative_path):
        if candidate.exists():
            return candidate
    return _resource_candidates(relative_path)[0]


class DesktopApi:
    def save_video(self, filename: str, base64_data: str):
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        window = webview.windows[0] if getattr(webview, "windows", None) else None
        if window is None:
            raise RuntimeError("Desktop window is not ready.")

        selected = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=filename,
            file_types=(
                "Media files (*.mp4;*.webm;*.mov;*.gif)",
                "MP4 video (*.mp4)",
                "WebM video (*.webm)",
                "MOV video (*.mov)",
                "Animated GIF (*.gif)",
                "All files (*.*)",
            ),
        )
        if not selected:
            return {"saved": False}

        target = selected[0] if isinstance(selected, (list, tuple)) else selected
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(base64.b64decode(base64_data))
        return {"saved": True, "path": str(target_path)}

    def open_code_file(self):
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        window = webview.windows[0] if getattr(webview, "windows", None) else None
        if window is None:
            raise RuntimeError("Desktop window is not ready.")

        selected = window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("HTML files (*.html;*.htm)", "All files (*.*)"),
        )
        if not selected:
            return {"selected": False}

        target = selected[0] if isinstance(selected, (list, tuple)) else selected
        try:
            code = Path(target).read_text(encoding="utf-8")
        except Exception as exc:
            return {"selected": False, "error": str(exc)}

        return {"selected": True, "path": str(target), "code": code}

    def save_code_file(self, suggested_name: str, code: str):
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        window = webview.windows[0] if getattr(webview, "windows", None) else None
        if window is None:
            raise RuntimeError("Desktop window is not ready.")

        target_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_name or "clipacanvas_animation.html",
            file_types=("HTML files (*.html;*.htm)", "All files (*.*)"),
        )
        if not target_path:
            return {"saved": False}

        target = target_path[0] if isinstance(target_path, (list, tuple)) else target_path
        Path(target).write_text(code or "", encoding="utf-8")
        return {"saved": True, "path": str(target)}

    def save_project_file(self, suggested_name: str, content: str):
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        window = webview.windows[0] if getattr(webview, "windows", None) else None
        if window is None:
            raise RuntimeError("Desktop window is not ready.")

        target_path = window.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=suggested_name or "clipacanvas-project.ccproj.json",
            file_types=("Clip.A.Canvas project (*.json)", "All files (*.*)"),
        )
        if not target_path:
            return {"saved": False}

        target = target_path[0] if isinstance(target_path, (list, tuple)) else target_path
        Path(target).write_text(content or "", encoding="utf-8")
        return {"saved": True, "path": str(target)}

    def open_project_file(self):
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        window = webview.windows[0] if getattr(webview, "windows", None) else None
        if window is None:
            raise RuntimeError("Desktop window is not ready.")

        selected = window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Clip.A.Canvas project (*.json;*.ccproj.json)", "All files (*.*)"),
        )
        if not selected:
            return {"selected": False}

        target = selected[0] if isinstance(selected, (list, tuple)) else selected
        try:
            content = Path(target).read_text(encoding="utf-8")
        except Exception as exc:
            return {"selected": False, "error": str(exc)}
        return {"selected": True, "path": str(target), "content": content}

    def state_file_path(self):
        state_dir = Path(os.path.expanduser("~")) / ".clipacanvas"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / "desktop-state.json"

    def save_window_state(self, width, height):
        try:
            path = self.state_file_path()
            state = {}
            if path.exists():
                state = json.loads(path.read_text(encoding="utf-8"))
            state["width"] = int(width)
            state["height"] = int(height)
            path.write_text(json.dumps(state, indent=2), encoding="utf-8")
            return {"saved": True}
        except Exception as exc:
            return {"saved": False, "error": str(exc)}

    def load_window_state(self):
        try:
            path = self.state_file_path()
            if not path.exists():
                return {}
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def choose_audio_file(self):
        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        window = webview.windows[0] if getattr(webview, "windows", None) else None
        if window is None:
            raise RuntimeError("Desktop window is not ready.")

        selected = window.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=("Audio files (*.wav;*.mp3;*.aac;*.m4a)", "WAV (*.wav)", "MP3 (*.mp3)", "All files (*.*)"),
        )
        if not selected:
            return {"selected": False}

        target = selected[0] if isinstance(selected, (list, tuple)) else selected
        return {"selected": True, "path": str(target)}


def main() -> int:
    try:
        import webview
    except ImportError:
        print("pywebview is required for desktop mode.")
        print("Install it with: pip install -r desktop_requirements.txt")
        return 1

    # --- CROSS-PLATFORM PACKAGING LOGIC ---
    # Configure Playwright to use the bundled browser
    bundled_browsers = resolve_resource_path("bin/browsers")
    if bundled_browsers.exists():
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(bundled_browsers)
    
    # Configure FFmpeg to use the bundled binary
    bundled_ffmpeg = resolve_resource_path(f"bin/{FFMPEG_NAME}")
    if bundled_ffmpeg.exists():
        os.environ["FFMPEG_EXE"] = str(bundled_ffmpeg)
        # Ensure executable permission on Unix
        if not IS_WINDOWS:
            try:
                os.chmod(bundled_ffmpeg, 0o755)
            except Exception:
                pass
    # ---------------------------------------

    os.environ.setdefault("CLIPACANVAS_NO_BROWSER", "1")
    server, _thread = start_server(host="127.0.0.1", port=0)
    url = server_url(server, public_host="127.0.0.1")
    stopped = False

    def shutdown() -> None:
        nonlocal stopped
        if stopped:
            return
        stopped = True
        stop_server(server)

    api = DesktopApi()
    state = api.load_window_state()
    initial_width = int(state.get("width", 1480) or 1480)
    initial_height = int(state.get("height", 960) or 960)

    window = webview.create_window(
        "Clip.A.Canvas",
        f"{url}/clipacanvas.html",
        js_api=api,
        width=initial_width,
        height=initial_height,
        min_size=(1100, 720),
        text_select=True,
    )

    try:
        window.events.closed += shutdown
    except Exception:
        pass

    def on_window_ready() -> None:
        # Close the PyInstaller splash screen once the UI is up.
        try:
            import pyi_splash  # type: ignore[import-not-found]

            pyi_splash.close()
        except Exception:
            pass

    try:
        webview.start(
            debug=os.environ.get("CLIPACANVAS_DEBUG") == "1",
            func=on_window_ready,
        )
    finally:
        shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
