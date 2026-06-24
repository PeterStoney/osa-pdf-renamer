# OSA PDF Renamer

Local macOS tool for renaming selected patient PDFs from Finder.

The tool reads the first page of each selected PDF, extracts the patient name
and document type, and renames the file safely:

```text
Patient Name - Document type.pdf
```

Examples:

```text
John Smith - MRI left knee.pdf
John Smith - Unknown.pdf
unknown - Reg form.pdf
```

## Privacy

This tool is designed to run locally.

- OCR is performed on the Mac.
- Document extraction uses local Ollama.
- No cloud APIs are used by the renamer.
- Real patient PDFs, debug files, OCR dumps, and build artifacts are ignored by
  git.

Regression tests must use fictional patient details only.

## Main workflow

The normal workflow is through a Finder Automator Quick Action:

1. Select one or more PDFs in Finder.
2. Run the PDF renaming Quick Action.
3. Wait for the completion notification.
4. Review any files ending in `- Unknown` or starting with `unknown -`.

The Automator entry point is:

```text
patient_pdf_renamer.py
```

## Requirements

Coworker Macs should have:

- macOS with Apple Vision OCR support
- Python 3
- Python packages:
  - `requests`
  - `pdf2image`
  - `Pillow`
- Poppler command line tools:
  - `pdftotext`
  - `pdftoppm`
- Ollama
- Ollama model:
  - `qwen2.5:7b`
- Xcode Command Line Tools for rebuilding the Swift Vision helper

The current default assumes the model is available locally through Ollama.

## Configuration

Edit `config.toml`:

```toml
[renamer]
dry_run = false
debug_mode = "failures"
vision_dpi = 225
notifications = true
health_check = true

[ollama]
model = "qwen2.5:7b"
url = "http://localhost:11434/api/generate"
```

Useful options:

- `dry_run`: calculate intended filenames without renaming.
- `debug_mode`: `off`, `failures`, or `all`.
- `vision_dpi`: scan rendering resolution, clamped to 150–300.
- `notifications`: show macOS batch completion notifications.
- `health_check`: verify dependencies before processing.

With `debug_mode = "failures"`, debug files are written only when the final
patient name or document type needs review.

## Helper scripts

Double-clickable scripts live in `scripts/`:

- `health_check.command`: checks local dependencies and the Ollama model.
- `run_regression.command`: runs the privacy-safe synthetic regression suite.
- `build_vision_helper.command`: rebuilds the Swift Vision OCR helper.

These scripts are intended for setup/support rather than everyday use.

## Tests

Run:

```bash
/opt/miniconda3/bin/python tests/run_regression.py
```

The regression suite uses synthetic OCR text. Do not add real patient names,
real OCR output, PDFs, or debug files to the test manifest.

## Project structure

```text
patient_pdf_renamer.py       Automator-compatible entry point
config.toml                  Local default settings
vision_ocr.swift             macOS Vision OCR helper source
pdf_renamer/                 Application package
tests/                       Privacy-safe regression suite
scripts/                     Coworker/setup helper scripts
```

