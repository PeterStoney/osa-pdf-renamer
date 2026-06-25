#!/usr/bin/env python3

import argparse
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

import requests

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.config import OLLAMA_URL
from pdf_renamer.extraction import (
    build_evidence_extraction_prompt,
    constrain_model_details,
    deterministic_document_details,
    parse_model_response,
)


def installed_models() -> set[str]:
    result = subprocess.run(
        ["ollama", "list"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return {
        line.split()[0]
        for line in result.stdout.splitlines()[1:]
        if line.split()
    }


def call_model(model: str, text: str):
    prompt = build_evidence_extraction_prompt(text)
    started = time.perf_counter()
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0,
                "num_predict": 180,
            },
        },
        timeout=120,
    )
    elapsed = time.perf_counter() - started
    response.raise_for_status()
    raw = response.json().get("response", "").strip()
    deterministic = deterministic_document_details(text)
    details = constrain_model_details(
        parse_model_response(raw),
        text,
        deterministic,
    )
    return elapsed, raw, details


def load_cases(path: Path):
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def run_model(model: str, cases: list[dict], *, show_raw: bool = False) -> bool:
    print(f"\nMODEL {model}")
    passed = 0
    timings = []

    for case in cases:
        elapsed, raw, details = call_model(model, case["ocr_text"])
        timings.append(elapsed)

        name_ok = details.patient_name in case["patient_names"]
        type_ok = details.document_type in case["document_types"]
        date_ok = details.document_date == case["document_date"]
        ok = name_ok and type_ok and date_ok
        passed += int(ok)

        print(f"{'PASS' if ok else 'FAIL'}: {case['name']} ({elapsed:.1f}s)")
        print(
            "  "
            f"{details.document_date} - "
            f"{details.patient_name} - "
            f"{details.document_type}"
        )
        if not ok or show_raw:
            print(f"  raw: {raw or '<empty response>'}")

    median = statistics.median(timings) if timings else 0.0
    print(
        f"\nSUMMARY {model}: "
        f"{passed}/{len(cases)} passed, median {median:.1f}s"
    )
    return passed == len(cases)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark local Ollama models on synthetic OCR cases.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=Path(__file__).with_name("model_benchmark_cases.json"),
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["qwen2.5:3b"],
        help="Ollama models to benchmark.",
    )
    parser.add_argument(
        "--show-raw",
        action="store_true",
        help="Print raw model JSON for passing cases too.",
    )
    args = parser.parse_args()

    available = installed_models()
    cases = load_cases(args.cases)
    any_failed = False

    for model in args.models:
        if model not in available:
            print(f"\nSKIP {model}: model is not installed")
            any_failed = True
            continue
        any_failed |= not run_model(model, cases, show_raw=args.show_raw)

    return 1 if any_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
