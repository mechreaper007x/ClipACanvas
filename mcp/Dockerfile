# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
#  Clip.A.Canvas — MCP Server (SSE mode)
#  Hugging Face Spaces — Docker SDK  (port 7860)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System packages ──────────────────────────────────────────────────────────
# FFmpeg + Chromium runtime libs needed by Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
        libx11-6 libx11-xcb1 libxcb1 libxext6 \
        ca-certificates fonts-liberation wget \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir ".[sse]"

# ── Playwright browsers ───────────────────────────────────────────────────────
RUN playwright install chromium --with-deps

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
