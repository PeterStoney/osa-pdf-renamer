import json
import re

import requests

from .config import OLLAMA_MODEL, OLLAMA_URL, UNKNOWN
from .extraction_cleaning import (
    clean_document_type,
    clean_name,
    clean_sender,
    is_sender_based_document_type,
    likely_title_from_evidence,
    recurring_form_type_from_model,
    strip_unknown_alternative,
    valid_name,
    valid_sender,
)
from .extraction_dates import has_negative_date_context, parse_date_value
from .extraction_names import (
    deterministic_document_details,
    extract_primary_labeled_name,
    extract_primary_radiology_name,
    extract_primary_sticker_name,
)
from .models import DocumentDetails


def clean_generic_field(value: str) -> str:
    value = strip_unknown_alternative(value)
    value = re.sub(r"[\x00-\x1f/:\\]", " ", str(value))
    value = re.sub(r"\s+", " ", value).strip(" .-_")
    if not value or value.lower() == UNKNOWN:
        return UNKNOWN
    return value[:80]


def clean_amount(value: str) -> str:
    value = clean_generic_field(value)
    if value == UNKNOWN:
        return UNKNOWN
    match = re.search(
        r"(?:AUD|USD|GBP|EUR|NZD)?\s*\$?\s*-?\d[\d,]*(?:\.\d{2})?",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return UNKNOWN
    amount = re.sub(r"\s+", "", match.group(0))
    return amount if amount else UNKNOWN


def model_field(raw: str, key: str) -> str:
    match = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', raw)
    return match.group(1) if match else UNKNOWN


def parse_model_response(raw: str) -> DocumentDetails:
    try:
        data = json.loads(raw)
        name = strip_unknown_alternative(data.get("patient_name", UNKNOWN))
        sender = strip_unknown_alternative(data.get("sender", UNKNOWN))
        recipient = strip_unknown_alternative(data.get("recipient", UNKNOWN))
        document_type = strip_unknown_alternative(
            data.get("document_type", UNKNOWN)
        )
        document_date = strip_unknown_alternative(
            data.get("document_date", UNKNOWN)
        )
        reference = strip_unknown_alternative(data.get("reference", UNKNOWN))
        amount = strip_unknown_alternative(data.get("amount", UNKNOWN))
        location = strip_unknown_alternative(data.get("location", UNKNOWN))
        status = strip_unknown_alternative(data.get("status", UNKNOWN))
        name_evidence = data.get("name_evidence", "")
        sender_evidence = data.get("sender_evidence", "")
        recipient_evidence = data.get("recipient_evidence", "")
        type_evidence = data.get("type_evidence", "")
        date_evidence = data.get("date_evidence", "")
        reference_evidence = data.get("reference_evidence", "")
        amount_evidence = data.get("amount_evidence", "")
        location_evidence = data.get("location_evidence", "")
        status_evidence = data.get("status_evidence", "")
        try:
            confidence = float(data.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
    except Exception:
        name_match = re.search(r'"patient_name"\s*:\s*"([^"]*)"', raw)
        sender_match = re.search(r'"sender"\s*:\s*"([^"]*)"', raw)
        recipient_match = re.search(r'"recipient"\s*:\s*"([^"]*)"', raw)
        type_match = re.search(r'"document_type"\s*:\s*"([^"]*)"', raw)
        name_evidence_match = re.search(
            r'"name_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        sender_evidence_match = re.search(
            r'"sender_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        recipient_evidence_match = re.search(
            r'"recipient_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        type_evidence_match = re.search(
            r'"type_evidence"\s*:\s*"([^"]*)"',
            raw,
        )
        name = (
            strip_unknown_alternative(name_match.group(1))
            if name_match
            else UNKNOWN
        )
        sender = (
            strip_unknown_alternative(sender_match.group(1))
            if sender_match
            else UNKNOWN
        )
        recipient = (
            strip_unknown_alternative(recipient_match.group(1))
            if recipient_match
            else UNKNOWN
        )
        document_type = (
            strip_unknown_alternative(type_match.group(1))
            if type_match
            else UNKNOWN
        )
        date_match = re.search(r'"document_date"\s*:\s*"([^"]*)"', raw)
        document_date = (
            strip_unknown_alternative(date_match.group(1))
            if date_match
            else UNKNOWN
        )
        reference = strip_unknown_alternative(model_field(raw, "reference"))
        amount = strip_unknown_alternative(model_field(raw, "amount"))
        location = strip_unknown_alternative(model_field(raw, "location"))
        status = strip_unknown_alternative(model_field(raw, "status"))
        name_evidence = (
            name_evidence_match.group(1)
            if name_evidence_match
            else ""
        )
        sender_evidence = (
            sender_evidence_match.group(1)
            if sender_evidence_match
            else ""
        )
        recipient_evidence = (
            recipient_evidence_match.group(1)
            if recipient_evidence_match
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
        reference_evidence = model_field(raw, "reference_evidence")
        amount_evidence = model_field(raw, "amount_evidence")
        location_evidence = model_field(raw, "location_evidence")
        status_evidence = model_field(raw, "status_evidence")
        confidence = 0.0

    parsed_document_date = parse_date_value(str(document_date))
    if parsed_document_date == UNKNOWN and str(document_date).lower() == UNKNOWN:
        parsed_document_date = UNKNOWN

    cleaned_name = clean_name(name)
    if not valid_name(cleaned_name):
        cleaned_name = UNKNOWN
    cleaned_sender = clean_sender(sender)
    if not valid_sender(cleaned_sender):
        cleaned_sender = UNKNOWN

    return DocumentDetails(
        patient_name=cleaned_name,
        sender=cleaned_sender,
        recipient=clean_generic_field(recipient),
        document_type=clean_document_type(document_type),
        document_date=parsed_document_date,
        reference=clean_generic_field(reference),
        amount=clean_amount(amount),
        location=clean_generic_field(location),
        status=clean_generic_field(status),
        raw_model_response=raw,
        name_evidence=str(name_evidence).strip(),
        sender_evidence=str(sender_evidence).strip(),
        recipient_evidence=str(recipient_evidence).strip(),
        type_evidence=str(type_evidence).strip(),
        date_evidence=str(date_evidence).strip(),
        reference_evidence=str(reference_evidence).strip(),
        amount_evidence=str(amount_evidence).strip(),
        location_evidence=str(location_evidence).strip(),
        status_evidence=str(status_evidence).strip(),
        confidence=max(0.0, min(confidence, 1.0)),
    )


def normalized_words(value: str):
    return re.findall(r"[a-z]+", value.lower())


def evidence_is_supported(evidence: str, text: str) -> bool:
    if not evidence.strip():
        return False

    compact_evidence = re.sub(r"[^a-z0-9]+", "", evidence.lower())
    compact_text = re.sub(r"[^a-z0-9]+", "", text.lower())
    if compact_evidence and compact_evidence in compact_text:
        return True

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


def context_for_evidence(evidence: str, text: str) -> str:
    evidence = re.sub(r"\s+", " ", evidence).strip()
    if not evidence:
        return ""

    readable_text = text.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0]
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in readable_text.splitlines()
    ]

    evidence_lower = evidence.lower()
    for line in lines:
        if evidence_lower in line.lower() or line.lower() in evidence_lower:
            return line

    return ""


def model_date_is_supported(details: DocumentDetails, text: str) -> bool:
    if details.document_date == UNKNOWN:
        return False

    if details.date_evidence:
        evidence_date = parse_date_value(details.date_evidence)
        if evidence_date != UNKNOWN and evidence_date != details.document_date:
            return False

        context = context_for_evidence(details.date_evidence, text)
        if context and has_negative_date_context(context):
            return False

        if evidence_is_supported(details.date_evidence, text):
            return True

        # A model may provide just the raw date as evidence. Accept it only if
        # the containing OCR line is not an excluded DOB/generated/report date.
        if context and parse_date_value(details.date_evidence) != UNKNOWN:
            return True

    return False


def name_is_supported(name: str, text: str) -> bool:
    name_words = [
        word
        for word in normalized_words(name)
        if len(word) >= 2
    ]
    text_words = set(normalized_words(text))
    return bool(name_words) and all(word in text_words for word in name_words)


def sender_is_supported(sender: str, evidence: str, text: str) -> bool:
    if sender == UNKNOWN:
        return False

    sender_words = [
        word
        for word in normalized_words(sender)
        if len(word) >= 2
    ]
    if not sender_words:
        return False

    if evidence.strip():
        if not evidence_is_supported(evidence, text):
            return False
        if re.search(
            r"\b(?:referrer|bill\s+to|recipient|to|dear|patient)\b",
            evidence,
            flags=re.IGNORECASE,
        ):
            return False
        evidence_words = set(normalized_words(evidence))
        return all(word in evidence_words for word in sender_words)

    text_words = set(normalized_words(text))
    return bool(sender_words) and all(
        word in text_words
        for word in sender_words
    )


def generic_field_is_supported(value: str, evidence: str, text: str) -> bool:
    if value == UNKNOWN:
        return False
    if evidence.strip() and evidence_is_supported(evidence, text):
        return True
    return evidence_is_supported(value, text)


def response_has_expected_schema(raw: str) -> bool:
    try:
        data = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False

    return (
        isinstance(data, dict)
        and "patient_name" in data
        and "sender" in data
        and "recipient" in data
        and "document_type" in data
        and "reference" in data
    )


def constrain_model_details(
    details: DocumentDetails,
    text: str,
    deterministic: DocumentDetails,
) -> DocumentDetails:
    """Reject or repair model fields using deterministic local evidence."""
    common_document_type = deterministic.document_type

    if (
        details.patient_name != UNKNOWN
        and not name_is_supported(details.patient_name, text)
    ):
        details.patient_name = UNKNOWN

    deterministic_name = deterministic.patient_name
    if deterministic_name != UNKNOWN:
        details.patient_name = deterministic_name
        details.name_evidence = deterministic.name_evidence

    if common_document_type == "OP stickers":
        details.sender = UNKNOWN
        details.sender_evidence = ""

    if (
        details.sender != UNKNOWN
        and not sender_is_supported(details.sender, details.sender_evidence, text)
    ):
        details.sender = UNKNOWN
        details.sender_evidence = ""

    if deterministic.sender != UNKNOWN:
        details.sender = deterministic.sender
        details.sender_evidence = deterministic.sender_evidence

    for field, evidence_field in (
        ("recipient", "recipient_evidence"),
        ("reference", "reference_evidence"),
        ("amount", "amount_evidence"),
        ("location", "location_evidence"),
        ("status", "status_evidence"),
    ):
        value = getattr(details, field)
        evidence = getattr(details, evidence_field)
        if value != UNKNOWN and not generic_field_is_supported(
            value,
            evidence,
            text,
        ):
            setattr(details, field, UNKNOWN)
            setattr(details, evidence_field, "")

    recurring_type = recurring_form_type_from_model(details.document_type)
    if recurring_type != UNKNOWN:
        if common_document_type == recurring_type:
            details.document_type = recurring_type
        else:
            details.document_type = UNKNOWN

    if common_document_type != UNKNOWN:
        details.document_type = common_document_type
        details.type_evidence = deterministic.type_evidence

    if common_document_type == UNKNOWN:
        evidence_type = likely_title_from_evidence(details.type_evidence)
        if evidence_type != UNKNOWN:
            details.document_type = evidence_type
        elif (
            details.document_type != UNKNOWN
            and not (
                evidence_is_supported(details.type_evidence, text)
                or evidence_is_supported(details.document_type, text)
            )
        ):
            details.document_type = UNKNOWN

    if deterministic.document_date != UNKNOWN:
        details.document_date = deterministic.document_date
        details.date_evidence = deterministic.date_evidence
    elif not model_date_is_supported(details, text):
        details.document_date = UNKNOWN
        details.date_evidence = ""

    return details


def build_evidence_extraction_prompt(text: str) -> str:
    return f"""
Select useful filename fields from the OCR below.

Return one JSON object with exactly these nineteen keys and no others:
{{
  "patient_name": "unknown",
  "sender": "unknown",
  "recipient": "unknown",
  "document_type": "unknown",
  "document_date": "unknown",
  "reference": "unknown",
  "amount": "unknown",
  "location": "unknown",
  "status": "unknown",
  "name_evidence": "short exact OCR excerpt",
  "sender_evidence": "short exact OCR excerpt",
  "recipient_evidence": "short exact OCR excerpt",
  "type_evidence": "short exact OCR excerpt",
  "date_evidence": "short exact OCR excerpt",
  "reference_evidence": "short exact OCR excerpt",
  "amount_evidence": "short exact OCR excerpt",
  "location_evidence": "short exact OCR excerpt",
  "status_evidence": "short exact OCR excerpt",
  "confidence": 0.0
}}

Rules:
- Evidence must be copied from OCR, not invented.
- Each field must contain one final answer only. Never include alternatives
  such as "or unknown".
- Use structured line position, size, and confidence to understand layout.
- Prefer names labelled Patient/Name/Re or positioned beside DOB/patient ID.
- Ignore doctors, referrers, radiologists, surgeons, carers, and contacts.
- Convert surname-first names to normal order and remove titles.
- sender is the organisation, practice, clinic, company, doctor, or person who
  produced or sent the document. It is not the patient/person the file is about.
- recipient is who the document is addressed or billed to. It is not the
  sender and may differ from the patient/person/subject.
- patient_name is the broad subject the document is about. This can be a
  patient, client, customer, employee, student, claimant, tenant, project,
  property, or organisation. Prefer the document subject over contacts.
- Prefer sender from letterhead, From/Sender/Provider/Practice/Supplier labels,
  or a clear top-of-page organisation name.
- OP stickers / surgical implant sticker pages do not have a sender. Return
  "unknown" for sender on those pages.
- Do not use Referrer, Bill To, recipient, addressee, or Dear/To names as
  sender unless the OCR explicitly says they produced/sent the document.
- sender_evidence must include the sender text itself.
- reference is an invoice, claim, policy, case, matter, order, purchase order,
  account, booking, application, student, employee, or other document reference
  number. Return one concise reference only.
- amount is a total, balance due, invoice total, or other primary money amount.
- location is a site, property, delivery, branch, workplace, or service address
  only when the document clearly labels or centers that place.
- status is a clear document state such as Paid, Unpaid, Approved, Rejected,
  Final, Draft, Expired, Cancelled, Completed, or Pending.
- Prefer an explicit document title, Examination, Study, or procedure heading.
- Do not use an example document type unless that exact type appears in OCR.
- Do not use OP booking, OP consent, OP stickers, or Reg form unless the OCR
  clearly shows that exact recurring form.
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


def details_satisfy_required_fields(
    details: DocumentDetails,
    required_fields: set[str],
) -> bool:
    return (
        ("name" not in required_fields or details.patient_name != UNKNOWN)
        and ("sender" not in required_fields or details.sender != UNKNOWN)
        and ("recipient" not in required_fields or details.recipient != UNKNOWN)
        and ("type" not in required_fields or details.document_type != UNKNOWN)
        and ("date" not in required_fields or details.document_date != UNKNOWN)
        and ("reference" not in required_fields or details.reference != UNKNOWN)
        and ("amount" not in required_fields or details.amount != UNKNOWN)
        and ("location" not in required_fields or details.location != UNKNOWN)
        and ("status" not in required_fields or details.status != UNKNOWN)
    )


def extract_document_details_with_ollama(
    text: str,
    required_fields: set[str] | None = None,
) -> DocumentDetails:
    if not text.strip():
        return DocumentDetails()

    required_fields = required_fields or {"name", "type"}
    text = text[:16000]
    deterministic = deterministic_document_details(text)
    common_document_type = deterministic.document_type

    if details_satisfy_required_fields(deterministic, required_fields):
        deterministic.raw_model_response = "SKIPPED: deterministic extraction"
        return deterministic
    if (
        deterministic.sender != UNKNOWN
        and deterministic.document_type != UNKNOWN
        and deterministic.document_date != UNKNOWN
        and is_sender_based_document_type(deterministic.document_type)
        and details_satisfy_required_fields(deterministic, required_fields)
    ):
        deterministic.raw_model_response = (
            "SKIPPED: deterministic sender-based extraction"
        )
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
                    "num_predict": 320,
                },
            },
            timeout=90,
        )
        response.raise_for_status()
        raw = response.json().get("response", "").strip()
    except Exception as e:
        print(f"Ollama failed: {e}")
        deterministic.raw_model_response = f"ERROR: {e}"
        return deterministic

    details = constrain_model_details(
        parse_model_response(raw),
        text,
        deterministic,
    )
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

    fallback_details = constrain_model_details(
        fallback_details,
        text,
        deterministic,
    )

    if valid_name(fallback_details.patient_name):
        if fallback_details.document_type == UNKNOWN:
            fallback_details.document_type = details.document_type

        if fallback_details.document_date == UNKNOWN:
            fallback_details.document_date = details.document_date

        if fallback_details.sender == UNKNOWN:
            fallback_details.sender = details.sender
        if fallback_details.recipient == UNKNOWN:
            fallback_details.recipient = details.recipient
        if fallback_details.reference == UNKNOWN:
            fallback_details.reference = details.reference
        if fallback_details.amount == UNKNOWN:
            fallback_details.amount = details.amount
        if fallback_details.location == UNKNOWN:
            fallback_details.location = details.location
        if fallback_details.status == UNKNOWN:
            fallback_details.status = details.status

        return fallback_details

    fallback_details.patient_name = UNKNOWN

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
                    "num_predict": 260,
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
