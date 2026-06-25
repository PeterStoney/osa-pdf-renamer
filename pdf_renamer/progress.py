import os
from pathlib import Path


PROGRESS_FILE_ENV = "OSA_PDF_RENAMER_PROGRESS_FILE"


def progress_path() -> Path | None:
    value = os.environ.get(PROGRESS_FILE_ENV, "").strip()
    return Path(value) if value else None


def write_progress(
    completed: int,
    total: int,
    *,
    message: str = "",
) -> None:
    path = progress_path()
    if path is None:
        return

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        safe_message = message.replace("\t", " ").replace("\n", " ")
        path.write_text(
            f"{max(0, completed)}\t{max(0, total)}\t{safe_message}",
            encoding="utf-8",
        )
    except Exception:
        # Progress reporting should never interrupt PDF processing.
        pass
