#!/usr/bin/env python3
"""
Clip.A.Canvas MCP Server

A universal MCP server (STDIO transport) that exposes Clip.A.Canvas
rendering as MCP tools. Works with Claude Desktop, Codex, Gemini CLI,
Qwen Coder, and any STDIO-based MCP client.

Usage:
    pip install -e mcp/
    clipacanvas-mcp

Or via Python module:
    python -m clipacanvas_mcp.server
"""

from __future__ import annotations

import json
import os
import sys
import asyncio
import threading
from pathlib import Path
from typing import Any

# Ensure the src package is importable when installed as editable
_src_root = Path(__file__).resolve().parents[1] / "src"
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    Resource,
)

from .render_tool import TOOLS, handle_tool_call
from .config import get_config


# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

APP_NAME = "clipacanvas"
APP_VERSION = "1.0.0"

server = Server(APP_NAME)


# ---------------------------------------------------------------------------
# Server capabilities
# ---------------------------------------------------------------------------

@server.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    result = await asyncio.to_thread(handle_tool_call, name, arguments or {})
    return [result]


# ---------------------------------------------------------------------------
# Optional: config resources
# ---------------------------------------------------------------------------

@server.list_resources()
async def list_resources() -> list[Resource]:
    cfg = get_config()

    return [
        Resource(
            uri="config://clipacanvas/ffmpeg",
            name="FFmpeg Configuration",
            description="FFmpeg path and version info",
            mimeType="application/json",
        ),
        Resource(
            uri="config://clipacanvas/render-options",
            name="Render Options",
            description="Default render options",
            mimeType="application/json",
        ),
    ]


@server.read_resource()
async def read_resource(uri: str) -> str:
    cfg = get_config()

    if uri == "config://clipacanvas/ffmpeg":
        import subprocess

        try:
            result = subprocess.run(
                [cfg.ffmpeg_exe, "-version"],
                capture_output=True,
                text=True,
            )
            version = result.stdout.split("\n")[0]
        except Exception as e:
            version = f"error: {e}"

        return json.dumps(
            {"ffmpeg_exe": cfg.ffmpeg_exe, "version": version}, indent=2
        )

    elif uri == "config://clipacanvas/render-options":
        return json.dumps(
            {
                "default_width": cfg.default_width,
                "default_height": cfg.default_height,
                "default_bitrate": cfg.default_bitrate,
                "default_frame_rate": cfg.default_frame_rate,
                "max_duration": cfg.max_duration,
            },
            indent=2,
        )

    raise ValueError(f"Unknown resource: {uri}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        async def run():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(
                    read_stream,
                    write_stream,
                    server.create_initialization_options(),
                )

        asyncio.run(run())
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
