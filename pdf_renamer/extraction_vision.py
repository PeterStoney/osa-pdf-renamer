import json
import re


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
