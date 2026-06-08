#!/usr/bin/env bash
# Launch the local dashboard. Run from anywhere.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # the "Job automation" dir
cd "$HERE"
python3 -m pip install -q fastapi uvicorn python-multipart 2>/dev/null || true
echo "Dashboard → http://localhost:8000   (Ctrl+C to stop)"
exec python3 -m uvicorn dashboard.app:app --reload --port 8000
