#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

import pdf_renamer as renamer
from pdf_renamer.config import OLLAMA_MODEL, OLLAMA_URL


def load_cases(manifest_path: Path):
    with manifest_path.open(encoding="utf-8") as source:
        return json.load(source)


def model_response_was_used(details) -> bool:
    raw = details.raw_model_response.strip()
    return bool(raw) and not raw.startswith(("SKIPPED:", "ERROR:"))


def check_model_available() -> tuple[bool, str]:
    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": "Return JSON: {\"ok\": true}",
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 20,
                },
            },
            timeout=30,
        )
        response.raise_for_status()
    except Exception as error:
        return False, str(error)

    return True, ""


def run_case(case):
    if "ocr_text" in case:
        text = case["ocr_text"]
    else:
        pdf_path = Path(case["file"]).expanduser()
        if not pdf_path.is_file():
            return "SKIP", f"file not found: {pdf_path}"
        text = renamer.extract_document_text(pdf_path)

    details = renamer.extract_document_details_with_ollama(text)
    model_used = model_response_was_used(details)

    expected = [
        case["patient_name"],
        case["document_type"],
        case.get("document_date", renamer.UNKNOWN),
    ]
    actual = [
        details.patient_name,
        details.document_type,
        details.document_date,
    ]
    if "sender" in case:
        expected.insert(1, case["sender"])
        actual.insert(1, details.sender)

    if actual == expected:
        return "PASS", " - ".join(actual), model_used

    return (
        "FAIL",
        (
            f"expected {' - '.join(expected)}; "
            f"got {' - '.join(actual)}"
        ),
        model_used,
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
    parser.add_argument(
        "--require-model",
        action="store_true",
        help=(
            "Require Ollama model output. This is now the default and the "
            "flag is kept for compatibility."
        ),
    )
    parser.add_argument(
        "--allow-no-model",
        action="store_true",
        help=(
            "Allow deterministic-only fallback when Ollama is unavailable. "
            "Use only for offline/sandbox smoke checks."
        ),
    )
    args = parser.parse_args()

    require_model = not args.allow_no_model

    if require_model:
        model_available, message = check_model_available()
        if not model_available:
            print(
                f"FAIL: Ollama model is unavailable at {OLLAMA_URL}: {message}"
            )
            return 1

    cases = load_cases(args.cases)
    counts = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    model_used_count = 0

    for case in cases:
        status, message, model_used = run_case(case)
        if model_used:
            model_used_count += 1
        counts[status] += 1
        print(f"{status}: {case['name']}")
        print(f"  {message}")

    print(
        "\n"
        f"{counts['PASS']} passed, "
        f"{counts['FAIL']} failed, "
        f"{counts['SKIP']} skipped"
    )
    if require_model:
        print(f"{model_used_count} case(s) used model output")
        if model_used_count == 0:
            print("FAIL: no regression case exercised Ollama model output")
            return 1

    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
