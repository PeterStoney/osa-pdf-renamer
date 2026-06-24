import subprocess
import sys
from pathlib import Path

from .config import (
    DEBUG_MODE,
    DRY_RUN,
    HEALTH_CHECK,
    NOTIFICATIONS,
    OLLAMA_EXECUTABLE,
    OLLAMA_MODEL,
)
from .health import check_dependencies
from .health import format_dependency_report
from .models import BatchSummary
from .notifications import (
    send_macos_notification,
    send_text_notification,
)
from .workflow import rename_pdf


def main(
    args=None,
    *,
    dry_run: bool = DRY_RUN,
    debug_mode: str = DEBUG_MODE,
    health_check: bool = HEALTH_CHECK,
    notifications: bool = NOTIFICATIONS,
):
    arguments = list(sys.argv[1:] if args is None else args)
    summary = BatchSummary()
    pdf_paths = [
        Path(argument)
        for argument in arguments
        if (
            Path(argument).exists()
            and Path(argument).suffix.lower() == ".pdf"
        )
    ]

    if health_check and pdf_paths:
        health_errors = check_dependencies(auto_setup=True)
        if health_errors:
            summary.errors = len(health_errors)
            message = format_dependency_report(health_errors)
            print(f"PDF Renamer dependency check failed: {message}")
            if notifications:
                send_text_notification(
                    "PDF Renamer cannot start",
                    message,
                )
            return summary

    try:
        for pdf_path in pdf_paths:
            summary.processed += 1
            try:
                result = rename_pdf(
                    pdf_path,
                    dry_run=dry_run,
                    debug_mode=debug_mode,
                )
                if result.renamed:
                    summary.renamed += 1
                else:
                    summary.unchanged += 1
                if result.needs_review:
                    summary.needs_review += 1
            except Exception as error:
                summary.errors += 1
                print(f"Failed to process {pdf_path.name}: {error}")
    finally:
        try:
            subprocess.run(
                [OLLAMA_EXECUTABLE, "stop", OLLAMA_MODEL],
                check=False,
            )
        except Exception as error:
            print(f"Could not unload Ollama model: {error}")

        if notifications and summary.processed:
            send_macos_notification(summary, dry_run=dry_run)

    return summary
