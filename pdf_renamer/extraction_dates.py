import re
from datetime import date

from .config import UNKNOWN


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


def valid_document_year(year: int) -> bool:
    """Allow recent/historical document dates without accepting ancient DOBs."""
    return 1990 <= year <= date.today().year + 5


def valid_calendar_date(day: int, month: int, year: int) -> bool:
    if not valid_document_year(year):
        return False
    try:
        date(year, month, day)
    except ValueError:
        return False
    return True


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
        if valid_calendar_date(day, month, year):
            return format_document_date(day, month, year)

    iso = re.search(r"\b(\d{4})-([01]?\d)-([0-3]?\d)\b", value)
    if iso:
        year = int(iso.group(1))
        month = int(iso.group(2))
        day = int(iso.group(3))
        if valid_calendar_date(day, month, year):
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
        if valid_calendar_date(day, month, year):
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
        if valid_calendar_date(day, month, year):
            return format_document_date(day, month, year)

    return UNKNOWN


POSITIVE_DATE_LABELS = (
    "date of service",
    "service date",
    "study date",
    "exam date",
    "examination date",
    "date of examination",
    "procedure date",
    "performed date",
    "date performed",
    "performed on",
    "scan date",
    "scanned date",
    "imaging date",
    "appointment date",
    "operation date",
    "surgery date",
    "consultation date",
    "referral date",
    "requested date",
    "request date",
    "collection date",
    "collection time",
    "specimen collection date",
    "visit date",
    "admission date",
    "discharge date",
    "invoice date",
    "document date",
    "issue date",
    "letter date",
)


NEGATIVE_DATE_CONTEXT_RE = re.compile(
    r"\b("
    r"date\s+of\s+birth|birth\s+date|dob|born|"
    r"print(?:ed)?\s+date|printed|"
    r"report\s+date|reported|generated|created|modified|"
    r"downloaded|exported|dictated|transcribed|verified|"
    r"finali[sz]ed|uploaded"
    r")\b",
    flags=re.IGNORECASE,
)


GENERIC_DATE_RE = re.compile(
    r"(?im)^\s*date\s*[:\-–]?\s*([^\n]{4,80})$",
)


def has_negative_date_context(context: str) -> bool:
    return bool(NEGATIVE_DATE_CONTEXT_RE.search(context))


def label_pattern(label: str) -> str:
    return r"\s+".join(re.escape(part) for part in label.split())


def candidate_from_labelled_line(
    lines: list[str],
    index: int,
    label: str,
) -> tuple[str, str]:
    line = lines[index]
    pattern = (
        rf"\b{label_pattern(label)}\b"
        r"\s*(?:[:\-–]|\bon\b)?\s*"
        r"([^\n]{0,100})"
    )
    match = re.search(pattern, line, flags=re.IGNORECASE)
    if not match:
        return UNKNOWN, ""

    if has_negative_date_context(line[match.start():]):
        return UNKNOWN, ""

    value = match.group(1).strip()
    document_date = parse_date_value(value)
    evidence = line.strip()

    if document_date == UNKNOWN and index + 1 < len(lines):
        next_line = lines[index + 1].strip()
        if next_line and not has_negative_date_context(next_line):
            next_date = parse_date_value(next_line)
            if next_date != UNKNOWN:
                document_date = next_date
                evidence = f"{line.strip()} {next_line}"

    if document_date == UNKNOWN:
        return UNKNOWN, ""

    return document_date, evidence


def candidate_from_generic_date_line(
    lines: list[str],
    index: int,
) -> tuple[str, str]:
    line = lines[index]
    match = GENERIC_DATE_RE.search(line)
    if not match:
        return UNKNOWN, ""

    context = " ".join(lines[max(0, index - 1): index + 2])
    if has_negative_date_context(context):
        return UNKNOWN, ""

    document_date = parse_date_value(match.group(1))
    if document_date == UNKNOWN:
        return UNKNOWN, ""

    return document_date, line.strip()


def candidate_from_standalone_date_line(
    lines: list[str],
    index: int,
) -> tuple[str, str]:
    line = lines[index].strip()
    if parse_date_value(line) == UNKNOWN:
        return UNKNOWN, ""
    if len(line) > 40:
        return UNKNOWN, ""

    context = " ".join(lines[max(0, index - 1): index + 2])
    if has_negative_date_context(context):
        return UNKNOWN, ""

    return parse_date_value(line), line


def extract_document_date(text: str) -> tuple[str, str]:
    """Extract the document/event date, avoiding DOB and export dates."""
    readable_text = text.split(
        "===== STRUCTURED VISION OCR LINES =====",
        1,
    )[0]
    lines = [
        re.sub(r"\s+", " ", line).strip()
        for line in readable_text.splitlines()
    ]

    for index in range(len(lines)):
        if not lines[index]:
            continue
        for label in POSITIVE_DATE_LABELS:
            document_date, evidence = candidate_from_labelled_line(
                lines,
                index,
                label,
            )
            if document_date != UNKNOWN:
                return document_date, evidence

    # Generic "Date:" is useful for letters, but only after specific labels.
    for index, line in enumerate(lines):
        if not line:
            continue
        document_date, evidence = candidate_from_generic_date_line(
            lines,
            index,
        )
        if document_date != UNKNOWN:
            return document_date, evidence

    # Many letters put a standalone date near the top before "Dear".
    for index, line in enumerate(lines[:10]):
        if not line:
            continue
        document_date, evidence = candidate_from_standalone_date_line(
            lines,
            index,
        )
        if document_date != UNKNOWN:
            return document_date, evidence

    return UNKNOWN, ""
