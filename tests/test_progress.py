#!/usr/bin/env python3

import os
import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.progress import PROGRESS_FILE_ENV, write_progress


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "progress.txt"
        os.environ[PROGRESS_FILE_ENV] = str(path)
        write_progress(2, 5, message="Processing\tExample\nFile.pdf")
        body = path.read_text(encoding="utf-8")
        if body != "2\t5\tProcessing Example File.pdf":
            raise AssertionError(f"unexpected progress body: {body!r}")
        os.environ.pop(PROGRESS_FILE_ENV, None)

    print("PASS: progress file format")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
