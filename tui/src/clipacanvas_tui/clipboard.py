"""Clipboard helpers for the Clip.A.Canvas TUI."""

from __future__ import annotations

import platform
import subprocess
from shutil import which


def _read_with_command(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None

    text = result.stdout
    if text:
        return text
    return None


def read_clipboard_text() -> str:
    """Read text directly from the local OS clipboard."""

    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.update()
        try:
            text = root.clipboard_get()
        finally:
            root.destroy()
        if text:
            return text
    except Exception:
        pass

    system = platform.system()

    if system == "Windows":
        text = _read_with_command(
            ["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"]
        )
        if text:
            return text

    elif system == "Darwin":
        text = _read_with_command(["pbpaste"])
        if text:
            return text

    else:
        if which("wl-paste"):
            text = _read_with_command(["wl-paste", "--no-newline"])
            if text:
                return text
        if which("xclip"):
            text = _read_with_command(["xclip", "-selection", "clipboard", "-o"])
            if text:
                return text
        if which("xsel"):
            text = _read_with_command(["xsel", "--clipboard", "--output"])
            if text:
                return text

    raise RuntimeError("Clipboard text is unavailable. Copy the HTML first, or load it from a file.")
