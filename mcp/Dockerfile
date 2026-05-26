# ─────────────────────────────────────────────────────────────────────────────
#  Clip.A.Canvas — MCP Server (SSE mode)
#  Hugging Face Spaces — Docker SDK  (port 7860)
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim

# ── System packages ──────────────────────────────────────────────────────────
# Let playwright --with-deps handle all Chromium system libraries.
# We only pre-install ffmpeg and ca-certificates ourselves.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        ca-certificates \
        wget \
    && rm -rf /var/lib/apt/lists/*

# ── Python deps ───────────────────────────────────────────────────────────────
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir ".[sse]"

# ── Playwright browsers ───────────────────────────────────────────────────────
# --with-deps installs all required system libraries automatically
RUN playwright install --with-deps chromium

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
