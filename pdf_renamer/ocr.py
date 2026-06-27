import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pdf2image import convert_from_path

from .config import (
    PDFINFO_EXECUTABLE,
    PDFTOPPM_EXECUTABLE,
    PDFTOTEXT_EXECUTABLE,
    VISION_DPI,
    VISION_OCR_EXECUTABLE,
    VISION_OCR_SOURCE,
)
from .models import VisionLine, VisionOCR

FIELD_LABEL_PATTERNS = {
    "name": (
        r"(?:patient|client|customer|member|employee)?\s*name",
        r"patient",
        r"person",
        r"subject",
        r"first\s*name",
        r"given\s*name",
        r"surname",
        r"last\s*name",
        r"family\s*name",
        r"re",
    ),
    "date": (
        r"date",
        r"document\s*date",
        r"service\s*date",
        r"study\s*date",
        r"examination\s*date",
        r"procedure\s*date",
        r"operation\s*date",
        r"appointment\s*date",
        r"requested",
        r"collected",
    ),
    "sender": (
        r"sender",
        r"from",
        r"provider",
        r"practice",
        r"clinic",
        r"organisation",
        r"organization",
        r"company",
        r"supplier",
        r"facility",
    ),
    "recipient": (
        r"recipient",
        r"to",
        r"bill\s*to",
        r"ship\s*to",
        r"attention",
        r"attn",
        r"addressee",
        r"customer",
        r"client",
    ),
    "type": (
        r"document\s*type",
        r"report\s*type",
        r"examination",
        r"study",
        r"procedure",
        r"operation",
        r"test",
        r"request",
        r"report",
        r"title",
    ),
    "reference": (
        r"reference",
        r"ref",
        r"number",
        r"no",
        r"invoice\s*(?:number|no)",
        r"claim\s*(?:number|no)",
        r"policy\s*(?:number|no)",
        r"case\s*(?:number|no)",
        r"matter\s*(?:number|no)",
        r"order\s*(?:number|no)",
        r"purchase\s*order",
        r"po\s*(?:number|no)",
        r"account\s*(?:number|no)",
        r"booking\s*reference",
        r"application\s*(?:number|no)",
    ),
    "amount": (
        r"amount",
        r"total",
        r"total\s*due",
        r"balance",
        r"balance\s*due",
        r"invoice\s*total",
        r"subtotal",
        r"paid",
    ),
    "location": (
        r"location",
        r"address",
        r"site",
        r"site\s*address",
        r"property",
        r"property\s*address",
        r"destination",
        r"branch",
        r"facility",
        r"workplace",
    ),
    "status": (
        r"status",
        r"state",
        r"outcome",
        r"result",
        r"approval\s*status",
        r"payment\s*status",
    ),
}


def pdf_page_count(pdf_path: Path) -> int:
    try:
        result = subprocess.run(
            [PDFINFO_EXECUTABLE, str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return 1
        match = re.search(r"^Pages:\s*(\d+)", result.stdout, re.MULTILINE)
        return max(1, int(match.group(1))) if match else 1
    except Exception:
        return 1


def recovery_page_numbers(pdf_path: Path) -> list[int]:
    """Prefer pages likely to contain summary identifiers without scanning all pages."""
    total_pages = pdf_page_count(pdf_path)
    pages = [1]
    if total_pages > 1:
        pages.append(total_pages)
    if total_pages > 2:
        pages.append(2)

    unique_pages = []
    for page in pages:
        if page not in unique_pages:
            unique_pages.append(page)
    return unique_pages


def extract_embedded_pdf_text(pdf_path: Path, page_number: int = 1) -> str:
    """Read an existing page text layer without rendering or OCR."""
    try:
        result = subprocess.run(
            [
                PDFTOTEXT_EXECUTABLE,
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-layout",
                str(pdf_path),
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def has_useful_pdf_text(text: str) -> bool:
    words = re.findall(r"[A-Za-z]{2,}", text)
    return len(text) >= 200 and len(words) >= 25


def render_page(pdf_path: Path, page_number: int = 1, dpi: int = 225):
    poppler_path = None
    pdftoppm_path = Path(PDFTOPPM_EXECUTABLE)
    if pdftoppm_path.is_file():
        poppler_path = str(pdftoppm_path.parent)

    pages = convert_from_path(
        str(pdf_path),
        first_page=page_number,
        last_page=page_number,
        dpi=dpi,
        poppler_path=poppler_path,
    )
    return pages[0] if pages else None


def render_first_page(pdf_path: Path, dpi: int = 225):
    return render_page(pdf_path, page_number=1, dpi=dpi)


def extract_structured_macos_vision(
    pdf_path: Path,
    page=None,
) -> VisionOCR:
    """Run local macOS Vision OCR and retain geometry and confidence."""
    if sys.platform != "darwin":
        return VisionOCR()

    try:
        page = page or render_page(pdf_path, page_number=1)
        if page is None:
            return VisionOCR()

        with tempfile.TemporaryDirectory(prefix="pdf-renamer-") as temp_dir:
            temp_path = Path(temp_dir)
            image_path = temp_path / "page.png"
            page.save(image_path, "PNG")

            if VISION_OCR_EXECUTABLE.is_file():
                command = [str(VISION_OCR_EXECUTABLE), str(image_path)]
            elif VISION_OCR_SOURCE.is_file():
                command = [
                    "/usr/bin/xcrun",
                    "swift",
                    str(VISION_OCR_SOURCE),
                    str(image_path),
                ]
            else:
                print("macOS Vision OCR helper is missing")
                return VisionOCR()

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

        if result.returncode != 0:
            print(f"macOS Vision OCR failed: {result.stderr.strip()}")
            return VisionOCR()

        data = json.loads(result.stdout)
        lines = tuple(
            VisionLine(
                text=str(line.get("text", "")).strip(),
                confidence=float(line.get("confidence", 0.0)),
                x=float(line.get("x", 0.0)),
                y=float(line.get("y", 0.0)),
                width=float(line.get("width", 0.0)),
                height=float(line.get("height", 0.0)),
            )
            for line in data.get("lines", [])
            if str(line.get("text", "")).strip()
        )
        return VisionOCR(
            text="\n".join(line.text for line in lines),
            lines=lines,
        )
    except Exception as error:
        print(f"macOS Vision OCR failed for {pdf_path.name}: {error}")
        return VisionOCR()


def structured_vision_summary(lines) -> str:
    if not lines:
        return ""

    keywords = re.compile(
        r"\b(patient|name|surname|given|dob|birth|re:|examination|"
        r"report|plan|consent|operation|procedure|ultrasound|xray|"
        r"x-ray|mri|ct|pathology|findings|clinical)\b",
        re.IGNORECASE,
    )

    ranked = []
    for index, line in enumerate(lines):
        score = line.height * 8
        score += max(line.y - 0.55, 0) * 2
        score += 1.5 if keywords.search(line.text) else 0
        score += (
            0.5
            if re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", line.text)
            else 0
        )
        score += (
            0.5
            if line.text.isupper() and len(line.text) <= 80
            else 0
        )
        ranked.append((score, index, line))

    selected_indexes = {
        index
        for _, index, _ in sorted(ranked, reverse=True)[:40]
    }
    payload = [
        {
            "text": line.text,
            "confidence": round(line.confidence, 3),
            "x": round(line.x, 3),
            "y": round(line.y, 3),
            "width": round(line.width, 3),
            "height": round(line.height, 3),
        }
        for index, line in enumerate(lines)
        if index in selected_indexes
    ]
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def line_matches_field_label(line_text: str, field: str) -> bool:
    normalized = re.sub(r"[^A-Za-z0-9]+", " ", line_text).strip().lower()
    if not normalized or len(normalized) > 45:
        return False

    for pattern in FIELD_LABEL_PATTERNS.get(field, ()):
        if re.fullmatch(pattern, normalized, flags=re.IGNORECASE):
            return True
        if re.fullmatch(pattern + r"\s*", normalized, flags=re.IGNORECASE):
            return True
        if re.fullmatch(pattern + r"\s*(?:no|number)?", normalized, flags=re.IGNORECASE):
            return True
    return False


def field_crop_candidates(lines, target_fields: set[str]) -> list[tuple[str, tuple[float, float, float, float]]]:
    """Return normalized crop boxes near likely labels for unresolved fields."""
    candidates = []
    seen = set()

    for line in lines:
        text = str(getattr(line, "text", "")).strip()
        if not text:
            continue

        for field in target_fields:
            if not line_matches_field_label(text.rstrip(":."), field):
                continue

            x = max(0.0, min(float(getattr(line, "x", 0.0)), 1.0))
            y = max(0.0, min(float(getattr(line, "y", 0.0)), 1.0))
            width = max(0.0, min(float(getattr(line, "width", 0.0)), 1.0))
            height = max(0.012, min(float(getattr(line, "height", 0.025)), 0.12))
            label = text.rstrip(":.").strip().title()

            boxes = (
                (
                    max(0.0, x + width + 0.006),
                    max(0.0, y - height * 0.6),
                    0.98,
                    min(1.0, y + height * 2.2),
                ),
                (
                    max(0.0, x - 0.015),
                    min(1.0, y + height * 0.8),
                    min(0.98, max(x + width + 0.35, x + 0.55)),
                    min(1.0, y + height * 4.2),
                ),
            )
            for box in boxes:
                left, top, right, bottom = box
                if right - left < 0.05 or bottom - top < 0.008:
                    continue
                key = (
                    field,
                    round(left, 3),
                    round(top, 3),
                    round(right, 3),
                    round(bottom, 3),
                )
                if key in seen:
                    continue
                seen.add(key)
                candidates.append((f"{field} near {label}", box))

    return candidates[:12]


def ocr_crop_text(
    pdf_path: Path,
    page,
    label: str,
    box: tuple[float, float, float, float],
) -> str:
    width, height = page.size
    left, top, right, bottom = box
    pixel_box = (
        int(width * left),
        int(height * top),
        int(width * right),
        int(height * bottom),
    )
    crop = page.crop(pixel_box)
    if crop.width <= 0 or crop.height <= 0:
        return ""

    crop = crop.resize((crop.width * 4, crop.height * 4))
    ocr = extract_structured_macos_vision(pdf_path, page=crop)
    lines = [
        line.text.strip()
        for line in ocr.lines
        if line.text.strip()
    ]
    if not lines:
        return ""
    return f"{label}: " + " ".join(lines)


def extract_targeted_field_text(
    pdf_path: Path,
    target_fields: set[str],
    *,
    page_numbers: list[int] | None = None,
) -> str:
    """Retry OCR around likely labels for unresolved filename fields."""
    if not target_fields:
        return ""

    results = []
    seen_text = set()
    for page_number in page_numbers or [1]:
        try:
            page = render_page(pdf_path, page_number=page_number, dpi=VISION_DPI)
        except Exception as error:
            print(
                f"Targeted OCR rendering failed for {pdf_path.name} "
                f"page {page_number}: {error}"
            )
            continue

        if page is None:
            continue

        vision = extract_structured_macos_vision(pdf_path, page=page)
        candidates = field_crop_candidates(vision.lines, target_fields)
        for label, box in candidates:
            crop_text = ocr_crop_text(
                pdf_path,
                page,
                f"page {page_number} {label}",
                box,
            )
            normalized = re.sub(r"\s+", " ", crop_text).strip().lower()
            if not normalized or normalized in seen_text:
                continue
            seen_text.add(normalized)
            results.append(crop_text)

    return "\n".join(results)


def enhance_text_with_targeted_field_ocr(
    pdf_path: Path,
    text: str,
    target_fields: set[str],
) -> str:
    targeted_text = extract_targeted_field_text(
        pdf_path,
        target_fields,
        page_numbers=recovery_page_numbers(pdf_path),
    )
    if not targeted_text:
        return text

    return (
        text
        + "\n\n===== TARGETED FIELD OCR =====\n\n"
        + targeted_text[:3000]
    )


def extract_single_page_document_text(
    pdf_path: Path,
    *,
    page_number: int,
    label: str,
) -> str:
    embedded_text = extract_embedded_pdf_text(pdf_path, page_number=page_number)
    sections = []
    if embedded_text:
        sections.append(
            f"===== EMBEDDED PDF TEXT ({label}) =====\n\n"
            + embedded_text[:5000]
        )

    try:
        page = render_page(pdf_path, page_number=page_number, dpi=VISION_DPI)
    except Exception as error:
        print(
            f"PDF rendering failed for {pdf_path.name} page {page_number}: {error}"
        )
        return "\n\n".join(sections)

    if page is None:
        return "\n\n".join(sections)

    vision = extract_structured_macos_vision(pdf_path, page=page)
    if vision.text:
        sections.append(
            f"===== MACOS VISION OCR ({label}) =====\n\n"
            + vision.text[:4000]
        )

    summary = structured_vision_summary(vision.lines)
    if summary:
        sections.append(
            f"===== STRUCTURED VISION OCR LINES ({label}) =====\n\n"
            + summary
        )

    return "\n\n".join(sections)


def enhance_text_with_recovery_pages(
    pdf_path: Path,
    text: str,
    target_fields: set[str],
) -> str:
    if not target_fields:
        return text

    additions = []
    existing_normalized = re.sub(r"\s+", " ", text).strip().lower()
    total_pages = pdf_page_count(pdf_path)
    for page_number in recovery_page_numbers(pdf_path):
        if page_number == 1:
            continue
        label = "LAST PAGE" if page_number == total_pages else f"PAGE {page_number}"
        page_text = extract_single_page_document_text(
            pdf_path,
            page_number=page_number,
            label=label,
        )
        normalized = re.sub(r"\s+", " ", page_text).strip().lower()
        if not normalized or normalized in existing_normalized:
            continue
        additions.append(page_text)

    if not additions:
        return text

    return (
        text
        + "\n\n===== RECOVERY PAGE OCR =====\n\n"
        + "\n\n".join(additions)[:8000]
    )


def extract_document_text(pdf_path: Path) -> str:
    """Use embedded text when sufficient, otherwise structured Vision OCR."""
    embedded_text = extract_embedded_pdf_text(pdf_path)
    if has_useful_pdf_text(embedded_text):
        return (
            "===== EMBEDDED PDF TEXT =====\n\n"
            + embedded_text[:12000]
        )

    try:
        page = render_first_page(pdf_path, dpi=VISION_DPI)
    except Exception as error:
        print(f"PDF rendering failed for {pdf_path.name}: {error}")
        if embedded_text:
            return (
                "===== EMBEDDED PDF TEXT =====\n\n"
                + embedded_text[:7000]
            )
        return ""

    if page is None:
        return ""

    vision = extract_structured_macos_vision(pdf_path, page=page)
    sections = []
    if embedded_text:
        sections.append(
            "===== EMBEDDED PDF TEXT =====\n\n"
            + embedded_text[:7000]
        )
    if vision.text:
        sections.append(
            "===== MACOS VISION OCR (PRIMARY) =====\n\n"
            + vision.text[:5000]
        )

    summary = structured_vision_summary(vision.lines)
    if summary:
        sections.append(
            "===== STRUCTURED VISION OCR LINES =====\n\n"
            + summary
        )

    return "\n\n".join(sections)
