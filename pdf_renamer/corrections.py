import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from .config import APP_VERSION, CORRECTIONS_PATH, UNKNOWN
from .models import DocumentDetails


MAX_CORRECTIONS = 200


def ocr_hash(ocr_text: str) -> str:
    return hashlib.sha256(ocr_text.encode("utf-8")).hexdigest()


def details_payload(details: DocumentDetails) -> dict:
    return {
        "date": details.document_date,
        "sender": details.sender,
        "person_subject": details.patient_name,
        "document_type": details.document_type,
    }


def load_corrections(path: Path = CORRECTIONS_PATH) -> list[dict]:
    if not path.is_file():
        return []

    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def write_corrections(records: list[dict], path: Path = CORRECTIONS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(
        json.dumps(record, ensure_ascii=False, sort_keys=True)
        for record in records[-MAX_CORRECTIONS:]
    )
    path.write_text(body + ("\n" if body else ""), encoding="utf-8")


def save_correction(
    *,
    original_path: Path,
    reviewed_path: Path,
    corrected_path: Path,
    ocr_text: str,
    detected: DocumentDetails,
    corrected: DocumentDetails,
    path: Path = CORRECTIONS_PATH,
) -> None:
    source_hash = ocr_hash(ocr_text)
    record = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "app_version": APP_VERSION,
        "source_hash": source_hash,
        "original_filename": original_path.name,
        "reviewed_filename": reviewed_path.name,
        "corrected_filename": corrected_path.name,
        "detected": details_payload(detected),
        "corrected": details_payload(corrected),
        # Private local learning data. Do not commit this file to git.
        "ocr_text": ocr_text,
    }

    records = [
        existing
        for existing in load_corrections(path)
        if existing.get("source_hash") != source_hash
    ]
    records.append(record)
    write_corrections(records, path)


def value_or_unknown(value: str) -> str:
    value = value.strip()
    return value if value else UNKNOWN
