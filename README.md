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

1. Install `OSA PDF Renamer Installer.pkg`.
2. Enable the Quick Action once:
   - Right-click any PDF in Finder.
   - Choose `Quick Actions > Customize…`.
   - Tick `Rename OSA PDFs`.
3. Select one or more PDFs in Finder.
4. Run `Quick Actions > Rename OSA PDFs`.
5. Wait for the completion notification.
6. Review any files ending in `- Unknown` or starting with `unknown -`.

macOS commonly requires the one-time `Customize…` step for Automator Quick
Actions installed by a package rather than created manually in Automator.

The Automator entry point is:

```text
patient_pdf_renamer.py
```

## Requirements

Coworker Macs should have:

- macOS with Apple Vision OCR support
- Ollama model:
  - `qwen2.5:7b`
- Xcode Command Line Tools for rebuilding the Swift Vision helper

The packaged app bundles Python, its Python dependencies, Poppler, Ollama, and
the compiled Vision helper. The current default assumes the model is available
locally through Ollama.

The packaged app starts its bundled Ollama runtime automatically. If
`qwen2.5:7b` is missing, the app will prompt once and download the model locally
with `ollama pull qwen2.5:7b` while showing a native progress window.

## Configuration

Edit `config.toml`:

```toml
[renamer]
dry_run = false
debug_mode = "off"
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

The packaged coworker default is `debug_mode = "off"` for clean operation. Use
`debug_mode = "failures"` only when deliberately troubleshooting a problematic
document.

## Helper scripts

Double-clickable scripts live in `scripts/`:

- `health_check.command`: checks local dependencies and the Ollama model.
- `run_regression.command`: runs the privacy-safe synthetic regression suite.
- `build_vision_helper.command`: rebuilds the Swift Vision OCR helper.

These scripts are intended for setup/support rather than everyday use.

## macOS app packaging

The `packaging/` folder contains the PyInstaller scaffold for building a
shareable macOS app:

```text
dist/OSA PDF Renamer.app
```

The packaged app is intended for coworkers who do not have Python installed.
It bundles the Python runtime and this project code, but still expects Ollama
and the configured local model to be installed on the Mac.

Build notes are in `packaging/README.md`.

The Finder Quick Action template is also in `packaging/`, ready to be included
in the eventual main installer.

The package builder creates a coworker-facing installer:

```text
dist/OSA PDF Renamer Installer.pkg
```

Builds should use the clean Conda environment defined in
`packaging/environment.yml`, not the default Conda `base` environment.

## Updates

The installed app checks the public GitHub Releases page for newer versions.

Release process:

1. Update the top-level `VERSION` file.
2. Run `packaging/build_app.command`.
3. Run `packaging/build_pkg.command`.
4. Create a GitHub Release tagged `vX.Y.Z` matching `VERSION`.
5. Attach `dist/OSA PDF Renamer Installer.pkg` to the release.

Coworker installs compare their bundled `VERSION` against the latest GitHub
Release tag and offer to open the release page when a newer version exists.

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
helpers/vision_ocr.swift     macOS Vision OCR helper source
pdf_renamer/                 Application package
tests/                       Privacy-safe regression suite
scripts/                     Coworker/setup helper scripts
helpers/                     Helper source files used by the runtime
packaging/                   PyInstaller macOS app packaging scaffold
```

Key package modules:

- `app.py`: batch orchestration and Ollama shutdown.
- `config.py`: executable paths and model settings.
- `extraction.py`: deterministic rules, model prompt, and validation.
- `health.py`: dependency checks and Vision helper rebuilds.
- `models.py`: shared result dataclasses.
- `naming.py`: filename formatting and duplicate handling.
- `notifications.py`: macOS completion notification.
- `ocr.py`: embedded PDF text and structured Vision OCR.
- `workflow.py`: processing and renaming one PDF.
