#!/bin/zsh
set -euo pipefail

SCRIPT_DIR=${0:a:h}
PROJECT_DIR=${SCRIPT_DIR:h}
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
CONDA_ENV_PYTHON="/opt/miniconda3/envs/osa-pdf-renamer-build/bin/python"
PYTHON="$CONDA_ENV_PYTHON"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="/opt/miniconda3/bin/python"
fi

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
  echo "Create the clean build environment with:"
  echo "  /opt/miniconda3/bin/conda env create -f packaging/environment.yml"
  echo
  echo "Or update it with:"
  echo "  /opt/miniconda3/bin/conda env update -f packaging/environment.yml --prune"
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

POPPLER_VENDOR_DIR="$PROJECT_DIR/build/vendor_poppler"
POPPLER_BIN_DIR="$POPPLER_VENDOR_DIR/bin"
POPPLER_LIB_DIR="$POPPLER_VENDOR_DIR/lib"

echo "Bundling Poppler tools..."
rm -rf "$POPPLER_VENDOR_DIR"
mkdir -p "$POPPLER_BIN_DIR" "$POPPLER_LIB_DIR"

PDFTOTEXT_SOURCE="$(command -v pdftotext || true)"
PDFTOPPM_SOURCE="$(command -v pdftoppm || true)"
PDFINFO_SOURCE="$(command -v pdfinfo || true)"

if [[ -z "$PDFTOTEXT_SOURCE" || -z "$PDFTOPPM_SOURCE" || -z "$PDFINFO_SOURCE" ]]; then
  echo "pdftotext/pdftoppm/pdfinfo are missing on this build machine."
  echo "Install Poppler on the build machine before packaging."
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

cp "$(realpath "$PDFTOTEXT_SOURCE")" "$POPPLER_BIN_DIR/pdftotext"
cp "$(realpath "$PDFTOPPM_SOURCE")" "$POPPLER_BIN_DIR/pdftoppm"
cp "$(realpath "$PDFINFO_SOURCE")" "$POPPLER_BIN_DIR/pdfinfo"
chmod +x "$POPPLER_BIN_DIR/pdftotext" "$POPPLER_BIN_DIR/pdftoppm" "$POPPLER_BIN_DIR/pdfinfo"

POPPLER_LIB="$(
  otool -L "$PDFTOTEXT_SOURCE" \
    | awk '/libpoppler\.[0-9]+\.dylib/ {print $1; exit}'
)"
LCMS_LIB="$(
  otool -L "$PDFTOPPM_SOURCE" \
    | awk '/liblcms2\.2\.dylib/ {print $1; exit}'
)"

if [[ -z "$POPPLER_LIB" || -z "$LCMS_LIB" ]]; then
  echo "Could not locate Poppler runtime libraries."
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

if [[ "$POPPLER_LIB" == @rpath/* ]]; then
  POPPLER_LIB="/opt/homebrew/lib/${POPPLER_LIB:t}"
fi

if [[ "$LCMS_LIB" == @rpath/* ]]; then
  LCMS_LIB="/opt/homebrew/lib/${LCMS_LIB:t}"
fi

cp "$(realpath "$POPPLER_LIB")" "$POPPLER_LIB_DIR/libpoppler.161.dylib"
cp "$(realpath "$LCMS_LIB")" "$POPPLER_LIB_DIR/liblcms2.2.dylib"
chmod +w "$POPPLER_BIN_DIR/pdftoppm" "$POPPLER_LIB_DIR"/*.dylib

/usr/bin/install_name_tool \
  -change "$LCMS_LIB" \
  "@loader_path/../lib/liblcms2.2.dylib" \
  "$POPPLER_BIN_DIR/pdftoppm"

OLLAMA_VENDOR_DIR="$PROJECT_DIR/build/vendor_ollama"
OLLAMA_BIN_DIR="$OLLAMA_VENDOR_DIR/bin"

echo "Bundling Ollama runtime..."
rm -rf "$OLLAMA_VENDOR_DIR"
mkdir -p "$OLLAMA_BIN_DIR"

OLLAMA_SOURCE="$(command -v ollama || true)"
if [[ -z "$OLLAMA_SOURCE" ]]; then
  echo "Ollama is missing on this build machine."
  echo "Install Ollama on the build machine before packaging."
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close."
  fi
  exit 1
fi

cp "$(realpath "$OLLAMA_SOURCE")" "$OLLAMA_BIN_DIR/ollama"
chmod +x "$OLLAMA_BIN_DIR/ollama"

echo "Compiling Vision OCR helper..."
/usr/bin/xcrun swiftc -O helpers/vision_ocr.swift -o vision_ocr
chmod +x vision_ocr

echo "Compiling progress helper..."
/usr/bin/xcrun swiftc -O helpers/progress_runner.swift -o progress_runner
chmod +x progress_runner

echo "Compiling app shell..."
/usr/bin/xcrun swiftc -O helpers/app_shell.swift -o app_shell
chmod +x app_shell

echo "Running PyInstaller..."
"$PYTHON" -m PyInstaller --noconfirm "packaging/OSA PDF Renamer.spec"

APP_BUNDLE="$PROJECT_DIR/dist/OSA PDF Renamer.app"
APP_MACOS_DIR="$APP_BUNDLE/Contents/MacOS"
PYTHON_RUNNER="$APP_MACOS_DIR/renamer_cli"
PYINSTALLER_EXECUTABLE="$APP_MACOS_DIR/OSA PDF Renamer"
APP_EXECUTABLE="$APP_MACOS_DIR/OSAPDFRenamer"

echo "Installing Swift app shell..."
if [[ ! -x "$PYINSTALLER_EXECUTABLE" ]]; then
  echo "Missing PyInstaller app executable:"
  echo "  $PYINSTALLER_EXECUTABLE"
  exit 1
fi
rm -f "$PYTHON_RUNNER"
mv "$PYINSTALLER_EXECUTABLE" "$PYTHON_RUNNER"
cp "$PROJECT_DIR/app_shell" "$APP_EXECUTABLE"
chmod +x "$APP_EXECUTABLE" "$PYTHON_RUNNER"
/usr/libexec/PlistBuddy -c "Set :CFBundleExecutable OSAPDFRenamer" \
  "$APP_BUNDLE/Contents/Info.plist"
printf "APPL????" > "$APP_BUNDLE/Contents/PkgInfo"

echo "Signing app bundle..."
/usr/bin/codesign --force --deep --sign - "$APP_BUNDLE" >/dev/null

echo
echo "Built:"
echo "  $APP_BUNDLE"
echo
if [[ -t 0 ]]; then
  read -k 1 "?Press any key to close."
fi
