# ─────────────────────────────────────────────────────────────────────────────
#  Clip.A.Canvas — MCP Server (SSE mode)
#  Hugging Face Spaces — Docker SDK  (port 7860)
#
#  Uses Microsoft's official Playwright Python image — Chromium, all system
#  libs, and Python 3.11 are pre-installed and tested. No manual apt-get lists.
# ─────────────────────────────────────────────────────────────────────────────

FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

# ── FFmpeg (not bundled in playwright image) ──────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir ".[sse]"

# ── Non-root user ─────────────────────────────────────────────────────────────
RUN useradd -m -u 1000 appuser
USER appuser

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

ENV PORT=7860 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

CMD ["clipmcp-sse"]
