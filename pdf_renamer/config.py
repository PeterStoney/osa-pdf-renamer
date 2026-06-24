import shutil
import sys
import tomllib
from pathlib import Path

UNKNOWN = "unknown"


def resource_dir() -> Path:
    """Return project resources in source checkout or PyInstaller app."""
    bundled_dir = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundled_dir:
        return Path(bundled_dir)
    return Path(__file__).resolve().parent.parent


def first_available_executable(*candidates: str | Path) -> str:
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if path.is_file():
            return str(path)
        resolved = shutil.which(str(candidate))
        if resolved:
            return resolved
    return str(candidates[-1])


PROJECT_DIR = resource_dir()
CONFIG_PATH = PROJECT_DIR / "config.toml"
VISION_OCR_EXECUTABLE = PROJECT_DIR / "vision_ocr"
VISION_OCR_SOURCE = PROJECT_DIR / "helpers" / "vision_ocr.swift"
PDFTOTEXT_EXECUTABLE = first_available_executable(
    PROJECT_DIR / "bin" / "pdftotext",
    "pdftotext",
    "/opt/homebrew/bin/pdftotext",
)
PDFTOPPM_EXECUTABLE = first_available_executable(
    PROJECT_DIR / "bin" / "pdftoppm",
    "pdftoppm",
    "/opt/homebrew/bin/pdftoppm",
)
OLLAMA_EXECUTABLE = (
    shutil.which("ollama")
    or "/opt/homebrew/bin/ollama"
)


def load_config(config_path: Path = CONFIG_PATH):
    try:
        with config_path.open("rb") as source:
            return tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(f"Could not load {config_path.name}: {error}")
        return {}


_CONFIG = load_config()
_RENAMER = _CONFIG.get("renamer", {})
_OLLAMA = _CONFIG.get("ollama", {})

DRY_RUN = bool(_RENAMER.get("dry_run", False))
DEBUG_MODE = str(_RENAMER.get("debug_mode", "failures")).lower()
if DEBUG_MODE not in {"off", "failures", "all"}:
    print(
        f"Invalid debug_mode {DEBUG_MODE!r}; using 'failures'"
    )
    DEBUG_MODE = "failures"

VISION_DPI = max(150, min(int(_RENAMER.get("vision_dpi", 225)), 300))
NOTIFICATIONS = bool(_RENAMER.get("notifications", True))
HEALTH_CHECK = bool(_RENAMER.get("health_check", True))

OLLAMA_MODEL = str(_OLLAMA.get("model", "qwen2.5:7b"))
OLLAMA_URL = str(
    _OLLAMA.get(
        "url",
        "http://localhost:11434/api/generate",
    )
)
