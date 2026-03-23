#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This script must be run on macOS."
  exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required."
  exit 1
fi

echo "[*] Installing Python dependencies..."
python3 -m pip install -r requirements.txt
python3 -m pip install -r desktop_requirements.txt

echo "[*] Installing Chromium for Playwright..."
python3 -m playwright install chromium

echo "[*] Building macOS app..."
python3 build_mac_app.py

APP_PATH="dist/CODE2VIDEO.app"
ZIP_PATH="dist/CODE2VIDEO-macos.zip"

if [[ -d "$APP_PATH" ]]; then
  xattr -dr com.apple.quarantine "$APP_PATH" 2>/dev/null || true
fi

echo
echo "Build complete."
echo "App: $APP_PATH"
echo "Zip: $ZIP_PATH"
