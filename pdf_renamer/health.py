import importlib.util
import json
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path

from .config import (
    OLLAMA_EXECUTABLE,
    OLLAMA_MODEL,
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


class MacOSProgress:
    def __init__(
        self,
        title: str,
        description: str,
        *,
        total_steps: int | None = None,
    ):
        self.title = title
        self.description = description
        self.total_steps = total_steps
        self.process = None
        self.events = queue.Queue()
        self.thread = None

    def __enter__(self):
        if sys.platform != "darwin":
            print(f"{self.title}: {self.description}")
            return self

        max_value = self.total_steps if self.total_steps is not None else -1
        script = f"""
on run
    set progress total steps to {max_value}
    set progress completed steps to 0
    set progress description to {json.dumps(self.description)}
    set progress additional description to "Please wait…"

    repeat
        delay 0.2
    end repeat
end run
"""
        try:
            self.process = subprocess.Popen(
                ["/usr/bin/osascript", "-e", script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(0.5)
        except Exception:
            self.process = None
        return self

    def update(
        self,
        additional_description: str,
        *,
        completed_steps: int | None = None,
    ) -> None:
        if sys.platform != "darwin" or self.process is None:
            print(additional_description)
            return

        lines = [
            f"set progress additional description to "
            f"{json.dumps(additional_description)}"
        ]
        if completed_steps is not None:
            lines.append(
                f"set progress completed steps to {completed_steps}"
            )
        try:
            subprocess.run(
                ["/usr/bin/osascript", "-e", "\n".join(lines)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                check=False,
            )
        except Exception:
            pass

    def __exit__(self, exc_type, exc, traceback):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
        return False


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


def start_ollama(progress: MacOSProgress | None = None) -> bool:
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
    step = 0
    while time.monotonic() < deadline:
        try:
            if ollama_list().returncode == 0:
                if progress:
                    progress.update(
                        "Ollama is running.",
                        completed_steps=OLLAMA_STARTUP_TIMEOUT_SECONDS,
                    )
                return True
        except Exception:
            pass
        step += 2
        if progress:
            progress.update(
                "Waiting for Ollama to start…",
                completed_steps=min(
                    step,
                    OLLAMA_STARTUP_TIMEOUT_SECONDS,
                ),
            )
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
            capture_output=not executable_exists(
                str(PROGRESS_RUNNER_EXECUTABLE)
            ),
            text=True,
            timeout=OLLAMA_MODEL_PULL_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as error:
        return f"Could not download Ollama model {OLLAMA_MODEL}: {error}"

    if result.returncode != 0:
        detail = ""
        if result.stderr or result.stdout:
            detail = (result.stderr or result.stdout).strip()
        return f"Could not download Ollama model {OLLAMA_MODEL}: {detail}"

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
        errors.append("Ollama is missing")
        return errors

    try:
        running = ollama_list().returncode == 0
    except Exception:
        running = False

    if not running:
        if auto_setup:
            with MacOSProgress(
                "OSA PDF Renamer setup",
                "Starting Ollama",
                total_steps=OLLAMA_STARTUP_TIMEOUT_SECONDS,
            ) as progress:
                progress.update("Starting local Ollama runtime…")
                running = start_ollama(progress=progress)
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
