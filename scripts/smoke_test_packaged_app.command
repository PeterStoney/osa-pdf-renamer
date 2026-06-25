#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PYTHON="/opt/miniconda3/envs/osa-pdf-renamer-build/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="/opt/miniconda3/bin/python"
fi

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

cd "$PROJECT_DIR"

echo "Running packaged app smoke test..."
echo
"$PYTHON" tests/smoke_packaged_app.py

echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
