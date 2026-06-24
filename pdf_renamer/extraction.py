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

    raw_lines = primary_text.splitlines()
    for index, raw_line in enumerate(raw_lines):
        line = re.sub(r"\s+", " ", raw_line).strip(" :-.")
        match = re.fullmatch(
            r"(MRI|CT|US|ULTRASOUND|XRAY|X-RAY|X RAY)\s+"
            r"(?:OF\s+)?([A-Z][A-Z0-9 /,&+\-]{2,70})",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        previous_line = ""
        if index:
            previous_line = raw_lines[index - 1].strip()
        is_explicit_field = bool(
            re.fullmatch(
                r"(?:EXAMINATION|PROCEDURE DESCRIPTION|STUDY)\s*:?",
                previous_line,
                flags=re.IGNORECASE,
            )
        )
        if raw_line != raw_line.upper() and not is_explicit_field:
            continue

        modality = modality_names[
            re.sub(r"\s+", " ", match.group(1).upper())
        ]
        subject = re.sub(
            r"\b(?:REPORT|EXAMINATION|STUDY)\b",
            "",
            match.group(2),
            flags=re.IGNORECASE,
        )
        subject = re.sub(r"\s+", " ", subject).strip(" ,-")
        if (
            "," in subject
            or ";" in subject
            or re.search(
                r"\b(?:MRI|CT|US|ULTRASOUND|XRAY|X-RAY)\b",
                subject,
                flags=re.IGNORECASE,
            )
        ):
            continue
        if not subject:
            continue

        return f"{modality} {subject.lower()}"

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
        name_evidence=patient_name if patient_name != UNKNOWN else "",
        type_evidence=document_type if document_type != UNKNOWN else "",
        confidence=1.0 if (
            patient_name != UNKNOWN and document_type != UNKNOWN
        ) else 0.0,
    )


def parse_model_response(raw: str) -> DocumentDetails:
    try:
        data = json.loads(raw)
        name = data.get("patient_name", UNKNOWN)
        document_type = data.get("document_type", UNKNOWN)
        name_evidence = data.get("name_evidence", "")
        type_evidence = data.get("type_evidence", "")
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
        confidence = 0.0

    return DocumentDetails(
        patient_name=clean_name(name),
        document_type=clean_document_type(document_type),
        raw_model_response=raw,
        name_evidence=str(name_evidence).strip(),
        type_evidence=str(type_evidence).strip(),
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

Return one JSON object with exactly these five keys and no others:
{{
  "patient_name": "First Last or unknown",
  "document_type": "specific concise type or unknown",
  "name_evidence": "short exact OCR excerpt",
  "type_evidence": "short exact OCR excerpt",
  "confidence": 0.0
}}

Rules:
- Evidence must be copied from OCR, not invented.
- Use structured line position, size, and confidence to understand layout.
- Prefer names labelled Patient/Name/Re or positioned beside DOB/patient ID.
- Ignore doctors, referrers, radiologists, surgeons, carers, and contacts.
- Convert surname-first names to normal order and remove titles.
- Prefer an explicit document title, Examination, Study, or procedure heading.
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
    if deterministic.patient_name != UNKNOWN:
        details.patient_name = deterministic.patient_name
        details.name_evidence = deterministic.name_evidence
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
        elif fallback_details.document_type == UNKNOWN:
            fallback_details.document_type = details.document_type

        return fallback_details

    fallback_details.patient_name = UNKNOWN
    if common_document_type != UNKNOWN:
        fallback_details.document_type = common_document_type

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
