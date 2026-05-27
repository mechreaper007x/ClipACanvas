# ─────────────────────────────────────────────────────────────────────────────
#  Clip.A.Canvas — MCP Server (SSE mode)
#  Hugging Face Spaces — Docker SDK  (port 7860)
#
#  Uses Microsoft's official Playwright Python image — Chromium, all system
#  libs, and Python 3.11 are pre-installed and tested. No manual apt-get lists.
# ─────────────────────────────────────────────────────────────────────────────

FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

# ── FFmpeg, Node.js & Global tools (SSE + Tunnel) ─────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        nodejs \
        npm \
    && npm install -g @dotmcp/tunnel supergateway \
    && rm -rf /var/lib/apt/lists/*

# ── Application Build ─────────────────────────────────────────────────────────
WORKDIR /app
COPY pyproject.toml .
COPY README.md .
COPY src/ src/
COPY start.sh .

RUN chmod +x start.sh && pip install --no-cache-dir ".[sse]"

# ── Non-root user (UID 1000 already exists in playwright base image) ──────────
USER 1000

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

ENV PORT=7860 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

CMD ["./start.sh"]
