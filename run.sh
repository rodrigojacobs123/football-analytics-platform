#!/bin/bash
set -e
# Resolve project directory from the script's own location — works even when
# the shell's cwd is stale or unavailable (getcwd failure).
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"
exec /usr/local/bin/python3 -m streamlit run app.py \
  --server.port "${PORT:-8501}" \
  --server.headless true
