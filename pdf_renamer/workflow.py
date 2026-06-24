from pathlib import Path

from .config import UNKNOWN
from .extraction import extract_document_details_with_ollama
from .models import RenameResult
from .naming import build_filename, unique_path
from .ocr import extract_document_text


def rename_pdf(
    pdf_path: Path,
    *,
    dry_run: bool = False,
    debug_mode: str = "failures",
) -> RenameResult:
    text = extract_document_text(pdf_path)
    if not text.strip():
        raise RuntimeError(
            "No text could be extracted from the first page. "
            "Check PDF rendering, Vision OCR, and app permissions."
        )

    details = extract_document_details_with_ollama(text)

    base_name = build_filename(
        details.patient_name,
        details.document_type,
    )
    new_path = unique_path(
        pdf_path.parent,
        base_name,
        current_path=pdf_path,
    )

    needs_review = (
        details.patient_name == UNKNOWN
        or details.document_type == UNKNOWN
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
            + "\n\n===== DOCUMENT TYPE =====\n\n"
            + details.document_type
            + "\n\n===== NAME EVIDENCE =====\n\n"
            + details.name_evidence
            + "\n\n===== TYPE EVIDENCE =====\n\n"
            + details.type_evidence
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
    )
