# Clip.A.Canvas Claude Desktop Extension

This folder builds the Claude Desktop MCPB package for Clip.A.Canvas.

The extension bundles the Clip.A.Canvas MCP server source and lets Claude Desktop launch it through the UV runtime. Python package dependencies are resolved by UV when the extension is installed.

## Build

```bash
npm install -g @anthropic-ai/mcpb
mcpb pack claude/desktop-extension dist/ClipACanvas-1.0.2.mcpb
```

## Test

Open `dist/ClipACanvas-1.0.2.mcpb` with Claude Desktop, then confirm the following tools appear:

- `render_video`
- `render_video_to_file`

## Claude Code

Claude Code users do not need this bundle. They can install the published MCP package directly:

```bash
claude mcp add -s user clipacanvas -- uvx clipacanvas-mcp
```
