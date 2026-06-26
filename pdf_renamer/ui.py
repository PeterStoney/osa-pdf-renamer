import json
import subprocess
import sys
from pathlib import Path

from .config import (
    APP_VERSION,
    CONFIG_PATH,
    OLLAMA_MODEL,
    PROGRESS_RUNNER_EXECUTABLE,
    USER_CONFIG_PATH,
    deep_merge,
    effective_config,
    load_config,
    write_user_config,
)
from .progress import PROGRESS_FILE_ENV


OUTPUT_OPTIONS = {
    "Date": "include_date",
    "Sender": "include_sender",
    "Person / subject": "include_name",
    "Document type": "include_type",
}


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return ""
    return result.stdout.strip()


def dialog(
    title: str,
    message: str,
    *,
    buttons: tuple[str, ...] = ("OK",),
    default_button: str = "OK",
) -> str:
    button_list = "{" + ", ".join(json.dumps(button) for button in buttons) + "}"
    script = (
        "set dialogResult to display dialog "
        f"{json.dumps(message)} "
        f"with title {json.dumps(title)} "
        f"buttons {button_list} "
        f"default button {json.dumps(default_button)}\n"
        "return button returned of dialogResult"
    )
    return run_osascript(script)


def choose_enabled_output_parts() -> list[str] | None:
    settings = current_output_settings()
    defaults = []
    if settings["include_date"]:
        defaults.append("Date")
    if settings["include_sender"]:
        defaults.append("Sender")
    if settings["include_name"]:
        defaults.append("Person / subject")
    if settings["include_type"]:
        defaults.append("Document type")

    choices = "{" + ", ".join(json.dumps(key) for key in OUTPUT_OPTIONS) + "}"
    default_items = "{" + ", ".join(json.dumps(item) for item in defaults) + "}"
    script = (
        f"set choices to {choices}\n"
        f"set defaultChoices to {default_items}\n"
        "set picked to choose from list choices "
        'with title "OSA PDF Renamer" '
        'with prompt "Choose which fields should appear in renamed PDFs:" '
        "default items defaultChoices "
        "with multiple selections allowed\n"
        "if picked is false then return \"__CANCEL__\"\n"
        'set AppleScript\'s text item delimiters to "\\n"\n'
        "return picked as text"
    )
    output = run_osascript(script)
    if output == "__CANCEL__" or not output:
        return None
    return [part.strip() for part in output.splitlines() if part.strip()]


def save_output_settings(enabled_parts: list[str]) -> None:
    values = {
        config_key: label in enabled_parts
        for label, config_key in OUTPUT_OPTIONS.items()
    }
    write_user_config(
        deep_merge(load_config(USER_CONFIG_PATH), {"output": values})
    )


def current_output_settings() -> dict[str, bool]:
    output = effective_config().get("output", {})
    return {
        "include_date": bool(output.get("include_date", True)),
        "include_sender": bool(output.get("include_sender", False)),
        "include_name": bool(output.get("include_name", True)),
        "include_type": bool(output.get("include_type", True)),
    }


def current_format_preview() -> str:
    settings = current_output_settings()
    parts = []
    if settings["include_date"]:
        parts.append("16-05-26")
    if settings["include_sender"]:
        parts.append("Example Radiology")
    if settings["include_name"]:
        parts.append("John Smith")
    if settings["include_type"]:
        parts.append("MRI right knee")
    return " - ".join(parts) + ".pdf" if parts else "Unknown.pdf"


def show_settings() -> None:
    enabled_parts = choose_enabled_output_parts()
    if enabled_parts is None:
        return

    if not enabled_parts:
        dialog(
            "OSA PDF Renamer",
            "At least one filename field must be enabled.",
        )
        return

    save_output_settings(enabled_parts)
    dialog(
        "OSA PDF Renamer",
        (
            "Settings saved.\n\n"
            "The Rename OSA PDFs Quick Action will use these settings the "
            "next time it runs."
        ),
    )


def show_about() -> None:
    dialog(
        "OSA PDF Renamer",
        (
            f"Version: {APP_VERSION}\n"
            f"Model: {OLLAMA_MODEL}\n\n"
            f"Current filename format:\n{current_format_preview()}\n\n"
            f"Bundled config:\n{CONFIG_PATH}\n\n"
            f"User settings:\n{USER_CONFIG_PATH}"
        ),
    )


def choose_pdfs() -> list[Path]:
    script = (
        'set pickedFiles to choose file '
        'with prompt "Choose PDF files to rename:" '
        'of type {"com.adobe.pdf", "com.apple.pdf", "PDF"} '
        "with multiple selections allowed\n"
        "set outputPaths to {}\n"
        "repeat with pickedFile in pickedFiles\n"
        "  set end of outputPaths to POSIX path of pickedFile\n"
        "end repeat\n"
        'set AppleScript\'s text item delimiters to "\\n"\n'
        "return outputPaths as text"
    )
    output = run_osascript(script)
    if not output:
        return []

    paths = []
    for line in output.splitlines():
        path = Path(line.strip())
        if path.is_file() and path.suffix.lower() == ".pdf":
            paths.append(path)
    return paths


def rename_pdfs_from_ui(pdf_paths: list[Path]) -> int:
    if not pdf_paths:
        return 0

    if getattr(sys, "frozen", False) and PROGRESS_RUNNER_EXECUTABLE.is_file():
        command = [
            str(PROGRESS_RUNNER_EXECUTABLE),
            "--progress-env",
            PROGRESS_FILE_ENV,
            "OSA PDF Renamer",
            "Renaming PDFs",
            sys.executable,
            *[str(path) for path in pdf_paths],
        ]
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            message = (
                result.stderr.strip()
                or result.stdout.strip()
                or "The rename operation did not complete."
            )
            dialog("OSA PDF Renamer", message)
        return result.returncode

    from .app import main as run_main

    summary = run_main([str(path) for path in pdf_paths])
    return 1 if summary.errors else 0


def show_app_ui() -> int:
    if sys.platform != "darwin":
        print(
            "OSA PDF Renamer app UI is currently available on macOS only."
        )
        return 0

    while True:
        button = dialog(
            "OSA PDF Renamer",
            (
                f"Version {APP_VERSION}\n\n"
                "Current filename format:\n"
                f"{current_format_preview()}\n\n"
                "Choose PDFs here, or use the Finder Quick Action."
            ),
            buttons=("Close", "Settings", "Choose PDFs…"),
            default_button="Choose PDFs…",
        )
        if button == "Choose PDFs…":
            pdf_paths = choose_pdfs()
            if pdf_paths:
                rename_pdfs_from_ui(pdf_paths)
            continue
        if button == "Settings":
            show_settings()
            continue
        return 0
