#!/usr/bin/env python3

import json
import os
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.app import main
from pdf_renamer.ui import (
    preset_data_for_shell,
    save_output_settings,
    show_about,
    show_app_ui,
    show_settings,
)


def launch() -> int:
    if os.environ.get("OSA_PDF_RENAMER_SELF_TEST") == "1":
        print("OK: OSA PDF Renamer app launcher is working.")
        return 0

    args = sys.argv[1:]
    if args == ["--self-test"]:
        print("OK: OSA PDF Renamer app launcher is working.")
        return 0
    if args == ["--settings"]:
        show_settings()
        return 0
    if args == ["--preset-data"]:
        print(json.dumps(preset_data_for_shell()))
        return 0
    if len(args) == 3 and args[0] == "--save-preset":
        fields = json.loads(args[2])
        if not isinstance(fields, list):
            raise ValueError("preset fields must be a list")
        save_output_settings(args[1], [str(field) for field in fields])
        return 0
    if args == ["--about"]:
        show_about()
        return 0

    if not args:
        return show_app_ui()

    summary = main(args)
    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(launch())
