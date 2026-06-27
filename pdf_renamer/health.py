import importlib.util
import re
import subprocess
import sys
import time
from pathlib import Path

from . import applescript
from .config import (
    OLLAMA_EXECUTABLE,
    OLLAMA_MODEL,
    OLLAMA_OBSOLETE_MODELS,
    PDFINFO_EXECUTABLE,
    PDFTOPPM_EXECUTABLE,
    PDFTOTEXT_EXECUTABLE,
    PROGRESS_RUNNER_EXECUTABLE,
    VISION_OCR_EXECUTABLE,
    VISION_OCR_SOURCE,
)


OLLAMA_APP = Path("/Applications/Ollama.app")
OLLAMA_DOWNLOAD_URL = "https://ollama.com/download/mac"
OLLAMA_STARTUP_TIMEOUT_SECONDS = 45
OLLAMA_MODEL_PULL_TIMEOUT_SECONDS = 60 * 60
OLLAMA_DIR = Path.home() / ".ollama"
OLLAMA_KEY = OLLAMA_DIR / "id_ed25519"


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

    button_list = ", ".join(applescript.literal(button) for button in buttons)
    script = (
        f"display dialog {applescript.literal(message)} "
        f"with title {applescript.literal(title)} "
        f"buttons {{{button_list}}} "
        f"default button {applescript.literal(default_button)}"
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


def remove_obsolete_ollama_models(installed_models: set[str]) -> None:
    """Best-effort cleanup for specific old models after a model migration."""
    for model in OLLAMA_OBSOLETE_MODELS:
        if model not in installed_models:
            continue
        result = subprocess.run(
            [OLLAMA_EXECUTABLE, "rm", model],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode == 0:
            print(f"Removed obsolete Ollama model: {model}")
        else:
            detail = clean_command_output(result.stderr or result.stdout)
            print(f"Could not remove obsolete Ollama model {model}: {detail}")


def clean_command_output(text: str) -> str:
    """Remove terminal progress control codes from command output."""
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    text = re.sub(r"\r+", "\n", text)
    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]
    return "\n".join(lines[-12:])


def ensure_ollama_identity_key() -> str:
    """Create Ollama's local ed25519 identity key when missing."""
    if OLLAMA_KEY.is_file():
        return ""

    try:
        OLLAMA_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
        OLLAMA_DIR.chmod(0o700)
    except Exception as error:
        return f"Could not create {OLLAMA_DIR}: {error}"

    ssh_keygen = Path("/usr/bin/ssh-keygen")
    if not ssh_keygen.is_file():
        return "ssh-keygen is missing; cannot create Ollama identity key"

    try:
        result = subprocess.run(
            [
                str(ssh_keygen),
                "-q",
                "-t",
                "ed25519",
                "-N",
                "",
                "-f",
                str(OLLAMA_KEY),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as error:
        return f"Could not create Ollama identity key: {error}"

    if result.returncode != 0:
        detail = clean_command_output(result.stderr or result.stdout)
        return f"Could not create Ollama identity key: {detail}"

    try:
        OLLAMA_KEY.chmod(0o600)
        public_key = OLLAMA_KEY.with_suffix(".pub")
        if public_key.is_file():
            public_key.chmod(0o644)
    except Exception:
        pass

    return ""


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
    button = show_dialog(
        "OSA PDF Renamer setup",
        (
            f"The local AI model {OLLAMA_MODEL} needs to be downloaded once.\n\n"
            "This may take several minutes and requires an internet "
            "connection. The renamer will continue automatically when the "
            "download finishes."
        ),
        buttons=("Cancel", "Download"),
        default_button="Download",
    )
    if button != "Download":
        return f"Ollama model {OLLAMA_MODEL} download was cancelled"

    key_error = ensure_ollama_identity_key()
    if key_error:
        return key_error

    command = [OLLAMA_EXECUTABLE, "pull", OLLAMA_MODEL]
    if executable_exists(str(PROGRESS_RUNNER_EXECUTABLE)):
        command = [
            str(PROGRESS_RUNNER_EXECUTABLE),
            "OSA PDF Renamer setup",
            f"Downloading {OLLAMA_MODEL}",
            OLLAMA_EXECUTABLE,
            "pull",
            OLLAMA_MODEL,
        ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=OLLAMA_MODEL_PULL_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as error:
        return f"Could not download Ollama model {OLLAMA_MODEL}: {error}"

    if result.returncode != 0:
        detail = ""
        if result.stderr or result.stdout:
            detail = clean_command_output(result.stderr or result.stdout)
        return (
            f"Could not download Ollama model {OLLAMA_MODEL}.\n"
            f"Details:\n{detail}"
        )

    if OLLAMA_MODEL not in installed_ollama_models():
        detail = clean_command_output(result.stderr or result.stdout or "")
        if detail:
            return (
                f"Ollama reported that {OLLAMA_MODEL} finished downloading, "
                f"but the model is not installed.\nDetails:\n{detail}"
            )
        return (
            f"Ollama reported that {OLLAMA_MODEL} finished downloading, "
            "but the model is not installed."
        )

    show_dialog(
        "OSA PDF Renamer setup",
        f"The local AI model {OLLAMA_MODEL} is installed. Continuing now.",
    )

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
        errors.append(f"Ollama runtime is missing at {OLLAMA_EXECUTABLE}")
        return errors

    try:
        running = ollama_list().returncode == 0
    except Exception:
        running = False

    if not running:
        if auto_setup:
            show_dialog(
                "OSA PDF Renamer setup",
                "Starting the bundled local Ollama runtime.",
            )
            running = start_ollama()
        if not running:
            errors.append(
                "Ollama runtime could not be started. "
                f"Expected executable: {OLLAMA_EXECUTABLE}"
            )
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

    if auto_setup and not errors:
        remove_obsolete_ollama_models(installed_ollama_models())

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
        errors.append(f"pdftotext is missing at {PDFTOTEXT_EXECUTABLE}")
    if not executable_exists(PDFTOPPM_EXECUTABLE):
        errors.append(f"pdftoppm/Poppler is missing at {PDFTOPPM_EXECUTABLE}")
    if not executable_exists(PDFINFO_EXECUTABLE):
        errors.append(f"pdfinfo/Poppler is missing at {PDFINFO_EXECUTABLE}")

    rebuild_error = rebuild_vision_helper()
    if rebuild_error:
        errors.append(rebuild_error)
    elif not executable_exists(str(VISION_OCR_EXECUTABLE)):
        errors.append(f"Vision OCR helper is missing at {VISION_OCR_EXECUTABLE}")

    errors.extend(ensure_ollama_ready(auto_setup=auto_setup))

    return errors


def format_dependency_report(errors: list[str]) -> str:
    """Build a coworker-friendly dependency failure report."""
    if not errors:
        return ""

    numbered_errors = "\n".join(
        f"{index}. {error}"
        for index, error in enumerate(errors, start=1)
    )
    return (
        "OSA PDF Renamer cannot safely process these PDFs because one or "
        "more local components are unavailable.\n\n"
        f"Problems found:\n{numbered_errors}\n\n"
        "What to try:\n"
        "1. Reinstall the latest OSA PDF Renamer package.\n"
        "2. Make sure the app is installed in /Applications.\n"
        "3. If this is the first run, keep the Mac online while the local "
        "AI model downloads.\n"
        "4. If this message appears again, send Peter a screenshot of "
        "this popup.\n\n"
        "No PDFs were renamed."
    )
