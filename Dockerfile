# ─────────────────────────────────────────────────────────────────────────────
#  Clip.A.Canvas — MCP Server (Stdio mode for Glama / General Docker build)
#
#  Uses Microsoft's official Playwright Python image.
# ─────────────────────────────────────────────────────────────────────────────

FROM mcr.microsoft.com/playwright/python:v1.52.0-noble

# Install FFmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy python packaging configuration and source files from the mcp directory
COPY mcp/pyproject.toml .
COPY mcp/README.md .
COPY mcp/src/ src/

# Install the package
RUN pip install --no-cache-dir .

# Non-root user (UID 1000 exists in playwright image)
USER 1000

# Set entry point to standard stdio mode
ENTRYPOINT ["clipmcp"]
