#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.update_check import newer_version_available, versioned_pkg_path


def main() -> int:
    cases = [
        ("0.2.0", "0.2.1", True),
        ("0.2.0", "v0.3.0", True),
        ("0.2.0", "0.2.0", False),
        ("0.2.1", "0.2.0", False),
        ("1.0", "1.0.1", True),
    ]
    for current, latest, expected in cases:
        actual = newer_version_available(current, latest)
        if actual != expected:
            print(
                "FAIL: "
                f"current={current}, latest={latest}, "
                f"expected={expected}, got={actual}"
            )
            return 1

    expected_name = "OSA PDF Renamer Installer 0.2.1.pkg"
    if versioned_pkg_path("0.2.1").name != expected_name:
        print("FAIL: unexpected versioned pkg filename")
        return 1

    print("PASS: update version comparison")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
