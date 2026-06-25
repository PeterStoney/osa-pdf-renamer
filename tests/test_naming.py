#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.naming import build_filename


def expect(actual: str, expected: str) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def main() -> int:
    expect(
        build_filename("John Smith", "MRI right knee", "16-05-26"),
        "16-05-26 - John Smith - MRI right knee",
    )
    expect(
        build_filename("John Smith", "MRI right knee"),
        "John Smith - MRI right knee",
    )
    expect(
        build_filename("unknown", "Reg form", "01-06-26"),
        "01-06-26 - unknown - Reg form",
    )
    expect(
        build_filename(
            "John Smith",
            "MRI right knee",
            "16-05-26",
            include_date=False,
        ),
        "John Smith - MRI right knee",
    )
    expect(
        build_filename(
            "John Smith",
            "MRI right knee",
            "16-05-26",
            include_name=False,
        ),
        "16-05-26 - MRI right knee",
    )
    expect(
        build_filename(
            "John Smith",
            "MRI right knee",
            "16-05-26",
            include_type=False,
        ),
        "16-05-26 - John Smith",
    )
    expect(
        build_filename(
            "John Smith",
            "MRI right knee",
            "16-05-26",
            include_date=False,
            include_name=False,
            include_type=True,
        ),
        "MRI right knee",
    )
    expect(
        build_filename(
            "John Smith",
            "MRI right knee",
            "16-05-26",
            include_date=False,
            include_name=False,
            include_type=False,
        ),
        "Unknown",
    )
    print("PASS: filename formatting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
