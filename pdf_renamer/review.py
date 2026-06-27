import subprocess
import sys
from pathlib import Path

from . import applescript
from .config import UNKNOWN
from .corrections import save_correction, value_or_unknown
from .models import BatchSummary, DocumentDetails, RenameResult
from .naming import build_filename, unique_path


EXIT_REVIEW = "__EXIT_REVIEW__"


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
        f"{applescript.literal(message)} "
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
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> list[str]:
    labels = []
    if include_date:
        labels.append("Date")
    if include_sender:
        labels.append("Sender")
    if include_recipient:
        labels.append("Recipient")
    if include_name:
        labels.append("Subject")
    if include_reference:
        labels.append("Reference")
    if include_type:
        labels.append("Document type")
    if include_amount:
        labels.append("Amount")
    if include_location:
        labels.append("Location")
    if include_status:
        labels.append("Status")
    return labels


def default_review_values(
    details: DocumentDetails,
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
) -> list[str]:
    values = []
    if include_date:
        values.append(review_display_value(details.document_date))
    if include_sender:
        values.append(review_display_value(details.sender))
    if include_recipient:
        values.append(review_display_value(details.recipient))
    if include_name:
        values.append(review_display_value(details.patient_name))
    if include_reference:
        values.append(review_display_value(details.reference))
    if include_type:
        values.append(review_display_value(details.document_type))
    if include_amount:
        values.append(review_display_value(details.amount))
    if include_location:
        values.append(review_display_value(details.location))
    if include_status:
        values.append(review_display_value(details.status))
    return values


def review_display_value(value: str) -> str:
    return "" if value.strip().lower() == UNKNOWN else value


def correction_from_values(
    original: DocumentDetails,
    values: list[str],
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
) -> DocumentDetails:
    corrected = DocumentDetails(
        patient_name=original.patient_name,
        sender=original.sender,
        recipient=original.recipient,
        document_type=original.document_type,
        document_date=original.document_date,
        reference=original.reference,
        amount=original.amount,
        location=original.location,
        status=original.status,
        raw_model_response=original.raw_model_response,
        name_evidence=original.name_evidence,
        sender_evidence=original.sender_evidence,
        recipient_evidence=original.recipient_evidence,
        type_evidence=original.type_evidence,
        date_evidence=original.date_evidence,
        reference_evidence=original.reference_evidence,
        amount_evidence=original.amount_evidence,
        location_evidence=original.location_evidence,
        status_evidence=original.status_evidence,
        confidence=original.confidence,
    )
    index = 0
    if include_date:
        corrected.document_date = value_or_unknown(values[index])
        index += 1
    if include_sender:
        corrected.sender = value_or_unknown(values[index])
        index += 1
    if include_recipient:
        corrected.recipient = value_or_unknown(values[index])
        index += 1
    if include_name:
        corrected.patient_name = value_or_unknown(values[index])
        index += 1
    if include_reference:
        corrected.reference = value_or_unknown(values[index])
        index += 1
    if include_type:
        corrected.document_type = value_or_unknown(values[index])
        index += 1
    if include_amount:
        corrected.amount = value_or_unknown(values[index])
        index += 1
    if include_location:
        corrected.location = value_or_unknown(values[index])
        index += 1
    if include_status:
        corrected.status = value_or_unknown(values[index])
    return corrected


def contains_unresolved_value(values: list[str]) -> bool:
    return any(value_or_unknown(value).lower() == UNKNOWN for value in values)


def contains_unknown_value(values: list[str]) -> bool:
    return contains_unresolved_value(values)


def review_field_pairs(
    details: DocumentDetails,
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
) -> list[tuple[str, str]]:
    labels = enabled_field_labels(
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
    values = default_review_values(
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
    return list(zip(labels, values, strict=True))


def missing_field_labels(fields: list[tuple[str, str]]) -> list[str]:
    return [
        label
        for label, value in fields
        if value_or_unknown(value).lower() == UNKNOWN
    ]


def field_dialog_script(
    *,
    title: str,
    message: str,
    fields: list[tuple[str, str]],
) -> str:
    label_rows = []
    field_rows = []
    read_values = []

    for index, (label, value) in enumerate(fields, start=1):
        y = (len(fields) - index) * 34
        label_rows.append(
            f'set label{index} to ca\'s NSTextField\'s '
            f'labelWithString:{applescript.literal(label + ":")}\n'
            f'label{index}\'s setFrame:(ca\'s NSMakeRect(0, {y + 3}, 130, 20))\n'
            f'accessoryView\'s addSubview:label{index}'
        )
        field_rows.append(
            f'set field{index} to ca\'s NSTextField\'s alloc()\'s '
            f'initWithFrame:(ca\'s NSMakeRect(142, {y}, 300, 24))\n'
            f'field{index}\'s setStringValue:{applescript.literal(value)}\n'
            f'accessoryView\'s addSubview:field{index}'
        )
        read_values.append(f'text of field{index}')

    values_expression = " & linefeed & ".join(read_values)
    accessory_height = max(24, len(fields) * 34)

    return (
        'use framework "AppKit"\n'
        'use scripting additions\n'
        'set ca to current application\n'
        'set alert to ca\'s NSAlert\'s alloc()\'s init()\n'
        f'alert\'s setMessageText:{applescript.literal(title)}\n'
        f'alert\'s setInformativeText:{applescript.literal(message)}\n'
        'alert\'s addButtonWithTitle:"Save"\n'
        'alert\'s addButtonWithTitle:"Skip"\n'
        'alert\'s addButtonWithTitle:"Exit review"\n'
        f'set accessoryView to ca\'s NSView\'s alloc()\'s '
        f'initWithFrame:(ca\'s NSMakeRect(0, 0, 452, {accessory_height}))\n'
        + "\n".join(label_rows)
        + "\n"
        + "\n".join(field_rows)
        + "\n"
        'alert\'s setAccessoryView:accessoryView\n'
        'set response to alert\'s runModal()\n'
        'if response = 1000 then\n'
        f'  return "Save" & linefeed & {values_expression}\n'
        'else if response = 1001 then\n'
        '  return "Skip"\n'
        'else\n'
        '  return "Exit review"\n'
        'end if\n'
    )


def review_preview_path(item: RenameResult) -> Path | None:
    for path in (item.final_path, item.original_path):
        if path and path.is_file():
            return path
    return None


def open_review_preview(item: RenameResult) -> None:
    if sys.platform != "darwin":
        return

    path = review_preview_path(item)
    if path is None:
        return

    try:
        subprocess.Popen(
            ["/usr/bin/open", "-a", "Preview", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass


def prompt_for_correction(
    item: RenameResult,
    *,
    position: int = 1,
    total: int = 1,
    include_date: bool,
    include_sender: bool,
    include_name: bool,
    include_type: bool,
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> DocumentDetails | None | str:
    fields = review_field_pairs(
        item.details,
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
    if not fields:
        return None

    filename = item.final_path.name if item.final_path else "Unknown.pdf"
    missing = missing_field_labels(fields)
    missing_text = ", ".join(missing) if missing else "None"
    detected = (
        "Detected fields:\n"
        f"Date: {item.details.document_date}\n"
        f"Sender: {item.details.sender}\n"
        f"Recipient: {item.details.recipient}\n"
        f"Subject: {item.details.patient_name}\n"
        f"Reference: {item.details.reference}\n"
        f"Document type: {item.details.document_type}\n"
        f"Amount: {item.details.amount}\n"
        f"Location: {item.details.location}\n"
        f"Status: {item.details.status}"
    )
    message = (
        f"Review {position} of {total}\n\n"
        f"Current filename: {filename}\n"
        f"Missing fields: {missing_text}\n\n"
        "Edit the enabled filename fields below. Blank fields must be filled "
        "before saving."
    )

    script = field_dialog_script(
        title="Review PDF filename",
        message=f"{message}\n\n{detected}",
        fields=fields,
    )
    output = run_osascript(script)
    if not output:
        return None

    button, _, answer = output.partition("\n")
    if button == "Exit review":
        return EXIT_REVIEW
    if button != "Save":
        return None

    values = [part.strip() for part in answer.splitlines()]
    if len(values) != len(fields):
        return None
    if contains_unresolved_value(values):
        return None
    return correction_from_values(
        item.details,
        values,
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


def apply_corrected_details(
    item: RenameResult,
    corrected: DocumentDetails,
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
) -> Path | None:
    if item.final_path is None:
        return None

    base_name = build_filename(
        corrected.patient_name,
        corrected.document_type,
        corrected.document_date,
        corrected.sender,
        corrected.recipient,
        corrected.reference,
        corrected.amount,
        corrected.location,
        corrected.status,
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
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> int:
    if dry_run or not review_summary_dialog(summary):
        return 0

    corrected_count = 0
    total = len(summary.review_items)
    for index, item in enumerate(summary.review_items, start=1):
        open_review_preview(item)
        corrected = prompt_for_correction(
            item,
            position=index,
            total=total,
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
        if corrected == EXIT_REVIEW:
            break
        if corrected is None:
            continue

        corrected_path = apply_corrected_details(
            item,
            corrected,
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
