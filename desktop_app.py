#!/usr/bin/env python3

import base64
import os
import sys
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
            file_types=("MP4 video (*.mp4)", "All files (*.*)"),
        )
        if not selected:
            return {"saved": False}

        target = selected[0] if isinstance(selected, (list, tuple)) else selected
        target_path = Path(target)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(base64.b64decode(base64_data))
        return {"saved": True, "path": str(target_path)}


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

    os.environ.setdefault("CODE2VIDEO_NO_BROWSER", "1")
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
    window = webview.create_window(
        "CODE2VIDEO",
        url,
        js_api=api,
        width=1480,
        height=960,
        min_size=(1100, 720),
        text_select=True,
    )

    try:
        window.events.closed += shutdown
    except Exception:
        pass

    try:
        webview.start(debug=os.environ.get("CODE2VIDEO_DEBUG") == "1")
    finally:
        shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
