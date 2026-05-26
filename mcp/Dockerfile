# syntax=docker/dockerfile:1
# ─────────────────────────────────────────────────────────────────────────────
#  Clip.A.Canvas — MCP Server (SSE mode)
#  Hugging Face Spaces — Docker SDK
#
#  Port 7860 is the HF Spaces convention; the SSE server honours $PORT.
# ─────────────────────────────────────────────────────────────────────────────

# ---------- stage 1: dependency installer ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools
RUN pip install --no-cache-dir hatchling

# Copy only the files needed to resolve deps first (layer-cache friendly)
COPY pyproject.toml .
COPY src/ src/

# Install the package WITH the sse extra into /install
RUN pip install --no-cache-dir --prefix=/install ".[sse]"


# ---------- stage 2: Playwright + system deps ----------
FROM python:3.11-slim AS runtime

# System packages required by Playwright's Chromium and FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        # Chromium runtime libs (playwright installs its own binary)
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
        libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
        libgbm1 libasound2 libpango-1.0-0 libpangocairo-1.0-0 \
        libx11-6 libx11-xcb1 libxcb1 libxext6 \
        ca-certificates fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Copy installed Python packages from builder
COPY --from=builder /install /usr/local

# Copy source so the editable install resolves correctly
WORKDIR /app
COPY src/ src/

# Install Playwright browsers (Chromium only – minimal footprint)
RUN playwright install chromium --with-deps 2>/dev/null || \
    playwright install chromium

# Non-root user for safety
RUN useradd -m -u 1000 appuser
USER appuser

# HF Spaces exposes port 7860
EXPOSE 7860

# Health check (HF probes / Docker healthcheck)
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')"

ENV PORT=7860 \
    HOST=0.0.0.0 \
    PYTHONUNBUFFERED=1

CMD ["clipmcp-sse"]
