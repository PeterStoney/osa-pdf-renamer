#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
PYTHON="/opt/miniconda3/bin/python"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3)"
fi

cd "$PROJECT_DIR"

echo "Building OSA PDF Renamer.app..."
echo

if ! "$PYTHON" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller is not installed in:"
  echo "  $PYTHON"
  echo
  echo "Install it on this build machine with:"
  echo "  $PYTHON -m pip install pyinstaller"
  echo
  echo "Coworker machines will not need Python or PyInstaller after the app is built."
  echo
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

if [[ ! -f helpers/vision_ocr.swift ]]; then
  echo "Missing helpers/vision_ocr.swift"
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

if [[ ! -x /usr/bin/xcrun ]]; then
  echo "xcrun is missing. Install Xcode Command Line Tools first."
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

echo "Compiling Vision OCR helper..."
/usr/bin/xcrun swiftc -O helpers/vision_ocr.swift -o vision_ocr
chmod +x vision_ocr

echo "Running PyInstaller..."
"$PYTHON" -m PyInstaller --noconfirm "packaging/OSA PDF Renamer.spec"

echo
echo "Built:"
echo "  $PROJECT_DIR/dist/OSA PDF Renamer.app"
echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
