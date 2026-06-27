from pathlib import Path

from .config import UNKNOWN
from .extraction import extract_document_details_with_ollama
from .models import RenameResult
from .naming import build_filename, unique_path
from .ocr import extract_document_text, enhance_text_with_targeted_field_ocr


def unresolved_enabled_fields(
    details,
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> set[str]:
    fields = set()
    if include_name and details.patient_name == UNKNOWN:
        fields.add("name")
    if include_sender and details.sender == UNKNOWN:
        fields.add("sender")
    if include_recipient and details.recipient == UNKNOWN:
        fields.add("recipient")
    if include_type and details.document_type == UNKNOWN:
        fields.add("type")
    if include_date and details.document_date == UNKNOWN:
        fields.add("date")
    if include_reference and details.reference == UNKNOWN:
        fields.add("reference")
    if include_amount and details.amount == UNKNOWN:
        fields.add("amount")
    if include_location and details.location == UNKNOWN:
        fields.add("location")
    if include_status and details.status == UNKNOWN:
        fields.add("status")
    return fields


def enabled_fields(
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> set[str]:
    fields = set()
    if include_name:
        fields.add("name")
    if include_sender:
        fields.add("sender")
    if include_recipient:
        fields.add("recipient")
    if include_type:
        fields.add("type")
    if include_date:
        fields.add("date")
    if include_reference:
        fields.add("reference")
    if include_amount:
        fields.add("amount")
    if include_location:
        fields.add("location")
    if include_status:
        fields.add("status")
    return fields


def merge_recovered_details(original, recovered):
    if original.patient_name != UNKNOWN and recovered.patient_name == UNKNOWN:
        recovered.patient_name = original.patient_name
        recovered.name_evidence = original.name_evidence
    if original.sender != UNKNOWN and recovered.sender == UNKNOWN:
        recovered.sender = original.sender
        recovered.sender_evidence = original.sender_evidence
    if original.recipient != UNKNOWN and recovered.recipient == UNKNOWN:
        recovered.recipient = original.recipient
        recovered.recipient_evidence = original.recipient_evidence
    if original.document_type != UNKNOWN and recovered.document_type == UNKNOWN:
        recovered.document_type = original.document_type
        recovered.type_evidence = original.type_evidence
    if original.document_date != UNKNOWN and recovered.document_date == UNKNOWN:
        recovered.document_date = original.document_date
        recovered.date_evidence = original.date_evidence
    if original.reference != UNKNOWN and recovered.reference == UNKNOWN:
        recovered.reference = original.reference
        recovered.reference_evidence = original.reference_evidence
    if original.amount != UNKNOWN and recovered.amount == UNKNOWN:
        recovered.amount = original.amount
        recovered.amount_evidence = original.amount_evidence
    if original.location != UNKNOWN and recovered.location == UNKNOWN:
        recovered.location = original.location
        recovered.location_evidence = original.location_evidence
    if original.status != UNKNOWN and recovered.status == UNKNOWN:
        recovered.status = original.status
        recovered.status_evidence = original.status_evidence
    return recovered


def rename_pdf(
    pdf_path: Path,
    *,
    dry_run: bool = False,
    debug_mode: str = "failures",
    include_date: bool = True,
    include_sender: bool = False,
    include_name: bool = True,
    include_type: bool = True,
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> RenameResult:
    text = extract_document_text(pdf_path)
    if not text.strip():
        raise RuntimeError(
            "No text could be extracted from the first page. "
            "Check PDF rendering, Vision OCR, and app permissions."
        )

    required_fields = enabled_fields(
        include_date=include_date,
        include_sender=include_sender,
        include_name=include_name,
        include_type=include_type,
        include_recipient=include_recipient,
        include_reference=include_reference,
        include_amount=include_amount,
        include_location=include_location,
        include_status=include_status,
    )
    details = extract_document_details_with_ollama(
        text,
        required_fields=required_fields,
    )
    unresolved_fields = unresolved_enabled_fields(
        details,
        include_date=include_date,
        include_sender=include_sender,
        include_name=include_name,
        include_type=include_type,
        include_recipient=include_recipient,
        include_reference=include_reference,
        include_amount=include_amount,
        include_location=include_location,
        include_status=include_status,
    )
    if unresolved_fields:
        enhanced_text = enhance_text_with_targeted_field_ocr(
            pdf_path,
            text,
            unresolved_fields,
        )
        if enhanced_text != text:
            recovered_details = extract_document_details_with_ollama(
                enhanced_text,
                required_fields=required_fields,
            )
            details = merge_recovered_details(details, recovered_details)
            text = enhanced_text

    base_name = build_filename(
        details.patient_name,
        details.document_type,
        details.document_date,
        details.sender,
        details.recipient,
        details.reference,
        details.amount,
        details.location,
        details.status,
        include_date=include_date,
        include_sender=include_sender,
        include_name=include_name,
        include_type=include_type,
        include_recipient=include_recipient,
        include_reference=include_reference,
        include_amount=include_amount,
        include_location=include_location,
        include_status=include_status,
    )
    new_path = unique_path(
        pdf_path.parent,
        base_name,
        current_path=pdf_path,
    )

    needs_review = bool(
        unresolved_enabled_fields(
            details,
            include_date=include_date,
            include_sender=include_sender,
            include_name=include_name,
            include_type=include_type,
            include_recipient=include_recipient,
            include_reference=include_reference,
            include_amount=include_amount,
            include_location=include_location,
            include_status=include_status,
        )
    )
    write_debug = (
        debug_mode == "all"
        or (debug_mode == "failures" and needs_review)
    )

    if write_debug:
        debug_path = new_path.with_suffix(".debug.txt")
        debug_path.write_text(
            "===== ORIGINAL FILE =====\n\n"
            + pdf_path.name
            + "\n\n===== FINAL FILE =====\n\n"
            + new_path.name
            + "\n\n===== LABELLED OCR TEXT =====\n\n"
            + text
            + "\n\n===== RAW MODEL RESPONSE =====\n\n"
            + details.raw_model_response
            + "\n\n===== PARSED PATIENT NAME =====\n\n"
            + details.patient_name
            + "\n\n===== SENDER =====\n\n"
            + details.sender
            + "\n\n===== RECIPIENT =====\n\n"
            + details.recipient
            + "\n\n===== DOCUMENT TYPE =====\n\n"
            + details.document_type
            + "\n\n===== DOCUMENT DATE =====\n\n"
            + details.document_date
            + "\n\n===== REFERENCE =====\n\n"
            + details.reference
            + "\n\n===== AMOUNT =====\n\n"
            + details.amount
            + "\n\n===== LOCATION =====\n\n"
            + details.location
            + "\n\n===== STATUS =====\n\n"
            + details.status
            + "\n\n===== NAME EVIDENCE =====\n\n"
            + details.name_evidence
            + "\n\n===== SENDER EVIDENCE =====\n\n"
            + details.sender_evidence
            + "\n\n===== RECIPIENT EVIDENCE =====\n\n"
            + details.recipient_evidence
            + "\n\n===== TYPE EVIDENCE =====\n\n"
            + details.type_evidence
            + "\n\n===== DATE EVIDENCE =====\n\n"
            + details.date_evidence
            + "\n\n===== REFERENCE EVIDENCE =====\n\n"
            + details.reference_evidence
            + "\n\n===== AMOUNT EVIDENCE =====\n\n"
            + details.amount_evidence
            + "\n\n===== LOCATION EVIDENCE =====\n\n"
            + details.location_evidence
            + "\n\n===== STATUS EVIDENCE =====\n\n"
            + details.status_evidence
            + "\n\n===== MODEL CONFIDENCE =====\n\n"
            + f"{details.confidence:.3f}\n",
            encoding="utf-8",
        )

    print(f"{pdf_path.name} -> {new_path.name}")

    renamed = pdf_path.resolve() != new_path.resolve()
    if renamed and not dry_run:
        pdf_path.rename(new_path)

    return RenameResult(
        renamed=renamed,
        needs_review=needs_review,
        original_path=pdf_path,
        final_path=new_path,
        details=details,
        ocr_text=text,
    )
