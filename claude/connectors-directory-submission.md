# Claude Submission Packet

## Product

- Name: Clip.A.Canvas
- Website: https://clipacanvas.vercel.app
- Documentation: https://clipacanvas.vercel.app/claude.html
- Privacy policy: https://clipacanvas.vercel.app/privacy.html
- Support: https://github.com/mechreaper007x/ClipACanvas/issues
- License: MIT

## Claude Desktop Extension

- Package source: `claude/desktop-extension`
- Release artifact: `dist/ClipACanvas-1.0.2.mcpb`
- Runtime: UV
- Python dependency: `clipacanvas-mcp==1.0.2`
- Tools:
  - `render_video`
  - `render_video_to_file`

## Claude Code

Recommended install command:

```bash
claude mcp add -s user clipacanvas -- uvx clipacanvas-mcp
```

Windows-safe command:

```bash
claude mcp add -s user clipacanvas -- cmd /c uvx clipacanvas-mcp
```

## Review Notes

Clip.A.Canvas is local-first. HTML, CSS, JavaScript, Chromium rendering, and FFmpeg encoding run on the user's machine through the local MCP server.

The `render_video_to_file` tool writes to the user-provided output path and can overwrite files. The tool is marked destructive in the MCP tool annotations.

## Remote Connector Status

The published package is currently a local STDIO MCP server. A hosted Claude Connector Directory listing for Claude.ai would require a separate public HTTPS MCP service and a hardened browser-rendering sandbox. That service is intentionally not bundled here because it would change the privacy and security model from local rendering to hosted rendering.
