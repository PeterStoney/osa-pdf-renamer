#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.corrections import (
    MAX_CORRECTIONS,
    load_corrections,
    save_correction,
)
from pdf_renamer.models import DocumentDetails


def main() -> int:
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "corrections.jsonl"
        detected = DocumentDetails(
            patient_name="unknown",
            document_type="Unknown",
            document_date="unknown",
        )
        corrected = DocumentDetails(
            patient_name="Alex Sample",
            document_type="MRI right knee",
            document_date="16-05-26",
        )

        for index in range(MAX_CORRECTIONS + 5):
            save_correction(
                original_path=Path(f"original-{index}.pdf"),
                reviewed_path=Path(f"reviewed-{index}.pdf"),
                corrected_path=Path(f"corrected-{index}.pdf"),
                ocr_text=f"synthetic OCR {index}",
                detected=detected,
                corrected=corrected,
                path=path,
            )

        records = load_corrections(path)
        if len(records) != MAX_CORRECTIONS:
            raise AssertionError(
                f"expected {MAX_CORRECTIONS} records, got {len(records)}"
            )

        save_correction(
            original_path=Path("original-duplicate.pdf"),
            reviewed_path=Path("reviewed-duplicate.pdf"),
            corrected_path=Path("corrected-duplicate.pdf"),
            ocr_text="synthetic OCR 204",
            detected=detected,
            corrected=corrected,
            path=path,
        )
        records = load_corrections(path)
        if len(records) != MAX_CORRECTIONS:
            raise AssertionError("duplicate correction changed record count")
        if records[-1]["corrected_filename"] != "corrected-duplicate.pdf":
            raise AssertionError("duplicate correction was not replaced")

    print("PASS: correction store bounds and dedupe")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
