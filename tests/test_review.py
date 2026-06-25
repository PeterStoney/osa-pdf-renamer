#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.review import contains_unknown_value


def main() -> int:
    if not contains_unknown_value(["16-05-26", "unknown", "MRI right knee"]):
        raise AssertionError("unknown correction value should be treated as skip")
    if contains_unknown_value(["16-05-26", "John Smith", "MRI right knee"]):
        raise AssertionError("complete correction was treated as unknown")

    print("PASS: review unknown handling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
