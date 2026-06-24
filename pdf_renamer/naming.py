import re
from pathlib import Path
from typing import Optional

from .config import UNKNOWN


def build_filename(patient_name: str, document_type: str) -> str:
    if document_type == UNKNOWN:
        document_type = "Unknown"
    return f"{patient_name} - {document_type}"


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
