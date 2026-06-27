import re

from .config import UNKNOWN
from .extraction_cleaning import clean_name, clean_sender, valid_name, valid_sender
from .extraction_dates import extract_document_date
from .extraction_types import detect_common_document_type
from .extraction_vision import structured_vision_lines, primary_vision_text, normalize_labeled_name_value
from .models import DocumentDetails


def extract_primary_labeled_name(text: str) -> str:
    """Read explicit name fields from the primary Vision OCR when available."""
    primary_text = primary_vision_text(text)

    surname_match = re.search(
        r"(?im)^\s*Surname\s*:\s*[._-]*\s*"
        r"([A-Za-z0-9][A-Za-z0-9' -]*)\s*$",
        primary_text,
    )
    if not surname_match:
        surname_match = re.search(
            r"(?im)^\s*Surname\s*:\s*[._]*\s*$\n"
            r"\s*([A-Za-z][A-Za-z' -]*)\s*$",
            primary_text,
        )
    if not surname_match:
        surname_match = re.search(
            r"(?im)^Surname\s*:\s*([A-Za-z][A-Za-z' -]*)\s*$",
            text.split(
                "===== TARGETED OSA NAME OCR =====",
                1,
            )[-1],
        )
    first_name_match = re.search(
        r"(?im)^\s*(?:First Name|Given Name)\s*:\s*"
        r"[._-]*\s*"
        r"([A-Za-z][A-Za-z' -]*)\s*$",
        primary_text,
    )
    if not first_name_match:
        first_name_match = re.search(
            r"(?im)^\s*(?:First Name|Given Name)\s*:\s*_*\s*$\n"
            r"\s*([A-Za-z][A-Za-z' -]*)\s*$",
            primary_text,
        )
    if not first_name_match:
        first_name_match = re.search(
            r"(?im)^First Name\s*:\s*"
            r"([A-Za-z][A-Za-z' -]*)\s*$",
            text.split(
                "===== TARGETED OSA NAME OCR =====",
                1,
            )[-1],
        )

    if not first_name_match:
        return UNKNOWN

    first_name = normalize_labeled_name_value(first_name_match.group(1))
    if surname_match:
        surname = normalize_labeled_name_value(surname_match.group(1))
    else:
        email_match = re.search(
            r"(?im)^\s*Email\s*:\s*([^\n@]+)@",
            primary_text,
        )
        if not email_match:
            return UNKNOWN

        local_part = re.sub(
            r"[^A-Za-z0-9]",
            "",
            email_match.group(1),
        ).lower()
        normalized_first = re.sub(
            r"[^a-z]",
            "",
            first_name.lower(),
        )
        if not local_part.startswith(normalized_first):
            return UNKNOWN

        surname = re.sub(
            r"[^a-z]",
            "",
            local_part[len(normalized_first):],
        )
        if len(surname) < 2:
            return UNKNOWN

    name = clean_name(f"{first_name} {surname}")
    return name if valid_name(name) else UNKNOWN


def extract_primary_sticker_name(text: str) -> str:
    """Read common hospital patient-label name layouts from Vision OCR."""
    primary_text = primary_vision_text(text)
    title = r"(?:DR|MR|MRS|MS|MISS)"

    same_line_match = re.search(
        rf"(?im)^\s*([A-Z][A-Z' -]+),\s*{title}\.?\s+"
        r"([A-Za-z][A-Za-z' -]*)\s*$",
        primary_text,
    )
    if same_line_match:
        name = clean_name(
            f"{same_line_match.group(2)} {same_line_match.group(1)}"
        )
        if valid_name(name):
            return name

    split_line_match = re.search(
        rf"(?m)^\s*([A-Z][A-Z' -]+)\s*$\n"
        rf"\s*{title}\.?\s+([A-Z][A-Z' -]+)\s*$",
        primary_text,
    )
    if split_line_match:
        name = clean_name(
            f"{split_line_match.group(2)} {split_line_match.group(1)}"
        )
        if valid_name(name):
            return name

    return UNKNOWN


def extract_primary_radiology_name(text: str) -> str:
    """Read a patient heading formatted as NAME (DOB) on radiology reports."""
    primary_text = primary_vision_text(text)
    normalized = primary_text.lower()

    if "radiology" not in normalized or "patient id" not in normalized:
        return UNKNOWN

    match = re.search(
        r"(?m)^\s*([A-Z][A-Z' -]{2,})\s*"
        r"\(\s*\d{1,2}/\d{1,2}/\d{2,4}\s*\)"
        r"(?=\s*$|\s{2,}(?:Patient ID|Service Date|UR No)\b)",
        primary_text,
    )
    if not match:
        return UNKNOWN

    name = clean_name(match.group(1))
    return name if valid_name(name) else UNKNOWN


def extract_sender(text: str) -> tuple[str, str]:
    """Extract the document sender/source from obvious letterhead lines."""
    readable_text = text.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0]
    raw_lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in readable_text.splitlines()
    ]
    lines = [line for line in raw_lines if line]

    labelled_patterns = (
        r"(?im)^\s*(?:From|Sender|Provider|Practice|Clinic|Facility|"
        r"Organisation|Organization|Radiology provider|Supplier)\s*:\s*"
        r"([^\n]{3,100})$",
        r"(?im)^\s*(?:Issued by|Prepared by|Sent by)\s*:\s*"
        r"([^\n]{3,100})$",
    )
    for pattern in labelled_patterns:
        match = re.search(pattern, readable_text)
        if not match:
            continue
        sender = clean_sender(match.group(1))
        if valid_sender(sender):
            return sender, match.group(0).strip()

    skip_re = re.compile(
        r"\b("
        r"embedded pdf text|macos vision|structured vision|"
        r"patient|dob|date|invoice date|invoice number|bill to|"
        r"dear|re\s*:|findings|clinical|examination|procedure|"
        r"phone|fax|email|www|@"
        r")\b",
        flags=re.IGNORECASE,
    )

    for line in lines[:8]:
        if skip_re.search(line):
            continue
        sender = clean_sender(line)
        if valid_sender(sender):
            return sender, line

    return UNKNOWN, ""


def extract_explicit_patient_name(text: str) -> str:
    """Extract names from general patient-labelled layouts."""
    readable_text = text.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0]
    title = r"(?:DR|MR|MRS|MS|MISS|PROF)"

    patterns = (
        rf"(?im)^\s*Re\s*:\s*{title}\.?\s+"
        r"([A-Za-z][A-Za-z' -]{2,60}?)(?:\s*\(|\s+-|\s*$)",
        r"(?im)^\s*Patient Name\s*:\s*"
        r"([A-Za-z][A-Za-z' -]+,\s*[A-Za-z][A-Za-z' -]+?)"
        r"(?=\s{2,}[A-Z][A-Za-z ]+\s*:|\s*$)",
        r"(?im)^\s*Patient Name\s*:\s*"
        r"([A-Za-z][A-Za-z' -]+,\s*[A-Za-z][A-Za-z' -]+)\s*$",
        r"(?im)^\s*Patient Name\s*:\s*"
        r"([A-Za-z][A-Za-z' -]{2,60})\s*$",
        r"(?im)^\s*Patient\s*:\s*"
        r"([A-Za-z][A-Za-z' -]{2,60})\s*$",
        rf"(?im)^\s*Name\s*:\s*{title}\.?\s+"
        r"([A-Za-z][A-Za-z' -]{2,60})\s*$",
        r"(?im)^\s*Name\s*:\s*"
        r"([A-Za-z][A-Za-z' -]{2,60})\s*$",
        rf"(?im)^\s*Patient\b.*?,\s*([A-Z][A-Z' -]+),\s*"
        rf"{title}\.?\s+([A-Za-z][A-Za-z' -]+)\s*$",
    )

    for pattern in patterns:
        match = re.search(pattern, readable_text)
        if not match:
            continue

        if len(match.groups()) == 2:
            candidate = f"{match.group(2)} {match.group(1)}"
        else:
            candidate = match.group(1)
            if "," in candidate:
                surname, given = candidate.split(",", 1)
                candidate = f"{given} {surname}"

        name = clean_name(candidate)
        if valid_name(name):
            return name

    return UNKNOWN


def extract_structured_re_name(text: str) -> str:
    """Use Vision coordinates when a referral value sits right of RE:."""
    lines = structured_vision_lines(text)
    title_pattern = re.compile(
        r"^(?:DR|MR|MRS|MS|MISS|PROF)\.?\s+(.+)$",
        re.IGNORECASE,
    )

    for label in lines:
        if not re.fullmatch(r"\s*RE\s*:\s*", str(label.get("text", "")), re.I):
            continue

        label_y = float(label.get("y", 0.0))
        label_x = float(label.get("x", 0.0))
        candidates = []
        for line in lines:
            line_x = float(line.get("x", 0.0))
            line_y = float(line.get("y", 0.0))
            if line_x <= label_x or abs(line_y - label_y) > 0.012:
                continue

            match = title_pattern.match(str(line.get("text", "")).strip())
            if match:
                candidates.append((line_x, match.group(1)))

        if candidates:
            _, candidate = min(candidates)
            name = clean_name(candidate)
            if valid_name(name):
                return name

    return UNKNOWN


def deterministic_document_details(text: str) -> DocumentDetails:
    document_type = detect_common_document_type(text)
    document_date, date_evidence = extract_document_date(text)
    sender, sender_evidence = extract_sender(text)
    if document_type == "OP stickers":
        sender = UNKNOWN
        sender_evidence = ""
    patient_name = UNKNOWN

    if document_type == "Reg form":
        patient_name = extract_primary_labeled_name(text)
    elif document_type == "Referral":
        patient_name = extract_structured_re_name(text)
    elif document_type == "OP stickers":
        patient_name = extract_primary_sticker_name(text)

    if patient_name == UNKNOWN:
        patient_name = extract_primary_radiology_name(text)
    if patient_name == UNKNOWN and document_type != "Reg form":
        patient_name = extract_explicit_patient_name(text)

    return DocumentDetails(
        patient_name=patient_name,
        sender=sender,
        document_type=document_type,
        document_date=document_date,
        name_evidence=patient_name if patient_name != UNKNOWN else "",
        sender_evidence=sender_evidence,
        type_evidence=document_type if document_type != UNKNOWN else "",
        date_evidence=date_evidence,
        confidence=1.0 if (
            patient_name != UNKNOWN
            and document_type != UNKNOWN
            and document_date != UNKNOWN
        ) else 0.0,
    )
