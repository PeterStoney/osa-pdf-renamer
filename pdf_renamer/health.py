import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

from .config import (
    OLLAMA_EXECUTABLE,
    OLLAMA_MODEL,
    PDFTOPPM_EXECUTABLE,
    PDFTOTEXT_EXECUTABLE,
    VISION_OCR_EXECUTABLE,
    VISION_OCR_SOURCE,
)


OLLAMA_APP = Path("/Applications/Ollama.app")
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/mac"
OLLAMA_STARTUP_TIMEOUT_SECONDS = 45
OLLAMA_MODEL_PULL_TIMEOUT_SECONDS = 60 * 60


def executable_exists(executable: str) -> bool:
    path = Path(executable)
    return path.is_file() and path.stat().st_mode & 0o111 != 0


def show_dialog(
    title: str,
    message: str,
    *,
    buttons: tuple[str, ...] = ("OK",),
    default_button: str = "OK",
) -> str:
    """Best-effort macOS dialog. Returns the pressed button title."""
    if sys.platform != "darwin":
        print(f"{title}: {message}")
        return default_button

    button_list = ", ".join(json.dumps(button) for button in buttons)
    script = (
        f"display dialog {json.dumps(message)} "
        f"with title {json.dumps(title)} "
        f"buttons {{{button_list}}} "
        f"default button {json.dumps(default_button)}"
    )
    try:
        result = subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except Exception:
        return default_button

    if result.returncode != 0:
        return ""

    output = result.stdout.strip()
    prefix = "button returned:"
    if output.startswith(prefix):
        return output[len(prefix):].strip()
    return default_button


def open_url(url: str) -> None:
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/open", url], check=False)


def ollama_list() -> subprocess.CompletedProcess:
    return subprocess.run(
        [OLLAMA_EXECUTABLE, "list"],
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )


def installed_ollama_models() -> set[str]:
    result = ollama_list()
    if result.returncode != 0:
        return set()
    return {
        line.split()[0]
        for line in result.stdout.splitlines()[1:]
        if line.split()
    }


def start_ollama() -> bool:
    """Try to start Ollama and wait until `ollama list` responds."""
    if OLLAMA_APP.is_dir():
        subprocess.run(
            ["/usr/bin/open", "-a", str(OLLAMA_APP)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            subprocess.Popen(
                [OLLAMA_EXECUTABLE, "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            return False

    deadline = time.monotonic() + OLLAMA_STARTUP_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            if ollama_list().returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def pull_ollama_model() -> str:
    show_dialog(
        "OSA PDF Renamer setup",
        (
            f"The local AI model {OLLAMA_MODEL} needs to be downloaded once.\n\n"
            "This may take several minutes and requires an internet "
            "connection. The renamer will continue automatically when the "
            "download finishes."
        ),
    )
    try:
        result = subprocess.run(
            [OLLAMA_EXECUTABLE, "pull", OLLAMA_MODEL],
            capture_output=True,
            text=True,
            timeout=OLLAMA_MODEL_PULL_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as error:
        return f"Could not download Ollama model {OLLAMA_MODEL}: {error}"

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        return f"Could not download Ollama model {OLLAMA_MODEL}: {detail}"

    return ""


def ensure_ollama_ready(auto_setup: bool = False) -> list[str]:
    errors = []

    if not executable_exists(OLLAMA_EXECUTABLE):
        message = (
            "Ollama is required for local document understanding.\n\n"
            "The installer cannot bundle the model because it is very large. "
            "Install Ollama once, then run Rename OSA PDFs again."
        )
        if auto_setup:
            show_dialog("OSA PDF Renamer setup", message)
            open_url(OLLAMA_DOWNLOAD_URL)
        errors.append("Ollama is missing")
        return errors

    try:
        running = ollama_list().returncode == 0
    except Exception:
        running = False

    if not running:
        if auto_setup:
            show_dialog(
                "OSA PDF Renamer setup",
                "Starting Ollama so the PDF renamer can run locally.",
            )
            running = start_ollama()
        if not running:
            errors.append("Ollama is not running")
            return errors

    models = installed_ollama_models()
    if OLLAMA_MODEL not in models:
        if auto_setup:
            pull_error = pull_ollama_model()
            if pull_error:
                errors.append(pull_error)
            elif OLLAMA_MODEL not in installed_ollama_models():
                errors.append(
                    f"Ollama model {OLLAMA_MODEL} is not installed"
                )
        else:
            errors.append(f"Ollama model {OLLAMA_MODEL} is not installed")

    return errors



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


def check_dependencies(auto_setup: bool = False):
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

    errors.extend(ensure_ollama_ready(auto_setup=auto_setup))

    return errors
