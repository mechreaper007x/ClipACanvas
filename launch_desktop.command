#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export CLIPACANVAS_NO_BROWSER=1
python3 desktop_app.py
