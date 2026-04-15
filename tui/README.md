# Clip.A.Canvas TUI

An interactive terminal UI for Clip.A.Canvas — the HTML-to-video renderer.

![layout preview]

## Features

- **Split-pane layout** — code editor on the left, render status on the right
- **Live rendering** — paste HTML/CSS/JS and export to MP4 without leaving the terminal
- **Resolution & bitrate controls** — choose from common aspect ratios
- **Render estimate + live activity** — see a wall-clock estimate, elapsed time, and a small render animation while export runs
- **Keyboard shortcuts** — full keyboard-driven workflow
- **Built with Textual** — modern, fast, and pretty

## Installation

```bash
pip install clipacanvas-tui
# or with uv (recommended on Windows)
uv tool install clipacanvas-tui
```

### Requirements

- Python 3.10+
- FFmpeg (system-wide, or set `CLIPACANVAS_FFMPEG_EXE`)
- Playwright Chromium: `python -m playwright install chromium`

## Usage

```bash
clippp
# or
python -m clipacanvas_tui.app
```

The TUI opens immediately in your terminal.

For large HTML that triggers terminal paste warnings, load from a file, stdin, or
the OS clipboard instead of terminal paste:

```bash
clipacanvas-tui --clipboard --preview
clipacanvas-tui path/to/snippet.html --preview
cat snippet.html | clipacanvas-tui - --preview
```

Use the `Clip` selector to switch between `Auto` and `Custom`. In `Custom`,
enter seconds in the `Duration` field. Typing a duration automatically switches
the TUI to `Custom` mode. The hard cap is `60` seconds.

Use `Output Path` in the status pane to choose where rendered videos go.
Enter either:
- a target `.mp4` file path
- a folder path, which will receive a timestamped MP4 file

The TUI now encodes to a temporary MP4 first and then moves it to your chosen
destination. If Windows blocks the selected folder, the TUI stops before render
starts and tells you how to fix the destination instead of silently saving
somewhere else.

If you want direct saves into protected folders such as `Videos` or `Documents`
on Windows, press `F7` in the TUI. This opens an elevated PowerShell prompt
that adds the active Clip.A.Canvas runtime to Microsoft Defender's
Controlled Folder Access allow-list.

On Windows machines with Controlled Folder Access enabled, direct saves to
protected folders such as `Documents` or `Videos` may be blocked unless the
active Python interpreter or packaged app is explicitly allowed in Windows
Security.

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+R` | Start render |
| `Ctrl+P` | Open live preview in browser |
| `Ctrl+V` | Paste code from local clipboard |
| `F6` | Load the entire editor from the OS clipboard |
| `F7` | Open Windows protected-folder save setup |
| `Ctrl+Y` | Hidden compatibility alias for clipboard load |
| `Ctrl+O` | Open HTML file |
| `Ctrl+S` | Save code to file |
| `Ctrl+K` | Clear all code in the editor |
| `Ctrl+L` | Legacy clear shortcut |
| `Ctrl+Q` | Quit |

## Layout

```
┌─────────────────────────────────────────────────────┐
│ Resolution: [540x960▾]  Bitrate: [5M▾]  [▶ Render] │
├──────────────────────────┬──────────────────────────┤
│ CODE                      │ RENDER STATUS           │
│ <!DOCTYPE html>...        │ Output: —               │
│                          │ Resolution: 540x960      │
│                          │ Bitrate: 5M             │
│                          │ Status: Ready           │
│                          │ [=========>    ] 75%     │
│                          │ Rendered 3.45s | 207 fr │
├──────────────────────────┴──────────────────────────┤
│ Ctrl+R: Render  ·  Ctrl+O: Open  ·  Ctrl+S: Save  │
└─────────────────────────────────────────────────────┘
```

## Configuration

Same environment variables as the main app:

| Variable | Default | Description |
|---|---|---|
| `CLIPACANVAS_FFMPEG_EXE` | auto | FFmpeg path |
| `CLIPACANVAS_BROWSERS_PATH` | auto | Playwright browsers |
| `CLIPACANVAS_MAX_DURATION` | `12` | Max render seconds |

## Architecture

```
tui/src/clipacanvas_tui/
├── __init__.py
├── app.py              # Textual App + bindings
└── screens/
    └── editor.py       # Main editor screen (split pane)
```

The TUI calls `playwright_render.render_payload()` directly in a background
worker thread — the same rendering engine used by the desktop and MCP
interfaces.

## License

MIT
