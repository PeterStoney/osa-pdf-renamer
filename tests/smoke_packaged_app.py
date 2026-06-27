#!/usr/bin/env python3

import subprocess
import sys
import plistlib
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_DIR / "dist" / "OSA PDF Renamer.app"
MACOS_DIR = APP_PATH / "Contents" / "MacOS"
RESOURCES_DIR = APP_PATH / "Contents" / "Resources"
FRAMEWORKS_DIR = APP_PATH / "Contents" / "Frameworks"
QUICK_ACTION = (
    PROJECT_DIR
    / "packaging"
    / "quick_action"
    / "Rename OSA PDFs.workflow"
    / "Contents"
    / "Info.plist"
)


def check(condition: bool, message: str) -> bool:
    if condition:
        print(f"PASS: {message}")
        return True
    print(f"FAIL: {message}")
    return False


def executable(path: Path) -> bool:
    return path.is_file() and path.stat().st_mode & 0o111 != 0


def main() -> int:
    ok = True
    info_plist = APP_PATH / "Contents" / "Info.plist"
    info = {}
    if info_plist.is_file():
        info = plistlib.loads(info_plist.read_bytes())
    executable_name = info.get("CFBundleExecutable", "OSA PDF Renamer")
    launcher = MACOS_DIR / executable_name
    runner = MACOS_DIR / "renamer_cli"
    ok &= check(APP_PATH.is_dir(), f"app bundle exists: {APP_PATH}")
    ok &= check(executable(launcher), "app launcher is executable")
    ok &= check(executable(runner), "bundled Python runner is executable")

    if info:
        document_types = info.get("CFBundleDocumentTypes", [])
        content_types = {
            content_type
            for document_type in document_types
            for content_type in document_type.get("LSItemContentTypes", [])
        }
        ok &= check(
            "public.pdf" in content_types,
            "app declares PDF document drag/drop support",
        )
    else:
        ok &= check(False, f"Info.plist exists: {info_plist}")

    for resource in ("config.toml", "VERSION"):
        ok &= check(
            (RESOURCES_DIR / resource).is_file(),
            f"bundled resource exists: {resource}",
        )

    for binary in (
        "pdftotext",
        "pdftoppm",
        "pdfinfo",
        "vision_ocr",
        "progress_runner",
        "ollama",
    ):
        candidates = (
            FRAMEWORKS_DIR / binary,
            FRAMEWORKS_DIR / "bin" / binary,
            RESOURCES_DIR / binary,
            RESOURCES_DIR / "bin" / binary,
        )
        ok &= check(
            any(executable(candidate) for candidate in candidates),
            f"bundled executable exists: {binary}",
        )

    if launcher.is_file():
        smoke_pdf = Path("/tmp/osa-pdf-renamer-drag-drop-smoke.pdf")
        smoke_pdf.write_bytes(b"%PDF-1.4\n% invalid smoke-test PDF\n")
        result = subprocess.run(
            [
                "/usr/bin/open",
                "-n",
                str(APP_PATH),
                "--args",
                str(smoke_pdf),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        ok &= check(
            result.returncode == 0,
            "app accepts PDF file path launch through Launch Services",
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
        smoke_pdf.unlink(missing_ok=True)

    if QUICK_ACTION.is_file():
        result = subprocess.run(
            ["/usr/bin/plutil", "-lint", str(QUICK_ACTION)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        ok &= check(result.returncode == 0, "Quick Action plist is valid")
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
    else:
        ok &= check(False, f"Quick Action plist exists: {QUICK_ACTION}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
