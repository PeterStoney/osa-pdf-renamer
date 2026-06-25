#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import pdf_renamer as renamer


def load_cases(manifest_path: Path):
    with manifest_path.open(encoding="utf-8") as source:
        return json.load(source)


def run_case(case):
    if "ocr_text" in case:
        text = case["ocr_text"]
    else:
        pdf_path = Path(case["file"]).expanduser()
        if not pdf_path.is_file():
            return "SKIP", f"file not found: {pdf_path}"
        text = renamer.extract_document_text(pdf_path)

    details = renamer.extract_document_details_with_ollama(text)

    expected = (
        case["patient_name"],
        case["document_type"],
        case.get("document_date", renamer.UNKNOWN),
    )
    actual = (
        details.patient_name,
        details.document_type,
        details.document_date,
    )

    if actual == expected:
        return "PASS", " - ".join(actual)

    return (
        "FAIL",
        (
            f"expected {' - '.join(expected)}; "
            f"got {' - '.join(actual)}"
        ),
    )


def main():
    parser = argparse.ArgumentParser(
        description="Run read-only PDF renamer regression cases.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("regression_cases.json"),
        help="Path to the regression case manifest.",
    )
    args = parser.parse_args()

    cases = load_cases(args.cases)
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}

    for case in cases:
        status, message = run_case(case)
        counts[status] += 1
        print(f"{status}: {case['name']}")
        print(f"  {message}")

    print(
        "\n"
        f"{counts['PASS']} passed, "
        f"{counts['FAIL']} failed, "
        f"{counts['SKIP']} skipped"
    )

    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
