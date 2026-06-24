#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PYTHON="/opt/miniconda3/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

cd "$PROJECT_DIR"

echo "Rebuilding macOS Vision OCR helper..."
"$PYTHON" - <<'PY'
from pdf_renamer.health import rebuild_vision_helper

error = rebuild_vision_helper()
if error:
    print(f"FAILED: {error}")
    raise SystemExit(1)

print("OK: Vision OCR helper is ready.")
PY

echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
