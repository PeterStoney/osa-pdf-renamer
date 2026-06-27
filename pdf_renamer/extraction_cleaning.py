import re

from .config import UNKNOWN
from .extraction_dates import parse_date_value


def clean_name(name: str) -> str:
    if not isinstance(name, str):
        return ""

    # Remove common titles.
    name = re.sub(
        r"\b(Dr|Mr|Mrs|Ms|Miss|Prof|Professor)\b\.?,?",
        " ",
        name,
        flags=re.IGNORECASE,
    )

    # Remove anything in brackets.
    name = re.sub(r"\(.*?\)", " ", name)

    # Keep only letters, spaces, apostrophes and hyphens.
    name = re.sub(r"[^A-Za-z\s'\-]", " ", name)

    # Collapse multiple spaces.
    name = re.sub(r"\s+", " ", name).strip()

    # Title-case for filenames.
    return name.title()


def valid_name(name: str) -> bool:
    name = clean_name(name)

    if not name:
        return False

    if name.lower() == UNKNOWN:
        return False

    # Full names are usually 2-5 words, allowing for middle names and compound surnames.
    if len(parts := name.split()) < 2 or len(parts) > 5:
        return False

    # Reject obviously non-name outputs.
    if any(len(part) < 2 for part in parts):
        return False

    bad_words = {
        "patient", "doctor", "clinic", "hospital", "orthopaedics",
        "radiology", "pathology", "email", "phone", "address",
        "booking", "operation", "surgeon", "unknown", "medical",
        "provider", "medicare", "mobile", "fax", "dob", "birth",
    }

    if any(part.lower() in bad_words for part in parts):
        return False

    return True


def clean_sender(sender: str) -> str:
    if not isinstance(sender, str):
        return UNKNOWN

    sender = re.sub(r"[\x00-\x1f/:\\]", " ", sender)
    sender = re.sub(
        r"\b(?:ABN|ACN|Phone|Fax|Email|Tel)\b.*$",
        "",
        sender,
        flags=re.IGNORECASE,
    )
    sender = re.sub(r"\s+", " ", sender).strip(" .,-_")
    if not sender or sender.lower() == UNKNOWN:
        return UNKNOWN
    return sender[:100]


def valid_sender(sender: str) -> bool:
    sender = clean_sender(sender)
    if sender == UNKNOWN:
        return False
    if len(sender) < 3:
        return False
    if len(sender.split()) == 1 and sender.isupper():
        return False
    if parse_date_value(sender) != UNKNOWN:
        return False
    bad_words = {
        "patient",
        "dob",
        "date",
        "invoice date",
        "total",
        "amount",
        "findings",
        "clinical",
        "dear",
        "re",
        "unknown",
    }
    if sender.lower() in bad_words:
        return False
    if re.fullmatch(r"[\d\s.,$-]+", sender):
        return False
    return True


def clean_document_type(document_type: str) -> str:
    if not isinstance(document_type, str):
        return UNKNOWN

    document_type = re.sub(r"[\x00-\x1f/:\\]", " ", document_type)
    document_type = re.sub(r"\s+", " ", document_type).strip(" .-_")

    generic_types = {
        "",
        "clinical document",
        "clinical report",
        "unknown",
        "unknown document type",
        "document",
        "exam report",
        "examination report",
        "form",
        "imaging report",
        "letter",
        "medical document",
        "medical report",
        "mri report",
        "ct report",
        "ultrasound report",
        "x-ray report",
        "xray report",
        "n/a",
        "none",
        "pdf",
        "report",
        "scan",
        "scanned document",
        "unspecified",
    }

    if document_type.lower() in generic_types:
        return UNKNOWN

    return document_type[:120].strip()


def strip_unknown_alternative(value: str) -> str:
    if not isinstance(value, str):
        return value
    value = re.sub(r"\s+or\s+unknown\b", "", value, flags=re.IGNORECASE)
    return value.strip()


def format_imaging_document_type(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .:-")
    match = re.fullmatch(
        r"(MRI|CT|US|ULTRASOUND|XRAY|X-RAY|X RAY)\s+"
        r"(?:OF\s+)?([A-Z][A-Z0-9 /,&+\-]{2,70})",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return UNKNOWN

    modality_names = {
        "MRI": "MRI",
        "CT": "CT",
        "US": "Ultrasound",
        "ULTRASOUND": "Ultrasound",
        "XRAY": "X-ray",
        "X-RAY": "X-ray",
        "X RAY": "X-ray",
    }
    modality = modality_names[re.sub(r"\s+", " ", match.group(1).upper())]
    subject = match.group(2)
    subject = re.sub(r"\bRT\b", "RIGHT", subject, flags=re.IGNORECASE)
    subject = re.sub(r"\bLT\b", "LEFT", subject, flags=re.IGNORECASE)
    subject = re.sub(
        r"\b(?:REPORT|EXAMINATION|STUDY)\b",
        "",
        subject,
        flags=re.IGNORECASE,
    )
    subject = re.sub(r"\s+", " ", subject).strip(" ,-")
    if not subject:
        return UNKNOWN
    return f"{modality} {subject.lower()}"


def likely_title_from_evidence(evidence: str) -> str:
    evidence = re.sub(r"\s+", " ", evidence).strip(" .:-")
    if not evidence:
        return UNKNOWN

    imaging_type = format_imaging_document_type(evidence)
    if imaging_type != UNKNOWN:
        return imaging_type

    if len(evidence) > 80:
        return UNKNOWN
    if re.search(r"[.!?;]", evidence):
        return UNKNOWN
    if re.search(
        r"\b(?:dear|dob|date|patient|referrer|doctor|please|reviewed|attached)\b",
        evidence,
        flags=re.IGNORECASE,
    ):
        return UNKNOWN

    cleaned = clean_document_type(evidence)
    if cleaned != UNKNOWN and cleaned[:1].islower():
        cleaned = cleaned[:1].upper() + cleaned[1:]
    return cleaned if cleaned != UNKNOWN else UNKNOWN


def extract_visible_document_title(text: str) -> str:
    """Read a concise, explicit document title from the top of the page."""
    readable_text = text.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0]
    title_aliases = {
        "tax invoice": "Tax Invoice",
        "invoice": "Invoice",
        "receipt": "Receipt",
        "statement": "Statement",
        "quote": "Quote",
        "purchase order": "Purchase order",
        "clinical note": "Clinical note",
        "consultation note": "Consultation note",
        "initial physiotherapy assessment": "Initial physiotherapy assessment",
        "physiotherapy assessment": "Physiotherapy assessment",
    }

    for raw_line in readable_text.splitlines()[:30]:
        line = re.sub(r"\s+", " ", raw_line).strip(" .:-")
        normalized = line.lower()
        if normalized in title_aliases:
            return title_aliases[normalized]

    return UNKNOWN


def recurring_form_type_from_model(document_type: str) -> str:
    normalized = re.sub(r"\s+", " ", document_type).lower()
    if normalized in {"op booking", "operation booking sheet"}:
        return "OP booking"
    if normalized in {
        "op consent",
        "operation consent",
        "operation procedure consent form",
        "operation/procedure consent form",
        "consent for operation",
    }:
        return "OP consent"
    if normalized in {"op stickers", "operation stickers"}:
        return "OP stickers"
    if normalized in {"reg form", "registration form"}:
        return "Reg form"
    return UNKNOWN


def is_sender_based_document_type(document_type: str) -> bool:
    return document_type.lower() in {
        "invoice",
        "tax invoice",
        "receipt",
        "statement",
        "quote",
        "purchase order",
    }
