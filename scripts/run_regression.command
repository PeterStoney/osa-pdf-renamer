#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PYTHON="/opt/miniconda3/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

cd "$PROJECT_DIR"

echo "Running privacy-safe PDF renamer regression tests with Ollama..."
echo
"$PYTHON" tests/run_regression.py
"$PYTHON" tests/test_update_check.py
"$PYTHON" tests/test_naming.py

echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
