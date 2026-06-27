import re

from .config import UNKNOWN
from .extraction_cleaning import clean_document_type
from .extraction_cleaning import extract_visible_document_title
from .extraction_vision import primary_vision_text


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

    visible_title = extract_visible_document_title(text)
    if visible_title != UNKNOWN:
        return visible_title

    if (
        "dear " in normalized
        and re.search(r"\bre\s*:", normalized)
        and re.search(
            r"\b(?:thank you|thanks(?: very much)?) for seeing\b"
            r"|\bplease\s+(?:assess|review|see|evaluate)\b"
            r"|\b(?:refer|referral)\b",
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
