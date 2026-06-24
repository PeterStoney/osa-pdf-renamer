import importlib.util
import subprocess
import sys
from pathlib import Path

from .config import (
    OLLAMA_EXECUTABLE,
    OLLAMA_MODEL,
    PDFTOPPM_EXECUTABLE,
    PDFTOTEXT_EXECUTABLE,
    VISION_OCR_EXECUTABLE,
    VISION_OCR_SOURCE,
)


def executable_exists(executable: str) -> bool:
    path = Path(executable)
    return path.is_file() and path.stat().st_mode & 0o111 != 0


def vision_helper_needs_rebuild() -> bool:
    if not VISION_OCR_EXECUTABLE.is_file():
        return True
    if not VISION_OCR_SOURCE.is_file():
        return False
    return (
        VISION_OCR_SOURCE.stat().st_mtime
        > VISION_OCR_EXECUTABLE.stat().st_mtime
    )


def rebuild_vision_helper() -> str:
    if not vision_helper_needs_rebuild():
        return ""
    if not VISION_OCR_SOURCE.is_file():
        return "Vision OCR source is missing"
    if not Path("/usr/bin/xcrun").is_file():
        return "xcrun is missing; install Xcode Command Line Tools"

    try:
        result = subprocess.run(
            [
                "/usr/bin/xcrun",
                "swiftc",
                "-O",
                str(VISION_OCR_SOURCE),
                "-o",
                str(VISION_OCR_EXECUTABLE),
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except Exception as error:
        return f"Vision helper rebuild failed: {error}"

    if result.returncode != 0:
        detail = result.stderr.strip() or "unknown compiler error"
        return f"Vision helper rebuild failed: {detail}"

    VISION_OCR_EXECUTABLE.chmod(0o755)
    return ""


def check_dependencies():
    errors = []

    if sys.platform != "darwin":
        errors.append("This tool requires macOS")
    for package_name in ("requests", "pdf2image", "PIL"):
        if importlib.util.find_spec(package_name) is None:
            errors.append(
                f"Python package {package_name} is missing"
            )
    if not executable_exists(PDFTOTEXT_EXECUTABLE):
        errors.append("pdftotext is missing")
    if not executable_exists(PDFTOPPM_EXECUTABLE):
        errors.append("pdftoppm/Poppler is missing")

    rebuild_error = rebuild_vision_helper()
    if rebuild_error:
        errors.append(rebuild_error)
    elif not executable_exists(str(VISION_OCR_EXECUTABLE)):
        errors.append("Vision OCR helper is missing")

    if not executable_exists(OLLAMA_EXECUTABLE):
        errors.append("Ollama is missing")
        return errors

    try:
        result = subprocess.run(
            [OLLAMA_EXECUTABLE, "list"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        if result.returncode != 0:
            errors.append("Ollama is not running")
        else:
            installed_models = {
                line.split()[0]
                for line in result.stdout.splitlines()[1:]
                if line.split()
            }
            if OLLAMA_MODEL not in installed_models:
                errors.append(
                    f"Ollama model {OLLAMA_MODEL} is not installed"
                )
    except Exception as error:
        errors.append(f"Could not check Ollama: {error}")

    return errors
