---
title: Clip A Canvas MCP Server
emoji: 🎬
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: "Render HTML/CSS/JS animations to MP4 via MCP (SSE)"
---

# 🎬 Clip.A.Canvas — MCP Server (SSE)

**Clip.A.Canvas** is a Model Context Protocol (MCP) server that lets AI
assistants render HTML / CSS / JavaScript animations to MP4 video using
Playwright (Chromium) and FFmpeg.

This Space exposes the server over **Server-Sent Events (SSE)** so it can be
consumed by any SSE-capable MCP client without installing anything locally.

## Connect

Point your MCP client at this Space's `/sse` endpoint:

```
https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse
```

### Claude Desktop (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "clipacanvas": {
      "url": "https://mechreaper007x-clip-a-canvas-mcp.hf.space/sse"
    }
  }
}
```

### Other clients

Any MCP client supporting SSE transport can connect — just use the URL above.

## Tools exposed

| Tool | Description |
|------|-------------|
| `render_video` | Render a full HTML document (CSS/JS animations) to an MP4, returned as base64 |

## Endpoints

| Path | Method | Purpose |
|------|--------|---------|
| `/` | GET | Info page |
| `/sse` | GET | MCP SSE stream |
| `/messages/` | POST | JSON-RPC message channel |
| `/health` | GET | Health check (`{"status":"ok"}`) |

## Source

[github.com/mechreaper007x/ClipACanvas](https://github.com/mechreaper007x/ClipACanvas)
