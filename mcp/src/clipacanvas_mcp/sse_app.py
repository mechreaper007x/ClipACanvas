#!/usr/bin/env python3
"""
Clip.A.Canvas MCP Server — SSE Transport (Cloud Mode)

Runs a Starlette ASGI application that exposes the same MCP tools over
Server-Sent Events (SSE). Designed for deployment on Hugging Face Spaces
(Docker SDK) or any cloud container host.

Usage:
    pip install "clipacanvas-mcp[sse]"
    clipmcp-sse                        # listens on 0.0.0.0:7860
    clipmcp-sse --host 0.0.0.0 --port 8080

Environment variables:
    HOST   – bind host (default: 0.0.0.0)
    PORT   – bind port (default: 7860, HF Spaces convention)
"""

from __future__ import annotations

import asyncio
import os

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse
from starlette.routing import Mount, Route

from mcp.server.sse import SseServerTransport

# Re-use the same MCP Server instance defined in server.py
from .server import server, APP_NAME, APP_VERSION

# ---------------------------------------------------------------------------
# SSE transport
# ---------------------------------------------------------------------------

sse = SseServerTransport("/messages/")


async def handle_sse(scope, receive, send):
    """Upgrade the HTTP request to an SSE stream and run the MCP session."""
    async with sse.connect_sse(scope, receive, send) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def handle_messages(scope, receive, send):
    """Accept POSTed JSON-RPC messages from the SSE client."""
    await sse.handle_post_message(scope, receive, send)


# ---------------------------------------------------------------------------
# Health / info endpoints
# ---------------------------------------------------------------------------

async def health(request: Request):
    return JSONResponse({"status": "ok", "server": APP_NAME, "version": APP_VERSION})


async def homepage(request: Request):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{APP_NAME} MCP Server</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 680px; margin: 60px auto; padding: 0 20px; }}
    code {{ background: #f3f4f6; padding: 2px 6px; border-radius: 4px; font-size: .9em; }}
    a {{ color: #2563eb; }}
  </style>
</head>
<body>
  <h1>🎬 {APP_NAME} v{APP_VERSION}</h1>
  <p>This is the <strong>Clip.A.Canvas MCP Server</strong> running in cloud mode over SSE.</p>
  <h2>Connect</h2>
  <p>Point your MCP client at the SSE endpoint:</p>
  <pre><code>GET /sse</code></pre>
  <h2>Endpoints</h2>
  <ul>
    <li><code>GET /sse</code> — SSE stream (MCP transport)</li>
    <li><code>POST /messages/</code> — JSON-RPC message channel</li>
    <li><code>GET /health</code> — health check</li>
  </ul>
  <p><a href="https://github.com/mechreaper007x/ClipACanvas">GitHub ↗</a></p>
</body>
</html>"""
    return HTMLResponse(html)


# ---------------------------------------------------------------------------
# Starlette application
# ---------------------------------------------------------------------------

app = Starlette(
    routes=[
        Route("/", homepage),
        Route("/health", health),
        Route("/sse", handle_sse),
        Mount("/messages/", app=handle_messages),
    ]
)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "7860"))

    import argparse
    parser = argparse.ArgumentParser(description="Clip.A.Canvas MCP SSE Server")
    parser.add_argument("--host", default=host)
    parser.add_argument("--port", type=int, default=port)
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
