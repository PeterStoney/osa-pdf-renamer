#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
SOURCE_WORKFLOW="$PROJECT_DIR/packaging/quick_action/(DEV) Rename PDFs.workflow"
SERVICES_DIR="$HOME/Library/Services"
TARGET_WORKFLOW="$SERVICES_DIR/(DEV) Rename PDFs.workflow"
PYTHON="${OSA_PDF_RENAMER_DEV_PYTHON:-/opt/miniconda3/bin/python}"

echo "Installing Finder Quick Action: (DEV) Rename PDFs"
echo

if [[ ! -d "$SOURCE_WORKFLOW" ]]; then
  echo "Missing workflow template:"
  echo "  $SOURCE_WORKFLOW"
  echo
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="$(command -v python3 || true)"
fi

if [[ -z "${PYTHON:-}" || ! -x "$PYTHON" ]]; then
  echo "Warning: could not find a Python interpreter."
  echo "Set OSA_PDF_RENAMER_DEV_PYTHON before running this installer if needed."
  echo
fi

mkdir -p "$SERVICES_DIR"
rm -rf "$TARGET_WORKFLOW"
cp -R "$SOURCE_WORKFLOW" "$TARGET_WORKFLOW"

escaped_project_dir="${PROJECT_DIR//\\/\\\\}"
escaped_project_dir="${escaped_project_dir//&/\\&}"
/usr/bin/sed -i '' "s|__OSA_PDF_RENAMER_PROJECT_DIR__|$escaped_project_dir|g" \
  "$TARGET_WORKFLOW/Contents/document.wflow"

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
if [[ -x "$LSREGISTER" ]]; then
  "$LSREGISTER" -f "$TARGET_WORKFLOW" >/dev/null 2>&1 || true
fi

if [[ -x "/System/Library/CoreServices/pbs" ]]; then
  /System/Library/CoreServices/pbs -flush >/dev/null 2>&1 || true
fi

echo "Installed:"
echo "  $TARGET_WORKFLOW"
echo
echo "This dev Quick Action runs:"
echo "  $PROJECT_DIR/patient_pdf_renamer.py"
echo
echo "If it does not appear immediately in Finder:"
echo "  1. Open System Settings"
echo "  2. Keyboard > Keyboard Shortcuts > Services"
echo "  3. Enable (DEV) Rename PDFs"
echo
echo "Use it by selecting PDFs in Finder, right-clicking, then choosing Quick Actions > (DEV) Rename PDFs."
echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
