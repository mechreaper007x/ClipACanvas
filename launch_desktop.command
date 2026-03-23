#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
export CODE2VIDEO_NO_BROWSER=1
python3 desktop_app.py
