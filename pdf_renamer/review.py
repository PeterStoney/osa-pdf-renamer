import json
import subprocess
import sys
from pathlib import Path

from .config import UNKNOWN
from .corrections import save_correction, value_or_unknown
from .models import BatchSummary, DocumentDetails, RenameResult
from .naming import build_filename, unique_path


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def review_summary_dialog(summary: BatchSummary) -> bool:
    if sys.platform != "darwin" or not summary.review_items:
        return False

    message = (
        f"Renamed: {summary.renamed}\n"
        f"Needs review: {summary.needs_review}\n"
        f"Errors: {summary.errors}"
    )
    script = (
        "set dialogResult to display dialog "
        f"{json.dumps(message)} "
        'with title "OSA PDF Renamer" '
        'buttons {"Done", "Review unknowns"} '
        'default button "Review unknowns"\n'
        "return button returned of dialogResult"
    )
    return run_osascript(script) == "Review unknowns"


def enabled_field_labels(
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
) -> list[str]:
    labels = []
    if include_date:
        labels.append("Date")
    if include_sender:
        labels.append("Sender")
    if include_name:
        labels.append("Person / subject")
    if include_type:
        labels.append("Document type")
    return labels


def default_review_values(
    details: DocumentDetails,
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
) -> list[str]:
    values = []
    if include_date:
        values.append(details.document_date)
    if include_sender:
        values.append(details.sender)
    if include_name:
        values.append(details.patient_name)
    if include_type:
        values.append(details.document_type)
    return values


def correction_from_values(
    original: DocumentDetails,
    values: list[str],
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
) -> DocumentDetails:
    corrected = DocumentDetails(
        patient_name=original.patient_name,
        sender=original.sender,
        document_type=original.document_type,
        document_date=original.document_date,
        raw_model_response=original.raw_model_response,
        name_evidence=original.name_evidence,
        sender_evidence=original.sender_evidence,
        type_evidence=original.type_evidence,
        date_evidence=original.date_evidence,
        confidence=original.confidence,
    )
    index = 0
    if include_date:
        corrected.document_date = value_or_unknown(values[index])
        index += 1
    if include_sender:
        corrected.sender = value_or_unknown(values[index])
        index += 1
    if include_name:
        corrected.patient_name = value_or_unknown(values[index])
        index += 1
    if include_type:
        corrected.document_type = value_or_unknown(values[index])
    return corrected


def prompt_for_correction(
    item: RenameResult,
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
) -> DocumentDetails | None:
    labels = enabled_field_labels(
        include_date=include_date,
        include_sender=include_sender,
        include_name=include_name,
        include_type=include_type,
    )
    if not labels:
        return None

    default_values = default_review_values(
        item.details,
        include_date=include_date,
        include_sender=include_sender,
        include_name=include_name,
        include_type=include_type,
    )
    default_answer = " | ".join(default_values)
    filename = item.final_path.name if item.final_path else "Unknown.pdf"
    prompt = (
        f"{filename} needs review.\n\n"
        "Edit the fields below, separated by pipes:\n"
        f"{' | '.join(labels)}"
    )

    while True:
        script = (
            "set dialogResult to display dialog "
            f"{json.dumps(prompt)} "
            'with title "Review PDF filename" '
            f"default answer {json.dumps(default_answer)} "
            'buttons {"Skip", "Save"} '
            'default button "Save"\n'
            "return button returned of dialogResult & linefeed & "
            "text returned of dialogResult"
        )
        output = run_osascript(script)
        if not output:
            return None

        button, _, answer = output.partition("\n")
        if button != "Save":
            return None

        values = [part.strip() for part in answer.split("|")]
        if len(values) == len(labels):
            return correction_from_values(
                item.details,
                values,
                include_date=include_date,
                include_sender=include_sender,
                include_name=include_name,
                include_type=include_type,
            )

        default_answer = answer
        prompt = (
            f"Please provide exactly {len(labels)} fields separated by pipes.\n\n"
            f"{' | '.join(labels)}"
        )


def apply_corrected_details(
    item: RenameResult,
    corrected: DocumentDetails,
    *,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
) -> Path | None:
    if item.final_path is None:
        return None

    base_name = build_filename(
        corrected.patient_name,
        corrected.document_type,
        corrected.document_date,
        corrected.sender,
        include_date=include_date,
        include_sender=include_sender,
        include_name=include_name,
        include_type=include_type,
    )
    corrected_path = unique_path(
        item.final_path.parent,
        base_name,
        current_path=item.final_path,
    )
    if corrected_path.resolve() != item.final_path.resolve():
        item.final_path.rename(corrected_path)
    return corrected_path


def review_unknowns(
    summary: BatchSummary,
    *,
    dry_run: bool,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
) -> int:
    if dry_run or not review_summary_dialog(summary):
        return 0

    corrected_count = 0
    for item in summary.review_items:
        corrected = prompt_for_correction(
            item,
            include_date=include_date,
            include_sender=include_sender,
            include_name=include_name,
            include_type=include_type,
        )
        if corrected is None:
            continue

        corrected_path = apply_corrected_details(
            item,
            corrected,
            include_date=include_date,
            include_sender=include_sender,
            include_name=include_name,
            include_type=include_type,
        )
        if corrected_path is None:
            continue

        save_correction(
            original_path=item.original_path or item.final_path,
            reviewed_path=item.final_path,
            corrected_path=corrected_path,
            ocr_text=item.ocr_text,
            detected=item.details,
            corrected=corrected,
        )
        item.final_path = corrected_path
        corrected_count += 1

    return corrected_count
