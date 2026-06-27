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


def user_config_path() -> Path:
    if sys.platform == "darwin":
        return (
            Path.home()
            / "Library"
            / "Application Support"
            / "OSA PDF Renamer"
            / "config.toml"
        )
    if sys.platform == "win32":
        return (
            Path.home()
            / "AppData"
            / "Roaming"
            / "OSA PDF Renamer"
            / "config.toml"
        )
    return Path.home() / ".config" / "osa-pdf-renamer" / "config.toml"


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
USER_CONFIG_PATH = user_config_path()
CORRECTIONS_PATH = USER_CONFIG_PATH.parent / "corrections.jsonl"
VERSION_PATH = PROJECT_DIR / "VERSION"
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
REVIEW_DIALOG_EXECUTABLE = Path(
    first_available_executable(
        *bundled_executable_candidates("review_dialog"),
        "review_dialog",
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
    if not config_path.is_file():
        return {}
    try:
        with config_path.open("rb") as source:
            return tomllib.load(source)
    except (OSError, tomllib.TOMLDecodeError) as error:
        print(f"Could not load {config_path.name}: {error}")
        return {}


def deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if (
            isinstance(value, dict)
            and isinstance(merged.get(key), dict)
        ):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def effective_config() -> dict:
    return deep_merge(load_config(CONFIG_PATH), load_config(USER_CONFIG_PATH))


def format_toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(format_toml_value(item) for item in value) + "]"
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def format_toml_key(key: str) -> str:
    text = str(key)
    if text.replace("_", "").replace("-", "").isalnum():
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def append_toml_section(lines: list[str], path: list[str], values: dict) -> None:
    lines.append("[" + ".".join(format_toml_key(part) for part in path) + "]")
    nested = []
    for key, value in values.items():
        if isinstance(value, dict):
            nested.append((str(key), value))
        else:
            lines.append(f"{format_toml_key(key)} = {format_toml_value(value)}")
    lines.append("")

    for key, value in nested:
        append_toml_section(lines, [*path, key], value)


def write_user_config(config: dict) -> None:
    USER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# User settings for OSA PDF Renamer.",
        "# This file overrides the bundled app defaults.",
        "",
    ]
    for section, values in config.items():
        if not isinstance(values, dict):
            continue
        append_toml_section(lines, [str(section)], values)
    USER_CONFIG_PATH.write_text("\n".join(lines), encoding="utf-8")


_CONFIG = effective_config()
_RENAMER = _CONFIG.get("renamer", {})
_OUTPUT = _CONFIG.get("output", {})
_OLLAMA = _CONFIG.get("ollama", {})
_UPDATES = _CONFIG.get("updates", {})

try:
    APP_VERSION = VERSION_PATH.read_text(encoding="utf-8").strip()
except OSError:
    APP_VERSION = "0.0.0"

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
UPDATE_CHECK = bool(_RENAMER.get("update_check", True))

INCLUDE_DATE = bool(_OUTPUT.get("include_date", True))
INCLUDE_SENDER = bool(_OUTPUT.get("include_sender", False))
INCLUDE_NAME = bool(_OUTPUT.get("include_name", True))
INCLUDE_TYPE = bool(_OUTPUT.get("include_type", True))
INCLUDE_RECIPIENT = bool(_OUTPUT.get("include_recipient", False))
INCLUDE_REFERENCE = bool(_OUTPUT.get("include_reference", False))
INCLUDE_AMOUNT = bool(_OUTPUT.get("include_amount", False))
INCLUDE_LOCATION = bool(_OUTPUT.get("include_location", False))
INCLUDE_STATUS = bool(_OUTPUT.get("include_status", False))

OLLAMA_MODEL = str(_OLLAMA.get("model", "qwen2.5:3b"))
OLLAMA_URL = str(
    _OLLAMA.get(
        "url",
        "http://localhost:11434/api/generate",
    )
)
OLLAMA_OBSOLETE_MODELS = tuple(
    str(model)
    for model in _OLLAMA.get("obsolete_models", ["qwen2.5:7b"])
    if str(model) != OLLAMA_MODEL
)

GITHUB_REPO = str(
    _UPDATES.get("github_repo", "PeterStoney/osa-pdf-renamer")
)
