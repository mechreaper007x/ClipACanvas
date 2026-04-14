"""MCP tool definitions and handlers for Clip.A.Canvas rendering."""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path
from typing import Any

from mcp.types import Tool, TextContent

from .config import get_config


# ---------------------------------------------------------------------------
# Tool schema
# ---------------------------------------------------------------------------

RENDER_VIDEO_TOOL = Tool(
    name="render_video",
    description=(
        "Render HTML, CSS, and JavaScript code to an MP4 video using "
        "Chromium (headless) and FFmpeg. Supports CSS animations, WAAPI, "
        "SVG, and canvas animations. Returns the video as base64-encoded MP4."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Complete HTML document including DOCTYPE, <html>, <head>, <body>, and any inline CSS/JS.",
            },
            "width": {
                "type": "integer",
                "description": "Video width in pixels (default: 540).",
                "default": 540,
            },
            "height": {
                "type": "integer",
                "description": "Video height in pixels (default: 960).",
                "default": 960,
            },
            "bitrate": {
                "type": "string",
                "description": "FFmpeg bitrate (default: '5M'). Examples: '2M', '10M'.",
                "default": "5M",
            },
            "frame_rate": {
                "type": "integer",
                "description": "Frame rate for capture and encoding (default: 60).",
                "default": 60,
            },
            "max_duration": {
                "type": "number",
                "description": "Maximum render duration in seconds (default: 12).",
                "default": 12.0,
            },
            "min_duration": {
                "type": "number",
                "description": "Minimum render duration in seconds (default: 0.35).",
                "default": 0.35,
            },
        },
        "required": ["code"],
    },
)

RENDER_VIDEO_TO_FILE_TOOL = Tool(
    name="render_video_to_file",
    description=(
        "Same as render_video but saves the resulting MP4 directly to a file "
        "path on disk instead of returning base64. Useful for integrating with "
        "other tools or when dealing with large videos."
    ),
    inputSchema={
        "type": "object",
        "properties": {
            "code": {
                "type": "string",
                "description": "Complete HTML document.",
            },
            "output_path": {
                "type": "string",
                "description": "Absolute path where the MP4 file should be saved.",
            },
            "width": {
                "type": "integer",
                "description": "Video width in pixels (default: 540).",
                "default": 540,
            },
            "height": {
                "type": "integer",
                "description": "Video height in pixels (default: 960).",
                "default": 960,
            },
            "bitrate": {
                "type": "string",
                "description": "FFmpeg bitrate (default: '5M').",
                "default": "5M",
            },
            "frame_rate": {
                "type": "integer",
                "description": "Frame rate (default: 60).",
                "default": 60,
            },
            "max_duration": {
                "type": "number",
                "description": "Maximum render duration in seconds (default: 12).",
                "default": 12.0,
            },
        },
        "required": ["code", "output_path"],
    },
)

TOOLS = [RENDER_VIDEO_TOOL, RENDER_VIDEO_TO_FILE_TOOL]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------

_import_error: str | None = None
_playwright_render: Any = None


def _ensure_renderer():
    global _playwright_render, _import_error
    if _playwright_render is not None or _import_error:
        return

    try:
        try:
            from . import playwright_render as pr
        except ImportError:
            import sys

            repo_root = Path(__file__).resolve().parents[3]
            if str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            import playwright_render as pr

        _playwright_render = pr
    except Exception as exc:  # pragma: no cover
        _import_error = str(exc)
        _playwright_render = None


def handle_render_video(arguments: dict) -> TextContent:
    """Handle render_video tool call."""
    _ensure_renderer()
    if _import_error:
        raise RuntimeError(f"Failed to load playwright_render: {_import_error}")

    cfg = get_config()

    payload = {
        "code": arguments["code"],
        "width": arguments.get("width", cfg.default_width),
        "height": arguments.get("height", cfg.default_height),
        "bitrate": arguments.get("bitrate", cfg.default_bitrate),
        "frameRate": arguments.get("frame_rate", cfg.default_frame_rate),
        "maxDuration": arguments.get("max_duration", cfg.max_duration),
        "minDuration": arguments.get("min_duration", 0.35),
        "settleWindow": 0.45,
    }

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = _playwright_render.render_payload(
            payload, tmp_path, ffmpeg_exe=cfg.ffmpeg_exe
        )

        with open(tmp_path, "rb") as f:
            video_b64 = base64.b64encode(f.read()).decode("ascii")

        return TextContent(
            type="text",
            text=f"Video rendered successfully.\n"
            f"Duration: {result.get('duration', 0):.2f}s\n"
            f"Frames: {result.get('frameCount', 0)}\n"
            f"Content mode: {result.get('content_mode', 'unknown')}\n"
            f"Video (base64): {video_b64}",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def handle_render_video_to_file(arguments: dict) -> TextContent:
    """Handle render_video_to_file tool call."""
    _ensure_renderer()
    if _import_error:
        raise RuntimeError(f"Failed to load playwright_render: {_import_error}")

    cfg = get_config()
    output_path = Path(arguments["output_path"])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "code": arguments["code"],
        "width": arguments.get("width", cfg.default_width),
        "height": arguments.get("height", cfg.default_height),
        "bitrate": arguments.get("bitrate", cfg.default_bitrate),
        "frameRate": arguments.get("frame_rate", cfg.default_frame_rate),
        "maxDuration": arguments.get("max_duration", cfg.max_duration),
        "minDuration": arguments.get("min_duration", 0.35),
        "settleWindow": 0.45,
    }

    result = _playwright_render.render_payload(
        payload, str(output_path), ffmpeg_exe=cfg.ffmpeg_exe
    )

    return TextContent(
        type="text",
        text=f"Video saved to: {output_path.resolve()}\n"
        f"Duration: {result.get('duration', 0):.2f}s\n"
        f"Frames: {result.get('frameCount', 0)}\n"
        f"Content mode: {result.get('content_mode', 'unknown')}",
    )


def handle_tool_call(name: str, arguments: dict) -> TextContent:
    if name == "render_video":
        return handle_render_video(arguments)
    elif name == "render_video_to_file":
        return handle_render_video_to_file(arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")
