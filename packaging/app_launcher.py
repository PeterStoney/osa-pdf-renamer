#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.app import main
from pdf_renamer.ui import show_app_ui


def launch() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:
        print("OK: OSA PDF Renamer app launcher is working.")
        return 0

    if not args:
        return show_app_ui()

    summary = main(args)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(launch())
