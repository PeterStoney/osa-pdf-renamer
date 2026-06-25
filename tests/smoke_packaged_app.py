#!/usr/bin/env python3

import subprocess
import sys
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
    launcher = MACOS_DIR / "OSA PDF Renamer"

    ok &= check(APP_PATH.is_dir(), f"app bundle exists: {APP_PATH}")
    ok &= check(executable(launcher), "app launcher is executable")

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
        result = subprocess.run(
            [str(launcher), "--self-test"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        ok &= check(
            result.returncode == 0 and "OK:" in result.stdout,
            "app self-test runs",
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)

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
