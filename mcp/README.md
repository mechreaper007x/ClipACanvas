# Clip.A.Canvas MCP Server

A universal MCP (Model Context Protocol) server that exposes Clip.A.Canvas HTML-to-video rendering as an MCP tool. Works with Claude Desktop, ChatGPT, Gemini CLI, Claude Code, and any STDIO/HTTPS-based MCP client.

<!-- mcp-name: io.github.mechreaper007x/clipacanvas -->

## Features

- **Universal MCP tool** — `render_video` and `render_video_to_file` exposed via the MCP protocol
- **Works everywhere** — Claude Desktop, ChatGPT, Gemini CLI, Claude Code, and more
- **Local rendering** — no upload, no cloud; Chromium + FFmpeg run on your machine
- **Base64 or file output** — return video as base64 string or save directly to a path

## Installation

### One-command MCP install

```bash
# Gemini CLI
gemini mcp add clipacanvas -- uvx clipacanvas-mcp

# Claude Code
claude mcp add -s user clipacanvas -- cmd /c uvx clipacanvas-mcp
```

### From PyPI

```bash
pip install clipacanvas-mcp
# or
uv tool install clipacanvas-mcp  # gives 'clipacanvas-mcp' command
```

## Configuration

Environment variables (all optional):

| Variable | Default | Description |
|---|---|---|
| `CLIPACANVAS_FFMPEG_EXE` | auto-detect | Path to FFmpeg executable |
| `CLIPACANVAS_BROWSERS_PATH` | auto-detect | Path to Playwright browsers |
| `CLIPACANVAS_MAX_DURATION` | `12` | Max render duration in seconds |
| `CLIPACANVAS_DEFAULT_WIDTH` | `540` | Default video width |
| `CLIPACANVAS_DEFAULT_HEIGHT` | `960` | Default video height |
| `CLIPACANVAS_DEFAULT_BITRATE` | `5M` | Default FFmpeg bitrate |
| `CLIPACANVAS_DEFAULT_FRAME_RATE` | `60` | Default frame rate |

## MCP Tools

### `render_video`
*Read-only hint: No* | *Destructive hint: No*

Render HTML/CSS/JS to MP4, returned as base64.

**Arguments:**

```json
{
  "code": "<!DOCTYPE html><html>...</html>",
  "width": 540,
  "height": 960,
  "bitrate": "5M",
  "frame_rate": 60,
  "max_duration": 12
}
```

**Returns:** Text content with video metadata and base64-encoded MP4 data.

### `render_video_to_file`
*Read-only hint: No* | *Destructive hint: Yes (overwrites file)*

Same as above but saves the MP4 directly to `output_path`.

**Arguments:**

```json
{
  "code": "<!DOCTYPE html><html>...</html>",
  "output_path": "/absolute/path/to/video.mp4",
  "width": 540,
  "height": 960
}
```

## Usage in AI Clients

### Claude Desktop
Add to your `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "clipacanvas": {
      "command": "uvx",
      "args": ["clipacanvas-mcp"]
    }
  }
}
```

### ChatGPT (via Bridge)
To use this local tool with ChatGPT, you can use an MCP-to-HTTPS bridge (like `mcp-proxy`) or host it on a public URL. ChatGPT currently requires an HTTPS endpoint for official "App" integrations.

### Other Clients (Codex, Qwen Coder, etc.)
Since this is a standard STDIO-based server, it works with any client that supports MCP. Use `uvx clipacanvas-mcp` or `python -m clipacanvas_mcp.server` as the launch command.

## Privacy Policy

**Clip.A.Canvas** is a local-first application.
- **Data Collection**: No user data, code snippets, or rendered videos are ever uploaded to any server.
- **Processing**: All HTML/CSS/JS rendering happens inside a local Chromium instance on your machine.
- **Storage**: Rendered MP4 files are saved only to the directory you specify.
- **Third-party Services**: None.

## Requirements

- Python 3.10+
- FFmpeg (installed system-wide, via `imageio-ffmpeg`, or set `CLIPACANVAS_FFMPEG_EXE`)
- Playwright Chromium: installed automatically on first render if missing.

## License

MIT
