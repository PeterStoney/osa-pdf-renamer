#!/usr/bin/env python3

import sys
import tempfile
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.models import RenameResult
from pdf_renamer.models import DocumentDetails
from pdf_renamer.review import (
    contains_unknown_value,
    field_dialog_script,
    review_field_pairs,
    review_preview_path,
)


def main() -> int:
    if not contains_unknown_value(["16-05-26", "unknown", "MRI right knee"]):
        raise AssertionError("unknown correction value should be treated as skip")
    if contains_unknown_value(["16-05-26", "John Smith", "MRI right knee"]):
        raise AssertionError("complete correction was treated as unknown")

    with tempfile.TemporaryDirectory() as tmpdir:
        folder = Path(tmpdir)
        original_path = folder / "Original.pdf"
        final_path = folder / "unknown - Reg form.pdf"
        original_path.write_text("original", encoding="utf-8")
        final_path.write_text("final", encoding="utf-8")

        item = RenameResult(
            renamed=True,
            needs_review=True,
            original_path=original_path,
            final_path=final_path,
        )
        if review_preview_path(item) != final_path:
            raise AssertionError("review should preview the current renamed file")

        final_path.unlink()
        if review_preview_path(item) != original_path:
            raise AssertionError("review should fall back to the original file")

    details = DocumentDetails(
        patient_name="Alex Sample",
        sender="Example Clinic",
        document_type="Referral",
        document_date="18-06-26",
    )
    fields = review_field_pairs(
        details,
        include_date=True,
        include_sender=False,
        include_name=True,
        include_type=True,
    )
    if fields != [
        ("Date", "18-06-26"),
        ("Subject", "Alex Sample"),
        ("Document type", "Referral"),
    ]:
        raise AssertionError(f"unexpected enabled review fields: {fields}")

    script = field_dialog_script(
        title="Review PDF filename",
        message="Example.pdf needs review.",
        fields=fields,
    )
    if "Date:" not in script or "Sender:" in script:
        raise AssertionError("review dialog should include only enabled fields")
    if "Subject:" not in script or "Document type:" not in script:
        raise AssertionError("review dialog is missing enabled fields")
    if " | " in script or "separated by pipes" in script:
        raise AssertionError("review dialog should not use pipe-separated input")

    print("PASS: review unknown handling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
