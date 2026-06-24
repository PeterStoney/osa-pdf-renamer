#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PYTHON="/opt/miniconda3/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

cd "$PROJECT_DIR"

echo "Running OSA PDF Renamer health check..."
echo
"$PYTHON" - <<'PY'
from pdf_renamer.config import OLLAMA_MODEL
from pdf_renamer.health import check_dependencies

errors = check_dependencies()
if errors:
    print("Health check failed:")
    for error in errors:
        print(f"- {error}")
    print()
    print("Fix the items above, then run this check again.")
    raise SystemExit(1)

print("OK: all required dependencies are available.")
print(f"OK: Ollama model is installed: {OLLAMA_MODEL}")
PY

echo
read -k 1 "?Press any key to close."

