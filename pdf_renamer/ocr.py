import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from pdf2image import convert_from_path

from .config import (
    PDFTOTEXT_EXECUTABLE,
    VISION_DPI,
    VISION_OCR_EXECUTABLE,
    VISION_OCR_SOURCE,
)
from .models import VisionLine, VisionOCR


def extract_embedded_pdf_text(pdf_path: Path) -> str:
    """Read an existing first-page text layer without rendering or OCR."""
    try:
        result = subprocess.run(
            [
                PDFTOTEXT_EXECUTABLE,
                "-f",
                "1",
                "-l",
                "1",
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


def render_first_page(pdf_path: Path, dpi: int = 225):
    pages = convert_from_path(
        str(pdf_path),
        first_page=1,
        last_page=1,
        dpi=dpi,
    )
    return pages[0] if pages else None


def extract_structured_macos_vision(
    pdf_path: Path,
    page=None,
) -> VisionOCR:
    """Run local macOS Vision OCR and retain geometry and confidence."""
    if sys.platform != "darwin":
        return VisionOCR()

    try:
        page = page or render_first_page(pdf_path)
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


def extract_targeted_osa_name_text(pdf_path: Path, page, vision_text: str) -> str:
    normalized = re.sub(r"\s+", " ", vision_text).lower()
    if not (
        "osa unit trust" in normalized
        and "personal details" in normalized
        and (
            re.search(r"(?im)^\s*Surname\s*:\s*$", vision_text)
            or re.search(r"(?im)^\s*First Name\s*:\s*$", vision_text)
        )
    ):
        return ""

    width, height = page.size
    crops = {
        "Surname": (0.12, 0.15, 0.39, 0.185),
        "First Name": (0.47, 0.15, 0.74, 0.185),
    }
    results = []

    for label, (left, top, right, bottom) in crops.items():
        box = (
            int(width * left),
            int(height * top),
            int(width * right),
            int(height * bottom),
        )
        crop = page.crop(box)
        crop = crop.resize((crop.width * 4, crop.height * 4))
        ocr = extract_structured_macos_vision(pdf_path, page=crop)
        if ocr.lines:
            best_line = max(
                ocr.lines,
                key=lambda line: (
                    line.confidence,
                    line.width * line.height,
                ),
            )
            results.append(f"{label}: {best_line.text}")

    return "\n".join(results)


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
        targeted_name_text = extract_targeted_osa_name_text(
            pdf_path,
            page,
            vision.text,
        )
        if targeted_name_text:
            sections.append(
                "===== TARGETED OSA NAME OCR =====\n\n"
                + targeted_name_text
            )

    summary = structured_vision_summary(vision.lines)
    if summary:
        sections.append(
            "===== STRUCTURED VISION OCR LINES =====\n\n"
            + summary
        )

    return "\n\n".join(sections)
