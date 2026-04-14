# Clip.A.Canvas

<p align="center">
  <img src="logo_neon_preview-removebg-preview.png" alt="Clip.A.Canvas logo" width="720">
</p>

**Clip.A.Canvas** is a local browser-motion-to-video toolkit.

It includes:

- a desktop app for paste, preview, and MP4 export
- an MCP server for Gemini, Codex, and Claude Code
- a terminal TUI for code-first render workflows

- Website: `https://clipacanvas.vercel.app`
- GitHub: `https://github.com/mechreaper007x/ClipACanvas`
- Releases: `https://github.com/mechreaper007x/ClipACanvas/releases/tag/v1.0.0`

## What It Does

- Renders HTML/CSS/JS, SVG, and canvas animations into MP4.
- Uses Playwright + Chromium for browser-accurate capture.
- Encodes locally with FFmpeg.
- Runs as a desktop app through `pywebview`.
- Exposes the same render engine through an MCP server and a TUI.

## Desktop App

### Install Dependencies

```bash
git clone https://github.com/mechreaper007x/ClipACanvas.git
cd ClipACanvas
pip install -r requirements.txt
pip install -r desktop_requirements.txt
npm install
python -m playwright install chromium
```

### Run the App

On Windows:

```bash
launch_desktop.bat
```

Or directly:

```bash
python desktop_app.py
```

On macOS:

```bash
chmod +x launch_desktop.command
./launch_desktop.command
```

## MCP Install

### Direct install from GitHub

These commands do not require cloning the repo first. They install the MCP package from the `mcp/` subdirectory of this repository.

Gemini CLI:

```bash
gemini mcp add clipacanvas -- uvx --from "clipacanvas-mcp @ git+https://github.com/mechreaper007x/ClipACanvas.git#subdirectory=mcp" clipacanvas-mcp
```

Codex CLI:

```bash
codex mcp add clipacanvas -- uvx --from "clipacanvas-mcp @ git+https://github.com/mechreaper007x/ClipACanvas.git#subdirectory=mcp" clipacanvas-mcp
```

Claude Code on Windows:

```bash
claude mcp add -s user clipacanvas -- cmd /c uvx --from "clipacanvas-mcp @ git+https://github.com/mechreaper007x/ClipACanvas.git#subdirectory=mcp" clipacanvas-mcp
```

### Local editable install

Use this path if you are developing the MCP package locally:

```bash
cd mcp
pip install -e .
python -m clipacanvas_mcp.server
```

Notes:

- `uvx` handles the Python package environment for end users.
- The MCP package auto-installs Playwright Chromium on first render if it is missing.
- After a future PyPI publish, the install command shortens to `uvx --from clipacanvas-mcp clipacanvas-mcp`.

## TUI

The repo also includes a terminal UI package:

```bash
cd tui
pip install -e .
clipacanvas-tui
```

## Build Outputs

### Windows Portable EXE + ZIP

```bash
python build_desktop.py
```

Outputs:

- `dist/ClipACanvas.exe`
- `dist/ClipACanvas-windows.zip`

### Windows Installer

```bash
python build_installer.py
```

Output:

- `dist/ClipACanvas-Setup.exe`

### macOS App Bundle

Run this on macOS:

```bash
python3 build_mac_app.py
```

Outputs:

- `dist/ClipACanvas.app`
- `dist/ClipACanvas-macos.zip`

## Release Workflow

Build the distributables first, then generate release metadata:

```bash
python build_release_assets.py --version v1.0.0
```

This generates:

- `dist/SHA256SUMS.txt`
- `dist/RELEASE_NOTES.md`

Ship releases through GitHub Releases. Windows builds are currently unsigned, so SmartScreen or Defender reputation warnings can still appear on first run.

## Project Layout

- `clipacanvas.html`: main app UI
- `desktop_app.py`: desktop launcher
- `serve.py`: local backend and render endpoint
- `playwright_render.py`: Python renderer path used by the desktop app
- `playwright_render.mjs`: Node renderer fallback
- `mcp/`: standalone MCP package
- `tui/`: terminal UI package
- `build_desktop.py`: packaged desktop build
- `build_installer.py`: Windows installer build
- `build_mac_app.py`: macOS app build
- `website/`: Vercel site
- `tests/frontend_render_matrix.py`: frontend render regression suite

## Notes

- The portable Windows build is a single-file executable that unpacks bundled payloads at runtime.
- The installer is the simplest Windows distribution path for non-technical users.
- macOS packaging must be built on macOS.

## License

MIT.
