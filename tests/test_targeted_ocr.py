#!/usr/bin/env python3

import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR))

from pdf_renamer.config import UNKNOWN
from pdf_renamer.extraction_model import (
    details_satisfy_required_fields,
    parse_model_response,
)
from pdf_renamer.models import DocumentDetails, VisionLine
from pdf_renamer import ocr
from pdf_renamer.ocr import field_crop_candidates, line_matches_field_label
from pdf_renamer.workflow import (
    enabled_fields,
    merge_recovered_details,
    unresolved_enabled_fields,
)


def expect(actual, expected) -> None:
    if actual != expected:
        raise AssertionError(f"expected {expected!r}, got {actual!r}")


def main() -> int:
    details = DocumentDetails(
        patient_name="Jane Smith",
        document_type=UNKNOWN,
        document_date=UNKNOWN,
        sender=UNKNOWN,
    )
    expect(
        enabled_fields(
            include_date=True,
            include_sender=False,
            include_name=True,
            include_type=True,
            include_reference=True,
        ),
        {"name", "type", "date", "reference"},
    )
    expect(
        unresolved_enabled_fields(
            details,
            include_date=True,
            include_sender=False,
            include_name=True,
            include_type=True,
        ),
        {"date", "type"},
    )

    recovered = merge_recovered_details(
        details,
        DocumentDetails(
            patient_name=UNKNOWN,
            document_type="MRI right knee",
            document_date="16-05-26",
            sender=UNKNOWN,
        ),
    )
    expect(recovered.patient_name, "Jane Smith")
    expect(recovered.document_type, "MRI right knee")
    expect(recovered.document_date, "16-05-26")
    expect(
        details_satisfy_required_fields(details, {"name", "type"}),
        False,
    )
    expect(
        details_satisfy_required_fields(recovered, {"name", "type", "date"}),
        True,
    )

    parsed = parse_model_response(
        """
        {
          "patient_name": "Jane Smith",
          "sender": "Example Supplies",
          "recipient": "Example Recipient",
          "document_type": "Tax Invoice",
          "document_date": "16/05/2026",
          "reference": "INV-1234",
          "amount": "$245.00",
          "location": "12 Smith Street",
          "status": "Paid",
          "name_evidence": "Jane Smith",
          "sender_evidence": "Example Supplies",
          "recipient_evidence": "Example Recipient",
          "type_evidence": "Tax Invoice",
          "date_evidence": "16/05/2026",
          "reference_evidence": "INV-1234",
          "amount_evidence": "$245.00",
          "location_evidence": "12 Smith Street",
          "status_evidence": "Paid",
          "confidence": 0.9
        }
        """
    )
    expect(parsed.reference, "INV-1234")
    expect(parsed.amount, "$245.00")
    expect(parsed.location, "12 Smith Street")
    expect(parsed.status, "Paid")

    if not line_matches_field_label("Patient Name:", "name"):
        raise AssertionError("Patient Name should match name labels")
    if not line_matches_field_label("Examination Date", "date"):
        raise AssertionError("Examination Date should match date labels")
    if line_matches_field_label("Date of Birth", "date"):
        raise AssertionError("Date of Birth should not be a crop label")
    if not line_matches_field_label("Invoice Number", "reference"):
        raise AssertionError("Invoice Number should match reference labels")
    if not line_matches_field_label("Total Due", "amount"):
        raise AssertionError("Total Due should match amount labels")

    candidates = field_crop_candidates(
        (
            VisionLine(
                text="Patient Name:",
                confidence=0.95,
                x=0.12,
                y=0.22,
                width=0.16,
                height=0.025,
            ),
            VisionLine(
                text="Service Date:",
                confidence=0.94,
                x=0.12,
                y=0.30,
                width=0.14,
                height=0.025,
            ),
            VisionLine(
                text="Invoice Number:",
                confidence=0.93,
                x=0.12,
                y=0.38,
                width=0.16,
                height=0.025,
            ),
        ),
        {"name", "date", "reference"},
    )
    labels = [label for label, _ in candidates]
    if not any(label.startswith("name near Patient Name") for label in labels):
        raise AssertionError("missing name crop candidate")
    if not any(label.startswith("date near Service Date") for label in labels):
        raise AssertionError("missing date crop candidate")
    if not any(label.startswith("reference near Invoice Number") for label in labels):
        raise AssertionError("missing reference crop candidate")

    original_page_count = ocr.pdf_page_count
    try:
        ocr.pdf_page_count = lambda _path: 1
        expect(ocr.recovery_page_numbers(Path("single.pdf")), [1])

        ocr.pdf_page_count = lambda _path: 2
        expect(ocr.recovery_page_numbers(Path("two.pdf")), [1, 2])

        ocr.pdf_page_count = lambda _path: 5
        expect(ocr.recovery_page_numbers(Path("five.pdf")), [1, 5, 2])
    finally:
        ocr.pdf_page_count = original_page_count

    print("PASS: targeted OCR planning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
