#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer import applescript


def main() -> int:
    text = applescript.literal("Choose PDFs…")
    if "\\u2026" in text:
        raise AssertionError("AppleScript literal should not ASCII-escape ellipsis")
    if text != '"Choose PDFs…"':
        raise AssertionError(f"unexpected AppleScript literal: {text}")

    quoted = applescript.literal('He said "hello"')
    if quoted != '"He said \\"hello\\""':
        raise AssertionError(f"quoted text was not escaped correctly: {quoted}")

    print("PASS: AppleScript literal formatting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
