#!/bin/bash

# Start the SSE server in the background
clipmcp-sse &
SSE_PID=$!

# Wait for SSE server to start
echo "[start.sh] Waiting for SSE server to start on port 7860..."
for i in {1..30}; do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/health')" &>/dev/null; then
        echo "[start.sh] SSE server is healthy!"
        break
    fi
    sleep 1
done

# Check if dotMCP environment secrets are set
if [ -n "$DOTMCP_KEY" ] && [ -n "$DOTMCP_SERVER_ID" ]; then
    echo "[start.sh] dotMCP secrets detected. Setting up tunnel..."
    
    # Dynamically generate tunnel.yaml inside the container
    cat <<EOF > /tmp/tunnel.yaml
key: "$DOTMCP_KEY"
servers:
  - id: "$DOTMCP_SERVER_ID"
    command: "supergateway"
    args:
      - "--sse"
      - "http://localhost:7860/sse"
      - "--logLevel"
      - "none"
EOF

    # Start the dotMCP tunnel CLI
    echo "[start.sh] Starting dotMCP tunnel..."
    dotmcp-tunnel -c /tmp/tunnel.yaml &
    TUNNEL_PID=$!
else
    echo "[start.sh] dotMCP secrets (DOTMCP_KEY/DOTMCP_SERVER_ID) not detected. Running SSE server only."
fi

# Keep container running and wait for background processes
wait $SSE_PID
