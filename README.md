# Clip.A.Canvas

<p align="center">
  <img src="logo_neon_preview-removebg-preview.png" alt="Clip.A.Canvas logo" width="720">
</p>

<!-- description:start -->
**Clip.A.Canvas** transforms HTML/CSS/JS animations into MP4 videos — entirely local or hosted in the cloud. Powered by Chromium + FFmpeg for high-quality, browser-accurate rendering. Perfect for AI agents generating video content, demos, or visual explanations on-the-fly.
<!-- description:end -->

**Clip.A.Canvas** is a local and remote browser-motion-to-video toolkit.

It includes:
- **Desktop App**: Paste, preview, and export animations locally with a pywebview UI.
- **MCP Server**: Exposes HTML-to-video rendering tools to Antigravity, Gemini, Codex, Claude Code, and other AI clients.
- **Terminal UI (TUI)**: Keyboard-first command-line client for code-first rendering.

- **Website**: `https://clipacanvas.vercel.app`
- **GitHub**: `https://github.com/mechreaper007x/ClipACanvas`
- **Releases**: `https://github.com/mechreaper007x/ClipACanvas/releases/tag/v1.0.0`
- **Cloud MCP (SSE)**: `https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse`

---

## 🎬 MCP Server (Model Context Protocol)

Expose `render_video` and `render_video_to_file` tools to your AI assistant.

### 1. Cloud-Hosted (Zero Resource Usage)
We host a public instance of the MCP server on Hugging Face Spaces using Server-Sent Events (SSE). Point your client configuration directly to our cloud endpoint:

**Claude Desktop Configuration (`claude_desktop_config.json`):**
```json
{
  "mcpServers": {
    "clipacanvas": {
      "url": "https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse"
    }
  }
}
```

### 2. Local Execution (Standard PyPI)
If you prefer running the server locally on your machine:
```bash
# Run locally with uvx
uvx --from clipacanvas-mcp clipmcp

# Or install via pip
pip install clipacanvas-mcp
```

**Claude Desktop Configuration for Local Server:**
```json
{
  "mcpServers": {
    "clipacanvas": {
      "command": "uvx",
      "args": ["--from", "clipacanvas-mcp", "clipmcp"]
    }
  }
}
```

---

## 💻 Terminal UI (TUI)

A keyboard-first CLI tool for local render pipelines.

### Install from PyPI:
```bash
# Using pipx (recommended)
pipx install clipacanvas-tui

# Using uv
uv tool install clipacanvas-tui
```

### Usage:
Run either command (`clipacanvas-tui` or `clippp`):
```bash
clipacanvas-tui --clipboard --preview
# or
clippp --clipboard --preview
```

---

## 🖥️ Desktop App

A visual UI for editing, previewing, and rendering HTML code to MP4.

### Install Dependencies:
```bash
git clone https://github.com/mechreaper007x/ClipACanvas.git
cd ClipACanvas
pip install -r requirements.txt
pip install -r desktop_requirements.txt
npm install
python -m playwright install chromium
```

### Run the App:
* **Windows**: Run `launch_desktop.bat` or `python desktop_app.py`
* **macOS**: Run `./launch_desktop.command`

---

## 🏗️ Build Outputs & Packaged Releases

See [build_desktop.py](build_desktop.py) to package binaries:
- **Windows Portable EXE**: `python build_desktop.py` -> `dist/ClipACanvas.exe`
- **Windows Installer**: `python build_installer.py` -> `dist/ClipACanvas-Setup.exe`
- **macOS Bundle**: `python3 build_mac_app.py` -> `dist/ClipACanvas.app`

---

## 📄 License

MIT
