---
name: clipacanvas-render
description: Use when the user asks Codex to render HTML, CSS, SVG, JavaScript, or canvas animation code to an MP4 video through Clip.A.Canvas.
---

# Clip.A.Canvas Render

Use the `clipacanvas` MCP server when the user wants browser animation code converted to MP4.

## Tools

- Use `render_video` when the user wants a video returned to the conversation.
- Use `render_video_to_file` when the user asks for a saved `.mp4` file or gives an output path.

## Defaults

- Width: `540`
- Height: `960`
- Bitrate: `5M`
- Frame rate: `60`
- Max duration: `12`

## Guidance

- Prefer `render_video_to_file` for large renders.
- Ask for an output path only when the user wants a saved file and did not provide one.
- Keep the input as a complete HTML document when possible.
- Do not upload snippets or rendered files to any external service.
