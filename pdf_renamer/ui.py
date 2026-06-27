import subprocess
import sys
from pathlib import Path

from . import applescript
from .config import (
    APP_VERSION,
    CONFIG_PATH,
    OLLAMA_MODEL,
    PROGRESS_RUNNER_EXECUTABLE,
    UPDATE_CHECK,
    USER_CONFIG_PATH,
    deep_merge,
    effective_config,
    load_config,
    write_user_config,
)
from .progress import PROGRESS_FILE_ENV
from .update_check import check_for_updates


OUTPUT_OPTIONS = {
    "Date": "include_date",
    "Sender": "include_sender",
    "Recipient": "include_recipient",
    "Subject": "include_name",
    "Reference": "include_reference",
    "Document type": "include_type",
    "Amount": "include_amount",
    "Location": "include_location",
    "Status": "include_status",
}

OUTPUT_PRESETS = {
    "General documents": ("Date", "Subject", "Document type"),
    "Correspondence": ("Date", "Sender", "Subject", "Document type"),
    "Finance": (
        "Date",
        "Sender",
        "Reference",
        "Document type",
        "Amount",
    ),
    "Legal / case": ("Date", "Subject", "Reference", "Document type"),
    "Property / site": ("Date", "Location", "Subject", "Document type"),
    "Logistics": (
        "Date",
        "Sender",
        "Recipient",
        "Reference",
        "Document type",
    ),
    "Full detail": (
        "Date",
        "Sender",
        "Recipient",
        "Subject",
        "Reference",
        "Document type",
    ),
}

CUSTOM_PRESET = "Custom"


def run_osascript(script: str) -> str:
    result = subprocess.run(
        ["/usr/bin/osascript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
        return ""
    return result.stdout.strip()


def dialog(
    title: str,
    message: str,
    *,
    buttons: tuple[str, ...] = ("OK",),
    default_button: str = "OK",
) -> str:
    button_list = "{" + ", ".join(applescript.literal(button) for button in buttons) + "}"
    script = (
        "set dialogResult to display dialog "
        f"{applescript.literal(message)} "
        f"with title {applescript.literal(title)} "
        f"buttons {button_list} "
        f"default button {applescript.literal(default_button)}\n"
        "return button returned of dialogResult"
    )
    return run_osascript(script)


def preset_summary(name: str, fields: tuple[str, ...] | list[str]) -> str:
    return f"{name} - {', '.join(fields)}"


def effective_output_config() -> dict:
    return effective_config().get("output", {})


def field_labels_from_output(output: dict) -> list[str]:
    defaults = {
        "include_date": True,
        "include_sender": False,
        "include_recipient": False,
        "include_name": True,
        "include_reference": False,
        "include_type": True,
        "include_amount": False,
        "include_location": False,
        "include_status": False,
    }
    fields = []
    for label, config_key in OUTPUT_OPTIONS.items():
        if bool(output.get(config_key, defaults[config_key])):
            fields.append(label)
    return fields


def effective_presets() -> dict[str, list[str]]:
    output = effective_output_config()
    presets = {
        name: list(fields)
        for name, fields in OUTPUT_PRESETS.items()
    }
    presets[CUSTOM_PRESET] = field_labels_from_output(output) or [
        "Date",
        "Subject",
        "Document type",
    ]

    saved_presets = output.get("presets", {})
    if isinstance(saved_presets, dict):
        for name, value in saved_presets.items():
            fields = value.get("fields") if isinstance(value, dict) else value
            if not isinstance(fields, list):
                continue
            clean_fields = [
                str(field)
                for field in fields
                if str(field) in OUTPUT_OPTIONS
            ]
            if clean_fields:
                presets[str(name)] = clean_fields

    return presets


def preset_from_summary(summary: str, presets: dict[str, list[str]]) -> str:
    for name, fields in presets.items():
        if summary == preset_summary(name, fields):
            return name
    return CUSTOM_PRESET


def choose_preset(presets: dict[str, list[str]], current_preset: str) -> str | None:
    summaries = [
        preset_summary(name, fields)
        for name, fields in presets.items()
    ]
    default_summary = preset_summary(
        current_preset,
        presets.get(current_preset, presets["General documents"]),
    )
    menu_items = "\n".join(
        f'presetMenu\'s addItemWithTitle:{applescript.literal(summary)}'
        for summary in summaries
    )
    script = (
        'use framework "AppKit"\n'
        'use scripting additions\n'
        'set ca to current application\n'
        'ca\'s NSRunningApplication\'s currentApplication()\'s activateWithOptions:3\n'
        'set alert to ca\'s NSAlert\'s alloc()\'s init()\n'
        'alert\'s setMessageText:"Filename presets"\n'
        'alert\'s setInformativeText:"Choose a preset to edit. Each preset shows the fields it currently enables."\n'
        'alert\'s addButtonWithTitle:"Edit"\n'
        'alert\'s addButtonWithTitle:"Close"\n'
        'set accessoryView to ca\'s NSView\'s alloc()\'s initWithFrame:(ca\'s NSMakeRect(0, 0, 520, 30))\n'
        'set presetMenu to ca\'s NSPopUpButton\'s alloc()\'s initWithFrame:(ca\'s NSMakeRect(0, 0, 520, 28)) pullsDown:false\n'
        + menu_items
        + "\n"
        f'presetMenu\'s selectItemWithTitle:{applescript.literal(default_summary)}\n'
        'accessoryView\'s addSubview:presetMenu\n'
        'alert\'s setAccessoryView:accessoryView\n'
        'alert\'s window()\'s setLevel:(ca\'s NSFloatingWindowLevel)\n'
        'set response to alert\'s runModal()\n'
        'if response is not equal to 1000 then return "__CANCEL__"\n'
        'return presetMenu\'s titleOfSelectedItem() as text\n'
    )
    output = run_osascript(script)
    if output == "__CANCEL__" or not output:
        return None
    return preset_from_summary(output, presets)


def choose_preset_fields(preset: str, defaults: list[str]) -> list[str] | None:
    checkbox_rows = []
    read_values = []
    field_names = list(OUTPUT_OPTIONS)
    for index, field in enumerate(field_names, start=1):
        y = (len(field_names) - index) * 30
        state = 1 if field in defaults else 0
        checkbox_rows.append(
            f'set checkbox{index} to ca\'s NSButton\'s alloc()\'s '
            f'initWithFrame:(ca\'s NSMakeRect(0, {y}, 260, 24))\n'
            f'checkbox{index}\'s setButtonType:(ca\'s NSButtonTypeSwitch)\n'
            f'checkbox{index}\'s setTitle:{applescript.literal(field)}\n'
            f'checkbox{index}\'s setState:{state}\n'
            f'accessoryView\'s addSubview:checkbox{index}'
        )
        read_values.append(
            f'if (checkbox{index}\'s state() as integer) = 1 then '
            f'set end of enabledFields to {applescript.literal(field)}'
        )

    script = (
        'use framework "AppKit"\n'
        'use scripting additions\n'
        'set ca to current application\n'
        'ca\'s NSRunningApplication\'s currentApplication()\'s activateWithOptions:3\n'
        'set alert to ca\'s NSAlert\'s alloc()\'s init()\n'
        f'alert\'s setMessageText:{applescript.literal("Edit preset: " + preset)}\n'
        'alert\'s setInformativeText:"Choose the fields this preset should include, then save."\n'
        'alert\'s addButtonWithTitle:"Save"\n'
        'alert\'s addButtonWithTitle:"Cancel"\n'
        f'set accessoryView to ca\'s NSView\'s alloc()\'s '
        f'initWithFrame:(ca\'s NSMakeRect(0, 0, 260, {len(field_names) * 30}))\n'
        + "\n".join(checkbox_rows)
        + "\n"
        'alert\'s setAccessoryView:accessoryView\n'
        'alert\'s window()\'s setLevel:(ca\'s NSFloatingWindowLevel)\n'
        'set response to alert\'s runModal()\n'
        'if response is not equal to 1000 then return "__CANCEL__"\n'
        'set enabledFields to {}\n'
        + "\n".join(read_values)
        + "\n"
        'set AppleScript\'s text item delimiters to "\\n"\n'
        'return enabledFields as text\n'
    )
    output = run_osascript(script)
    if output == "__CANCEL__":
        return None
    return [part.strip() for part in output.splitlines() if part.strip()]


def choose_enabled_output_parts() -> tuple[str, list[str]] | None:
    current_preset = current_output_settings().get(
        "preset",
        "General documents",
    )
    presets = effective_presets()
    if current_preset not in presets:
        current_preset = "General documents"

    preset = choose_preset(presets, current_preset)
    if preset is None:
        return None

    enabled_parts = choose_preset_fields(preset, presets[preset])
    if enabled_parts is None:
        return None
    return preset, enabled_parts


def save_output_settings(preset: str, enabled_parts: list[str]) -> None:
    values = {
        config_key: label in enabled_parts
        for label, config_key in OUTPUT_OPTIONS.items()
    }
    values["preset"] = preset
    values["presets"] = {
        preset: {
            "fields": enabled_parts,
        },
    }
    write_user_config(
        deep_merge(load_config(USER_CONFIG_PATH), {"output": values})
    )


def preset_data_for_shell() -> dict:
    presets = effective_presets()
    return {
        "options": list(OUTPUT_OPTIONS),
        "current_preset": current_output_settings().get(
            "preset",
            "General documents",
        ),
        "presets": [
            {"name": name, "fields": fields}
            for name, fields in presets.items()
        ],
    }


def current_output_settings() -> dict[str, bool]:
    output = effective_output_config()
    preset = str(output.get("preset", "General documents"))
    presets = effective_presets()
    if preset in presets:
        active_fields = set(presets[preset])
    else:
        active_fields = set()
    return {
        "preset": preset,
        "include_date": (
            "Date" in active_fields
            if active_fields
            else bool(output.get("include_date", True))
        ),
        "include_sender": (
            "Sender" in active_fields
            if active_fields
            else bool(output.get("include_sender", False))
        ),
        "include_name": (
            "Subject" in active_fields
            if active_fields
            else bool(output.get("include_name", True))
        ),
        "include_type": (
            "Document type" in active_fields
            if active_fields
            else bool(output.get("include_type", True))
        ),
        "include_recipient": (
            "Recipient" in active_fields
            if active_fields
            else bool(output.get("include_recipient", False))
        ),
        "include_reference": (
            "Reference" in active_fields
            if active_fields
            else bool(output.get("include_reference", False))
        ),
        "include_amount": (
            "Amount" in active_fields
            if active_fields
            else bool(output.get("include_amount", False))
        ),
        "include_location": (
            "Location" in active_fields
            if active_fields
            else bool(output.get("include_location", False))
        ),
        "include_status": (
            "Status" in active_fields
            if active_fields
            else bool(output.get("include_status", False))
        ),
    }


def current_format_preview() -> str:
    settings = current_output_settings()
    parts = []
    if settings["include_date"]:
        parts.append("16-05-26")
    if settings["include_sender"]:
        parts.append("Example Radiology")
    if settings["include_recipient"]:
        parts.append("Alex Recipient")
    if settings["include_location"]:
        parts.append("12 Smith Street")
    if settings["include_name"]:
        parts.append("John Smith")
    if settings["include_reference"]:
        parts.append("INV-1234")
    if settings["include_type"]:
        parts.append("MRI right knee")
    if settings["include_amount"]:
        parts.append("$245.00")
    if settings["include_status"]:
        parts.append("Paid")
    return " - ".join(parts) + ".pdf" if parts else "Unknown.pdf"


def show_settings() -> None:
    current_preset = current_output_settings().get(
        "preset",
        "General documents",
    )

    while True:
        presets = effective_presets()
        if current_preset not in presets:
            current_preset = "General documents"

        preset = choose_preset(presets, current_preset)
        if preset is None:
            return

        enabled_parts = choose_preset_fields(preset, presets[preset])
        if enabled_parts is None:
            current_preset = preset
            continue

        if not enabled_parts:
            dialog(
                "OSA PDF Renamer",
                "At least one filename field must be enabled.",
            )
            current_preset = preset
            continue

        save_output_settings(preset, enabled_parts)
        current_preset = preset


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

    if UPDATE_CHECK:
        check_for_updates()

    while True:
        button = dialog(
            "OSA PDF Renamer",
            (
                f"Version {APP_VERSION}\n\n"
                "Current filename format:\n"
                f"{current_format_preview()}\n\n"
                "Choose PDFs here, or use the Finder Quick Action."
            ),
            buttons=("Close", "Presets", "Choose PDFs…"),
            default_button="Choose PDFs…",
        )
        if button == "Choose PDFs…":
            pdf_paths = choose_pdfs()
            if pdf_paths:
                rename_pdfs_from_ui(pdf_paths)
            continue
        if button == "Presets":
            show_settings()
            continue
        return 0
