import re
from pathlib import Path
from typing import Optional

from .config import UNKNOWN


def build_filename(
    patient_name: str,
    document_type: str,
    document_date: str = UNKNOWN,
    sender: str = UNKNOWN,
    recipient: str = UNKNOWN,
    reference: str = UNKNOWN,
    amount: str = UNKNOWN,
    location: str = UNKNOWN,
    status: str = UNKNOWN,
    *,
    include_date: bool = True,
    include_sender: bool = False,
    include_name: bool = True,
    include_type: bool = True,
    include_recipient: bool = False,
    include_reference: bool = False,
    include_amount: bool = False,
    include_location: bool = False,
    include_status: bool = False,
) -> str:
    if document_type == UNKNOWN:
        document_type = "Unknown"
    parts = []
    if include_date and document_date != UNKNOWN:
        parts.append(document_date)
    if include_sender and sender != UNKNOWN:
        parts.append(sender)
    if include_recipient and recipient != UNKNOWN:
        parts.append(recipient)
    if include_location and location != UNKNOWN:
        parts.append(location)
    if include_name:
        parts.append(patient_name)
    if include_reference and reference != UNKNOWN:
        parts.append(reference)
    if include_type:
        parts.append(document_type)
    if include_amount and amount != UNKNOWN:
        parts.append(amount)
    if include_status and status != UNKNOWN:
        parts.append(status)
    return " - ".join(parts) if parts else "Unknown"


def unique_path(
    folder: Path,
    base_name: str,
    current_path: Optional[Path] = None,
) -> Path:
    base_name = re.sub(r"[\x00-\x1f/:\\]", " ", base_name)
    base_name = re.sub(r"\s+", " ", base_name).strip(" .-_") or UNKNOWN

    path = folder / f"{base_name}.pdf"
    counter = 1
    while path.exists():
        if current_path and path.resolve() == current_path.resolve():
            return path
        path = folder / f"{base_name} ({counter}).pdf"
        counter += 1

    return path
