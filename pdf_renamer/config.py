import shutil
import sys
import tomllib
from pathlib import Path

UNKNOWN = "unknown"


def bundle_search_dirs() -> tuple[Path, ...]:
    """Return likely resource/binary directories in source or PyInstaller app."""
    bundled_dir = getattr(sys, "_MEIPASS", None)
    if getattr(sys, "frozen", False) and bundled_dir:
        base = Path(bundled_dir)
        candidates = (
            base,
            base / "Resources",
            base / "Frameworks",
            base.parent / "Resources",
            base.parent / "Frameworks",
        )
    else:
        base = Path(__file__).resolve().parent.parent
        candidates = (base,)

    seen = set()
    dirs = []
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        dirs.append(candidate)
    return tuple(dirs)


def resource_dir() -> Path:
    """Return the directory containing config/data resources."""
    for directory in bundle_search_dirs():
        if (directory / "config.toml").is_file():
            return directory
    return bundle_search_dirs()[0]


def bundled_executable_candidates(name: str) -> tuple[Path, ...]:
    candidates = []
    for directory in bundle_search_dirs():
        candidates.append(directory / name)
        candidates.append(directory / "bin" / name)
    return tuple(candidates)


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
VISION_OCR_EXECUTABLE = Path(
    first_available_executable(
        *bundled_executable_candidates("vision_ocr"),
        "vision_ocr",
    )
)
VISION_OCR_SOURCE = PROJECT_DIR / "helpers" / "vision_ocr.swift"
PROGRESS_RUNNER_EXECUTABLE = Path(
    first_available_executable(
        *bundled_executable_candidates("progress_runner"),
        "progress_runner",
    )
)
PDFTOTEXT_EXECUTABLE = first_available_executable(
    *bundled_executable_candidates("pdftotext"),
    "pdftotext",
    "/opt/homebrew/bin/pdftotext",
)
PDFTOPPM_EXECUTABLE = first_available_executable(
    *bundled_executable_candidates("pdftoppm"),
    "pdftoppm",
    "/opt/homebrew/bin/pdftoppm",
)
PDFINFO_EXECUTABLE = first_available_executable(
    *bundled_executable_candidates("pdfinfo"),
    "pdfinfo",
    "/opt/homebrew/bin/pdfinfo",
)
OLLAMA_EXECUTABLE = first_available_executable(
    *bundled_executable_candidates("ollama"),
    "ollama",
    "/Applications/Ollama.app/Contents/Resources/ollama",
    "/opt/homebrew/bin/ollama",
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
