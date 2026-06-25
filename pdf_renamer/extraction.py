import json
import re

import requests
from .config import OLLAMA_MODEL, OLLAMA_URL, UNKNOWN
from .models import DocumentDetails


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


MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


def normalize_year(year: str) -> int:
    value = int(year)
    if value < 100:
        return 2000 + value if value < 50 else 1900 + value
    return value


def format_document_date(day: int, month: int, year: int) -> str:
    return f"{day:02d}-{month:02d}-{year % 100:02d}"


def parse_date_value(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()

    numeric = re.search(
        r"\b([0-3]?\d)[/.-]([01]?\d)[/.-](\d{2,4})\b",
        value,
    )
    if numeric:
        day = int(numeric.group(1))
        month = int(numeric.group(2))
        year = normalize_year(numeric.group(3))
        if 1 <= day <= 31 and 1 <= month <= 12:
            return format_document_date(day, month, year)

    iso = re.search(r"\b(\d{4})-([01]?\d)-([0-3]?\d)\b", value)
    if iso:
        year = int(iso.group(1))
        month = int(iso.group(2))
        day = int(iso.group(3))
        if 1 <= day <= 31 and 1 <= month <= 12:
            return format_document_date(day, month, year)

    month_first = re.search(
        r"\b("
        + "|".join(MONTHS)
        + r")\.?\s+([0-3]?\d)(?:st|nd|rd|th)?[,]?\s+(\d{2,4})\b",
        value,
        flags=re.IGNORECASE,
    )
    if month_first:
        month = MONTHS[month_first.group(1).lower()]
        day = int(month_first.group(2))
        year = normalize_year(month_first.group(3))
        if 1 <= day <= 31:
            return format_document_date(day, month, year)

    day_first = re.search(
        r"\b([0-3]?\d)(?:st|nd|rd|th)?\s+("
        + "|".join(MONTHS)
        + r")\.?[,]?\s+(\d{2,4})\b",
        value,
        flags=re.IGNORECASE,
    )
    if day_first:
        day = int(day_first.group(1))
        month = MONTHS[day_first.group(2).lower()]
        year = normalize_year(day_first.group(3))
        if 1 <= day <= 31:
            return format_document_date(day, month, year)

    return UNKNOWN


def extract_document_date(text: str) -> tuple[str, str]:
    """Extract the document/event date, avoiding DOB and export dates."""
    readable_text = text.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0]

    labels = (
        "service date",
        "study date",
        "exam date",
        "examination date",
        "procedure date",
        "performed date",
        "appointment date",
        "operation date",
        "surgery date",
        "consultation date",
        "requested date",
        "request date",
        "collection date",
        "visit date",
        "date of service",
    )

    for label in labels:
        pattern = (
            rf"(?im)\b{re.escape(label)}\s*:\s*"
            r"([^\n]{4,100})"
        )
        match = re.search(pattern, readable_text)
        if not match:
            continue
        evidence = f"{label}: {match.group(1).strip()}"
        document_date = parse_date_value(match.group(1))
        if document_date != UNKNOWN:
            return document_date, evidence

    # Fallback for a generic letter/form date near the top of a document.
    top_lines = "\n".join(readable_text.splitlines()[:12])
    generic = re.search(
        r"(?im)^\s*(?:date)\s*:\s*([^\n]{4,80})$",
        top_lines,
    )
    if generic:
        document_date = parse_date_value(generic.group(1))
        if document_date != UNKNOWN:
            return document_date, f"Date: {generic.group(1).strip()}"

    return UNKNOWN, ""


def primary_vision_text(text: str) -> str:
    marker = "===== MACOS VISION OCR (PRIMARY) ====="
    if marker not in text:
        return text.split(
            "===== STRUCTURED VISION OCR LINES =====",
            1,
        )[0]

    primary = text.split(marker, 1)[1]
    return primary.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0].strip()


def structured_vision_lines(text: str):
    marker = "===== STRUCTURED VISION OCR LINES ====="
    if marker not in text:
        return []

    raw = text.split(marker, 1)[1].strip()
    try:
        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return []


def normalize_labeled_name_value(value: str) -> str:
    """Repair conservative letter-like OCR errors inside labelled names."""
    value = re.sub(r"^[\s._-]+|[\s._-]+$", "", value)
    translation = str.maketrans({"0": "O", "1": "I", "5": "S"})
    tokens = []
    for token in value.split():
        if re.search(r"[A-Za-z]", token):
            token = token.translate(translation)
        tokens.append(token)
    return " ".join(tokens)


def explicit_imaging_type(text: str) -> str:
    """Normalize a specific imaging heading without guessing its body part."""
    primary_text = primary_vision_text(text)
    modality_names = {
        "MRI": "MRI",
        "CT": "CT",
        "US": "Ultrasound",
        "ULTRASOUND": "Ultrasound",
        "XRAY": "X-ray",
        "X-RAY": "X-ray",
        "X RAY": "X-ray",
    }

    def normalize_subject(subject: str) -> str:
        subject = re.sub(
            r"\b(?:REPORT|EXAMINATION|STUDY)\b",
            "",
            subject,
            flags=re.IGNORECASE,
        )
        subject = re.sub(
            r"\bRT\b",
            "RIGHT",
            subject,
            flags=re.IGNORECASE,
        )
        subject = re.sub(
            r"\bLT\b",
            "LEFT",
            subject,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", subject).strip(" ,-")

    def format_imaging_type(modality_token: str, subject: str) -> str:
        modality = modality_names[
            re.sub(r"\s+", " ", modality_token.upper())
        ]
        subject = normalize_subject(subject)
        if (
            not subject
            or "," in subject
            or ";" in subject
            or re.search(
                r"\b(?:MRI|CT|US|ULTRASOUND|XRAY|X-RAY)\b",
                subject,
                flags=re.IGNORECASE,
            )
        ):
            return UNKNOWN
        return f"{modality} {subject.lower()}"

    raw_lines = primary_text.splitlines()
    for index, raw_line in enumerate(raw_lines):
        line = re.sub(r"\s+", " ", raw_line).strip(" :-.")
        labelled_match = re.search(
            r"\b(?:PROCEDURE DESCRIPTION|EXAMINATION|STUDY)\s*:\s*"
            r"(MRI|CT|US|ULTRASOUND|XRAY|X-RAY|X RAY)\s+"
            r"(?:OF\s+)?([A-Z][A-Z0-9 /,&+\-]{2,70})",
            line,
            flags=re.IGNORECASE,
        )
        if labelled_match:
            document_type = format_imaging_type(
                labelled_match.group(1),
                labelled_match.group(2),
            )
            if document_type != UNKNOWN:
                return document_type

        match = re.fullmatch(
            r"(MRI|CT|US|ULTRASOUND|XRAY|X-RAY|X RAY)\s+"
            r"(?:OF\s+)?([A-Z][A-Z0-9 /,&+\-]{2,70})",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        previous_line = ""
        for previous in reversed(raw_lines[:index]):
            previous_line = previous.strip()
            if previous_line:
                break
        is_explicit_field = bool(
            re.fullmatch(
                r"(?:EXAMINATION|PROCEDURE DESCRIPTION|STUDY)\s*:?",
                previous_line,
                flags=re.IGNORECASE,
            )
        )
        if raw_line != raw_line.upper() and not is_explicit_field:
            continue

        document_type = format_imaging_type(
            match.group(1),
            match.group(2),
        )
        if document_type != UNKNOWN:
            return document_type

    return UNKNOWN


def detect_common_document_type(text: str) -> str:
    """Detect repetitive forms locally so their filenames stay consistent."""
    normalized = re.sub(r"\s+", " ", text).lower()
    primary_text = primary_vision_text(text)

    if "operation booking sheet" in normalized:
        return "OP booking"

    consent_markers = (
        "informed consent to treatment",
        "consent for operation",
        "consent for operation / procedure",
        "consent for operation procedure",
    )
    if any(marker in normalized for marker in consent_markers):
        return "OP consent"

    if "gp chronic condition management plan" in normalized:
        return "Chronic condition management plan"

    if (
        "dear " in normalized
        and re.search(r"\bre\s*:", normalized)
        and re.search(
            r"\b(?:thank you|thanks(?: very much)?) for seeing\b",
            normalized,
        )
    ):
        return "Referral"

    if "doppler venous ultrasound" in normalized:
        return "Doppler venous ultrasound"

    imaging_type = explicit_imaging_type(text)
    if imaging_type != UNKNOWN:
        return imaging_type

    examination_match = re.search(
        r"(?im)^\s*Examination\s*:\s*\n\s*([^\n]+)",
        primary_text,
    )
    if examination_match:
        examination = examination_match.group(1).strip()
        examination_upper = examination.upper()

        if (
            "CT LUMBOSACRAL SPINE" in examination_upper
            and "CT HIP LEFT" in examination_upper
        ):
            return "CT lumbosacral spine and left hip"

        if (
            "XRAY PELVIS" in examination_upper
            and "XRAY RIGHT HIP" in examination_upper
        ):
            return "X-ray pelvis and right hip"

    osa_header_markers = (
        "orthopaedics sports arthroplasty",
        "orthopaedics sports arthroplasty pty ltd",
        "osa unit trust",
        "stoney.admin@osa.melbourne",
        "www.osa.melbourne",
    )
    has_osa_header = any(
        marker in normalized
        for marker in osa_header_markers
    )

    if (
        has_osa_header
        and "personal details" in normalized
        and re.search(r"\bemergency conta(?:ct)?\b", normalized)
        and ("account details" in normalized or "medicare number" in normalized)
    ):
        return "Reg form"

    implant_markers = (
        "acetabular",
        "bone cement",
        "bone screw",
        "femoral stem",
        "femoral head",
        "hip system",
        "implant",
        "patella",
        "polyethylene",
        "tibial",
        "total knee",
        "triathlon",
    )
    label_markers = (
        " lot ",
        " lot:",
        " ref ",
        " ref:",
        "sterile",
        "stryker",
    )
    patient_label_markers = (
        "dob:",
        "gender",
        "m/care:",
        "medicare:",
        "ur:",
        "adm:",
        "adm no",
        "mrn:",
        "sex:",
    )

    implant_score = sum(marker in normalized for marker in implant_markers)
    label_score = sum(marker in normalized for marker in label_markers)
    patient_score = sum(
        marker in normalized
        for marker in patient_label_markers
    )

    if (
        implant_score >= 2
        and label_score >= 2
        and patient_score >= 2
    ):
        return "OP stickers"

    return UNKNOWN


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
        document_type=document_type,
        document_date=document_date,
        name_evidence=patient_name if patient_name != UNKNOWN else "",
        type_evidence=document_type if document_type != UNKNOWN else "",
        date_evidence=date_evidence,
        confidence=1.0 if (
            patient_name != UNKNOWN
            and document_type != UNKNOWN
            and document_date != UNKNOWN
        ) else 0.0,
    )


def parse_model_response(raw: str) -> DocumentDetails:
    try:
        data = json.loads(raw)
        name = data.get("patient_name", UNKNOWN)
        document_type = data.get("document_type", UNKNOWN)
        document_date = data.get("document_date", UNKNOWN)
        name_evidence = data.get("name_evidence", "")
        type_evidence = data.get("type_evidence", "")
        date_evidence = data.get("date_evidence", "")
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
    except Exception:
        name_match = re.search(r'"patient_name"\s*:\s*"([^"]+)"', raw)
        type_match = re.search(r'"document_type"\s*:\s*"([^"]+)"', raw)
        name_evidence_match = re.search(
            r'"name_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        type_evidence_match = re.search(
            r'"type_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        name = name_match.group(1) if name_match else UNKNOWN
        document_type = type_match.group(1) if type_match else UNKNOWN
        date_match = re.search(r'"document_date"\s*:\s*"([^"]+)"', raw)
        document_date = date_match.group(1) if date_match else UNKNOWN
        name_evidence = (
            name_evidence_match.group(1)
            if name_evidence_match
            else ""
        )
        type_evidence = (
            type_evidence_match.group(1)
            if type_evidence_match
            else ""
        )
        date_evidence_match = re.search(
            r'"date_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        date_evidence = (
            date_evidence_match.group(1)
            if date_evidence_match
            else ""
        )
        confidence = 0.0

    parsed_document_date = parse_date_value(str(document_date))
    if parsed_document_date == UNKNOWN and str(document_date).lower() == UNKNOWN:
        parsed_document_date = UNKNOWN

    return DocumentDetails(
        patient_name=clean_name(name),
        document_type=clean_document_type(document_type),
        document_date=parsed_document_date,
        raw_model_response=raw,
        name_evidence=str(name_evidence).strip(),
        type_evidence=str(type_evidence).strip(),
        date_evidence=str(date_evidence).strip(),
        confidence=max(0.0, min(confidence, 1.0)),
    )


def normalized_words(value: str):
    return re.findall(r"[a-z]+", value.lower())


def evidence_is_supported(evidence: str, text: str) -> bool:
    if not evidence.strip():
        return False

    evidence_words = [
        word
        for word in normalized_words(evidence)
        if len(word) >= 2
    ]
    text_words = set(normalized_words(text))
    return bool(evidence_words) and all(
        word in text_words
        for word in evidence_words
    )


def name_is_supported(name: str, text: str) -> bool:
    name_words = [
        word
        for word in normalized_words(name)
        if len(word) >= 2
    ]
    text_words = set(normalized_words(text))
    return bool(name_words) and all(word in text_words for word in name_words)


def response_has_expected_schema(raw: str) -> bool:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

    return (
        isinstance(data, dict)
        and "patient_name" in data
        and "document_type" in data
    )


def build_evidence_extraction_prompt(text: str) -> str:
    return f"""
Select the patient name and document type from the OCR below.

Return one JSON object with exactly these seven keys and no others:
{{
  "patient_name": "First Last or unknown",
  "document_type": "specific concise type or unknown",
  "document_date": "DD-MM-YY or unknown",
  "name_evidence": "short exact OCR excerpt",
  "type_evidence": "short exact OCR excerpt",
  "date_evidence": "short exact OCR excerpt",
  "confidence": 0.0
}}

Rules:
- Evidence must be copied from OCR, not invented.
- Use structured line position, size, and confidence to understand layout.
- Prefer names labelled Patient/Name/Re or positioned beside DOB/patient ID.
- Ignore doctors, referrers, radiologists, surgeons, carers, and contacts.
- Convert surname-first names to normal order and remove titles.
- Prefer an explicit document title, Examination, Study, or procedure heading.
- For document_date, prefer service/study/examination/procedure/requested/
  appointment/operation dates. Never use Date of Birth/DOB or report export
  dates as document_date.
- document_date must use DD-MM-YY format.
- For a compound imaging heading, preserve every visible modality/body part.
- Never replace a specific visible study with a generic label such as
  "Exam report", "Imaging report", "Medical report", or "Clinical document".
- If evidence does not support a field, return "unknown" for that field.
- confidence must be between 0 and 1.

Use these four exact labels only for their matching recurring forms:
- OP booking: Operation Booking Sheet.
- OP consent: operation/procedure consent form.
- OP stickers: patient label plus surgical implant/product stickers.
- Reg form: Orthopaedics Sports Arthroplasty Personal Details registration form
  with OSA identity visible in the header.

All other documents should use their actual concise title or purpose.

Example:
OCR heading: CT LUMBOSACRAL SPINE, MRI LEFT SHOULDER, MRI RIGHT HIP,
ULTRASOUND RIGHT FOOT
document_type: CT lumbosacral spine, MRI left shoulder and right hip,
ultrasound right foot

OCR:
{text}
""".strip()


def extract_document_details_with_ollama(text: str) -> DocumentDetails:
    if not text.strip():
        return DocumentDetails()

    text = text[:16000]
    deterministic = deterministic_document_details(text)
    common_document_type = deterministic.document_type

    if (
        deterministic.patient_name != UNKNOWN
        and deterministic.document_type != UNKNOWN
    ):
        deterministic.raw_model_response = "SKIPPED: deterministic extraction"
        return deterministic
    if deterministic.document_type == "Reg form":
        deterministic.raw_model_response = (
            "SKIPPED: registration patient fields incomplete"
        )
        return deterministic

    prompt = build_evidence_extraction_prompt(text)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 180,
                },
            },
            timeout=90,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except Exception as e:
        print(f"Ollama failed: {e}")
        return DocumentDetails(
            document_type=common_document_type,
            raw_model_response=f"ERROR: {e}",
        )

    details = parse_model_response(raw)
    if (
        details.patient_name != UNKNOWN
        and not name_is_supported(details.patient_name, text)
    ):
        details.patient_name = UNKNOWN
    if (
        common_document_type == UNKNOWN
        and details.document_type != UNKNOWN
        and not (
            evidence_is_supported(details.type_evidence, text)
            or evidence_is_supported(details.document_type, text)
        )
    ):
        details.document_type = UNKNOWN

    if common_document_type != UNKNOWN:
        details.document_type = common_document_type
        details.type_evidence = deterministic.type_evidence
    if deterministic.patient_name != UNKNOWN:
        details.patient_name = deterministic.patient_name
        details.name_evidence = deterministic.name_evidence
    if deterministic.document_date != UNKNOWN:
        details.document_date = deterministic.document_date
        details.date_evidence = deterministic.date_evidence
    if common_document_type == "Reg form":
        labeled_name = extract_primary_labeled_name(text)
        if labeled_name != UNKNOWN:
            details.patient_name = labeled_name
    elif common_document_type == "OP stickers":
        sticker_name = extract_primary_sticker_name(text)
        if sticker_name != UNKNOWN:
            details.patient_name = sticker_name

    radiology_name = extract_primary_radiology_name(text)
    if radiology_name != UNKNOWN:
        details.patient_name = radiology_name

    if valid_name(details.patient_name):
        return details

    if response_has_expected_schema(raw):
        return details

    # Retry only when the first model response is malformed or off-schema.
    fallback_details = extract_name_with_ollama_fallback(text)

    fallback_details.raw_model_response = (
        f"PRIMARY RESPONSE:\n{raw}\n\n"
        f"FALLBACK RESPONSE:\n{fallback_details.raw_model_response}"
    )

    if (
        fallback_details.patient_name != UNKNOWN
        and not name_is_supported(fallback_details.patient_name, text)
    ):
        fallback_details.patient_name = UNKNOWN

    if valid_name(fallback_details.patient_name):
        if common_document_type != UNKNOWN:
            fallback_details.document_type = common_document_type
            fallback_details.type_evidence = deterministic.type_evidence
        elif fallback_details.document_type == UNKNOWN:
            fallback_details.document_type = details.document_type

        if deterministic.document_date != UNKNOWN:
            fallback_details.document_date = deterministic.document_date
            fallback_details.date_evidence = deterministic.date_evidence
        elif fallback_details.document_date == UNKNOWN:
            fallback_details.document_date = details.document_date

        return fallback_details

    fallback_details.patient_name = UNKNOWN
    if common_document_type != UNKNOWN:
        fallback_details.document_type = common_document_type
        fallback_details.type_evidence = deterministic.type_evidence
    if deterministic.document_date != UNKNOWN:
        fallback_details.document_date = deterministic.document_date
        fallback_details.date_evidence = deterministic.date_evidence

    return fallback_details


def extract_name_with_ollama_fallback(text: str) -> DocumentDetails:
    if not text.strip():
        return DocumentDetails()

    text = text[:9000]

    prompt = build_evidence_extraction_prompt(text)

    try:
        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
                "options": {
                    "temperature": 0,
                    "num_predict": 140,
                },
            },
            timeout=90,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except Exception as e:
        print(f"Ollama fallback failed: {e}")
        return DocumentDetails(raw_model_response=f"ERROR: {e}")

    details = parse_model_response(raw)
    if (
        details.patient_name != UNKNOWN
        and not name_is_supported(details.patient_name, text)
    ):
        details.patient_name = UNKNOWN
    return details
