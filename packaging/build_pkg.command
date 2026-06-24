#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
APP_SOURCE="$PROJECT_DIR/dist/OSA PDF Renamer.app"
WORKFLOW_SOURCE="$PROJECT_DIR/packaging/quick_action/Rename OSA PDFs.workflow"
PKG_ROOT="$PROJECT_DIR/build/pkgroot"
PKG_COMPONENT="$PROJECT_DIR/build/OSA PDF Renamer-component.pkg"
PKG_OUTPUT="$PROJECT_DIR/dist/OSA PDF Renamer Installer.pkg"
APP_TARGET="$PKG_ROOT/Applications"
SUPPORT_TARGET="$PKG_ROOT/Library/Application Support/OSA PDF Renamer/Quick Actions"

echo "Building OSA PDF Renamer Installer.pkg..."
echo

if [[ ! -d "$APP_SOURCE" ]]; then
  echo "Missing built app:"
  echo "  $APP_SOURCE"
  echo
  echo "Build it first with:"
  echo "  packaging/build_app.command"
  echo
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

if [[ ! -d "$WORKFLOW_SOURCE" ]]; then
  echo "Missing Quick Action template:"
  echo "  $WORKFLOW_SOURCE"
  echo
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

rm -rf "$PKG_ROOT" "$PKG_COMPONENT" "$PKG_OUTPUT"
mkdir -p "$APP_TARGET" "$SUPPORT_TARGET" "$PROJECT_DIR/dist"

echo "Staging app..."
cp -R "$APP_SOURCE" "$APP_TARGET/"

echo "Staging Quick Action template..."
cp -R "$WORKFLOW_SOURCE" "$SUPPORT_TARGET/"

echo "Building component package..."
/usr/bin/pkgbuild \
  --root "$PKG_ROOT" \
  --scripts "$PROJECT_DIR/packaging/pkg_scripts" \
  --identifier "au.com.osa.pdf-renamer" \
  --version "0.1.0" \
  --install-location "/" \
  "$PKG_COMPONENT"

echo "Building installer product..."
/usr/bin/productbuild \
  --package "$PKG_COMPONENT" \
  "$PKG_OUTPUT"

echo
echo "Built:"
echo "  $PKG_OUTPUT"
echo
echo "This installer copies:"
echo "  /Applications/OSA PDF Renamer.app"
echo "  ~/Library/Services/Rename OSA PDFs.workflow"
echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
