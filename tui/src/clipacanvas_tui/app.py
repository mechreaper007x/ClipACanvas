"""Main Textual application for Clip.A.Canvas TUI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Input, TextArea

from .clipboard import read_clipboard_text
from .screens.editor import EditorScreen


class ClipACanvasTUI(App):
    """Interactive terminal UI for Clip.A.Canvas."""

    TITLE = "Clip.A.Canvas TUI"
    SUB_TITLE = "HTML → MP4 Renderer"

    BINDINGS = [
        Binding("ctrl+r", "render", "Render", show=True),
        Binding("ctrl+p", "preview", "Preview", show=True),
        Binding("ctrl+v", "paste_code", "Paste", show=True),
        Binding("f6", "load_clipboard", "Clipboard", show=True),
        Binding("f7", "enable_protected_saves", "Fix Save", show=True),
        Binding("ctrl+y", "load_clipboard", "Clipboard", show=False),
        Binding("ctrl+o", "open_file", "Open", show=True),
        Binding("ctrl+s", "save_file", "Save", show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
        Binding("ctrl+k", "clear_editor", "Clear All", show=True),
        Binding("ctrl+l", "clear_editor", "Clear", show=False),
    ]

    def __init__(
        self, initial_code: str | None = None, auto_open_preview: bool = False
    ) -> None:
        super().__init__()
        self._path_prompt_mode: str | None = None
        self._initial_code = initial_code
        self._auto_open_preview = auto_open_preview

    def on_mount(self) -> None:
        self.push_screen(
            EditorScreen(
                initial_code=self._initial_code,
                auto_open_preview=self._auto_open_preview,
            )
        )

    def compose(self) -> ComposeResult:
        yield Footer()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_render(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_render"):
            screen.action_render()

    def action_clear_editor(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_clear_editor"):
            screen.action_clear_editor()

    def action_preview(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_preview"):
            screen.action_preview()

    def action_paste_code(self) -> None:
        editor = self.screen.query_one("#code-editor", TextArea)
        editor.focus()
        editor.action_paste()

    def action_load_clipboard(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_load_clipboard"):
            screen.action_load_clipboard()

    def action_enable_protected_saves(self) -> None:
        screen = self.screen
        if hasattr(screen, "action_enable_protected_saves"):
            screen.action_enable_protected_saves()

    def action_open_file(self) -> None:
        self._show_path_prompt("open", "Enter file path to open...")

    def action_save_file(self) -> None:
        self._show_path_prompt("save", "Enter file path to save...")

    @on(Input.Submitted, "#file-input")
    def on_file_input_submitted(self, event: Input.Submitted) -> None:
        path = event.value.strip()
        mode = self._path_prompt_mode
        event.input.remove()
        self._path_prompt_mode = None

        if not path:
            return

        screen = self.screen
        editor = screen.query_one("#code-editor", TextArea)

        try:
            if mode == "open":
                editor.text = Path(path).read_text(encoding="utf-8")
                self.notify(f"Opened {path}")
            elif mode == "save":
                file_path = Path(path)
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(editor.text, encoding="utf-8")
                self.notify(f"Saved to {path}")
        except Exception as exc:
            action = "open" if mode == "open" else "save"
            self.notify(f"Failed to {action} file: {exc}", severity="error")
        finally:
            editor.focus()

    def _show_path_prompt(self, mode: str, placeholder: str) -> None:
        existing = self.query("#file-input")
        if existing:
            try:
                existing.first().remove()
            except Exception:
                pass

        self._path_prompt_mode = mode
        input_widget = Input(placeholder=placeholder, id="file-input")
        self.mount(input_widget)
        input_widget.focus()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="clipacanvas-tui",
        description="Clip.A.Canvas terminal UI with browser live preview.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        help="HTML file to load on startup, or '-' to read HTML from stdin.",
    )
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Open the browser live preview automatically on launch.",
    )
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Load startup HTML directly from the local clipboard.",
    )
    args = parser.parse_args()

    initial_code: str | None = None
    if args.clipboard:
        try:
            initial_code = read_clipboard_text()
        except Exception as exc:
            print(f"Failed to load clipboard: {exc}", file=sys.stderr)
            return 1
    elif args.input:
        try:
            if args.input == "-":
                initial_code = sys.stdin.read()
            else:
                initial_code = Path(args.input).read_text(encoding="utf-8")
        except Exception as exc:
            print(f"Failed to load input: {exc}", file=sys.stderr)
            return 1

    app = ClipACanvasTUI(
        initial_code=initial_code,
        auto_open_preview=args.preview,
    )
    app.run()
    return 0
