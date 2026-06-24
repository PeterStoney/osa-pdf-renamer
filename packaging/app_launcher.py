#!/usr/bin/env python3

import subprocess
import sys
import json
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.app import main


def show_dialog(title: str, message: str) -> None:
    script = (
        'display dialog '
        f'{json.dumps(message)} '
        f'with title {json.dumps(title)} '
        'buttons {"OK"} default button "OK"'
    )
    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def launch() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:
        print("OK: OSA PDF Renamer app launcher is working.")
        return 0

    if not args:
        show_dialog(
            "OSA PDF Renamer",
            (
                "OSA PDF Renamer is installed.\n\n"
                "To rename documents, select one or more PDFs in Finder "
                "and use the Rename OSA PDFs Quick Action."
            ),
        )
        return 0

    summary = main(args)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(launch())
