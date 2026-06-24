# PDF renamer package

- `app.py`: batch orchestration and Ollama shutdown
- `config.py`: executable paths and model settings
- `extraction.py`: deterministic rules, model prompt, and validation
- `models.py`: shared result dataclasses
- `naming.py`: filename formatting and duplicate handling
- `notifications.py`: macOS completion notification
- `ocr.py`: embedded PDF text and structured Vision OCR
- `workflow.py`: processing and renaming one PDF

`patient_pdf_renamer.py` remains the Automator-compatible entry point.

## Configuration

Edit the project-level `config.toml`:

- `dry_run`: calculate names without renaming files
- `debug_mode`: `off`, `failures`, or `all`
- `vision_dpi`: scan rendering resolution, clamped to 150–300
- `notifications`: show the batch completion notification
- `health_check`: verify dependencies before processing
- `ollama.model`: local model name
- `ollama.url`: local Ollama API endpoint

With the default `debug_mode = "failures"`, debug files are written only when
the final patient name or document type is unknown.
