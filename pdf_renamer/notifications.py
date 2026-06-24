import subprocess
import sys

from .models import BatchSummary


def show_text_message(title: str, message: str):
    if sys.platform != "darwin":
        return

    def escape(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    script = (
        f'display dialog "{escape(message)}" '
        f'with title "{escape(title)}" '
        'buttons {"OK"} default button "OK"'
    )

    try:
        subprocess.run(
            ["/usr/bin/osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as error:
        print(f"macOS message failed: {error}")


def send_text_notification(title: str, message: str):
    show_text_message(title, message)


def send_macos_notification(
    summary: BatchSummary,
    dry_run: bool = False,
):
    if sys.platform != "darwin":
        return

    if summary.errors:
        title = "PDF Renamer finished with errors"
    elif summary.needs_review:
        title = "PDF Renamer needs review"
    else:
        title = "PDF Renamer complete"

    action = "would rename" if dry_run else "renamed"
    parts = [
        f"{summary.processed} processed",
        f"{summary.renamed} {action}",
        f"{summary.unchanged} unchanged",
    ]
    if summary.needs_review:
        parts.append(f"{summary.needs_review} need review")
    if summary.errors:
        parts.append(f"{summary.errors} errors")

    show_text_message(title, " • ".join(parts))
