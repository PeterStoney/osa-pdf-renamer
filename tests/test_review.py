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
    contains_unresolved_value,
    field_dialog_script,
    missing_field_labels,
    review_field_pairs,
    review_preview_path,
    values_changed,
)


def main() -> int:
    if not contains_unknown_value(["16-05-26", "unknown", "MRI right knee"]):
        raise AssertionError("unknown correction value should be treated as skip")
    if not contains_unresolved_value(["16-05-26", "", "MRI right knee"]):
        raise AssertionError("blank correction value should be unresolved")
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
    if missing_field_labels(fields):
        raise AssertionError("complete fields should not be marked missing")

    missing_details = DocumentDetails(
        patient_name="unknown",
        sender="Example Clinic",
        document_type="Referral",
        document_date="unknown",
    )
    missing_fields = review_field_pairs(
        missing_details,
        include_date=True,
        include_sender=False,
        include_name=True,
        include_type=True,
    )
    if missing_fields != [
        ("Date", ""),
        ("Subject", ""),
        ("Document type", "Referral"),
    ]:
        raise AssertionError(f"unknown values should display as blanks: {missing_fields}")
    if missing_field_labels(missing_fields) != ["Date", "Subject"]:
        raise AssertionError("missing review fields were not labelled correctly")
    if values_changed(fields, ["18-06-26", "Alex Sample", "Referral"]):
        raise AssertionError("unchanged review values should be treated as skip")
    if not values_changed(fields, ["19-06-26", "Alex Sample", "Referral"]):
        raise AssertionError("changed review values should be treated as correction")

    script = field_dialog_script(
        title="Review PDF filename",
        message="Review 1 of 2\n\nMissing fields: Date",
        fields=fields,
    )
    if "Date:" not in script or "Sender:" in script:
        raise AssertionError("review dialog should include only enabled fields")
    if "Subject:" not in script or "Document type:" not in script:
        raise AssertionError("review dialog is missing enabled fields")
    if "setEditable:true" not in script or "stringValue() as text" not in script:
        raise AssertionError("review fields should be editable text fields")
    if "activateWithOptions:3" not in script or "System Events" in script:
        raise AssertionError("review dialog should activate without System Events")
    if "setInitialFirstResponder" in script:
        raise AssertionError("review dialog should not force a first responder before display")
    if " | " in script or "separated by pipes" in script:
        raise AssertionError("review dialog should not use pipe-separated input")

    print("PASS: review unknown handling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
