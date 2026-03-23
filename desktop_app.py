#!/usr/bin/env python3

import base64
import os
import sys
from pathlib import Path

from serve import server_url, start_server, stop_server


class DesktopApi:
    def __init__(self):
        self.window = None

    def bind_window(self, window) -> None:
        self.window = window

    def save_video(self, filename: str, base64_data: str):
        if self.window is None:
            raise RuntimeError("Desktop window is not ready.")

        try:
            import webview
        except ImportError as exc:
            raise RuntimeError("pywebview is not available.") from exc

        selected = self.window.create_file_dialog(
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
    api.bind_window(window)

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
