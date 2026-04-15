# Clip.A.Canvas MCP Server

A universal MCP (Model Context Protocol) server that exposes Clip.A.Canvas HTML-to-video rendering as an MCP tool. Works with any STDIO-based MCP client.

## Features

- **Universal MCP tool** — `render_video` and `render_video_to_file` exposed via the MCP protocol
- **Works everywhere** — Claude Desktop, Codex, Gemini CLI, Qwen Coder, and any MCP-compatible AI coding tool
- **Local rendering** — no upload, no cloud; Chromium + FFmpeg run on your machine
- **Base64 or file output** — return video as base64 string or save directly to a path

## Installation

### One-command MCP install

After publishing to PyPI:

```bash
# Gemini CLI
gemini mcp add clipacanvas -- uvx clipacanvas-mcp

# Codex CLI
codex mcp add clipacanvas -- uvx clipacanvas-mcp

# Claude Code on Windows
claude mcp add -s user clipacanvas -- cmd /c uvx clipacanvas-mcp
```

### From PyPI

```bash
pip install clipacanvas-mcp
# or
uv tool install clipacanvas-mcp  # gives 'clipmcp' command
```

### From source (editable)

```bash
cd code2video/mcp
pip install -e .
```

`uvx` handles the Python package environment. On first render, the MCP package will also install Playwright Chromium automatically if it is missing.

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

## Usage in AI Coding Tools

### Claude Code

For this local repo checkout:

```bash
cd code2video/mcp
pip install -e .
claude mcp add -s local clipacanvas -- cmd /c python -m clipacanvas_mcp.server
```

The `cmd /c` wrapper is useful on Windows because Claude Code's MCP health check can fail to resolve the same Python command that works in an interactive PowerShell session.

### Claude Desktop

Add to your Claude Desktop config file:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "clipacanvas": {
      "command": "python",
      "args": ["-m", "clipacanvas_mcp.server"]
    }
  }
}
```

Then restart Claude Desktop. The `render_video` and `render_video_to_file` tools will appear in the tool list.

### Codex CLI

For this local repo checkout:

```bash
cd code2video/mcp
pip install -e .
codex mcp add clipacanvas -- python -m clipacanvas_mcp.server
```

### Gemini CLI (Google)

For this local repo checkout, install the server in editable mode first:

```bash
cd code2video/mcp
pip install -e .
gemini mcp add clipacanvas -- python -m clipacanvas_mcp.server
```

Use the `uvx` command only after `clipacanvas-mcp` is published to a package index and `uvx` is installed:

```bash
gemini mcp add clipacanvas -- uvx --from clipacanvas-mcp clipacanvas-mcp
```

### Qwen Coder (Alibaba)

Add to Qwen Coder's MCP configuration:

```json
{
  "mcpServers": {
    "clipacanvas": {
      "command": "uvx",
      "args": ["--from", "clipacanvas-mcp", "clipacanvas-mcp"]
    }
  }
}
```

### Any STDIO MCP Client

```bash
# Direct run
uvx --from clipacanvas-mcp clipacanvas-mcp

# Or after pip install
clipacanvas-mcp
```

## Testing the Server Manually

```bash
# Start the server
python -m clipacanvas_mcp.server

# Send initialize
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | clipacanvas-mcp

# List tools
echo '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}' | clipacanvas-mcp
```

## Requirements

- Python 3.10+
- FFmpeg (installed system-wide, via `imageio-ffmpeg`, or set `CLIPACANVAS_FFMPEG_EXE`)
- Playwright Chromium: installed automatically on first render if missing; run `python -m playwright install chromium` manually only if you want to preinstall it

## License

MIT
