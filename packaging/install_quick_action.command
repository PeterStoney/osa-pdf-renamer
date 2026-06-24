#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
SOURCE_WORKFLOW="$PROJECT_DIR/packaging/quick_action/Rename OSA PDFs.workflow"
SERVICES_DIR="$HOME/Library/Services"
TARGET_WORKFLOW="$SERVICES_DIR/Rename OSA PDFs.workflow"

echo "Installing Finder Quick Action: Rename OSA PDFs"
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

if [[ ! -d "/Applications/OSA PDF Renamer.app" && ! -d "$HOME/Applications/OSA PDF Renamer.app" ]]; then
  echo "Warning: OSA PDF Renamer.app is not installed in /Applications or ~/Applications."
  echo
  echo "The Quick Action will install, but it will show an error until the app is installed."
  echo
fi

mkdir -p "$SERVICES_DIR"
rm -rf "$TARGET_WORKFLOW"
cp -R "$SOURCE_WORKFLOW" "$TARGET_WORKFLOW"

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
echo "If it does not appear immediately in Finder:"
echo "  1. Open System Settings"
echo "  2. Keyboard > Keyboard Shortcuts > Services"
echo "  3. Enable Rename OSA PDFs"
echo
echo "Use it by selecting PDFs in Finder, right-clicking, then choosing Quick Actions > Rename OSA PDFs."
echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
