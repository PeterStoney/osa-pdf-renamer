# OSA PDF Renamer

Local macOS tool for renaming selected PDFs from Finder.

The tool reads the first page of each selected PDF, extracts useful fields,
and renames the file safely:

```text
Date - Person or subject - Document type.pdf
```

Examples:

```text
16-05-26 - John Smith - MRI left knee.pdf
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

Model choice and longer-term cross-platform notes are documented in
`docs/model_strategy.md`.

## Main workflow

The normal workflow is through a Finder Automator Quick Action:

1. Install `OSA PDF Renamer Installer.pkg`.
2. Enable the Quick Action once:
   - Right-click any PDF in Finder.
   - Choose `Quick Actions > Customize…`.
   - Tick `Rename OSA PDFs`.
3. Select one or more PDFs in Finder.
4. Run `Quick Actions > Rename OSA PDFs`.
5. Wait for the progress indicator and completion popup.
6. If files need review, choose `Review unknowns` to correct them immediately.

macOS commonly requires the one-time `Customize…` step for Automator Quick
Actions installed by a package rather than created manually in Automator.

Opening `OSA PDF Renamer.app` directly from `/Applications` shows a small
settings interface. The current UI can change which filename fields are used:

- date
- sender
- person / subject
- document type

The settings are saved per user in:

```text
~/Library/Application Support/OSA PDF Renamer/config.toml
```

The Automator entry point is:

```text
patient_pdf_renamer.py
```

## Review and local learning

When a batch finishes with unknown enabled fields, the app shows:

```text
Renamed: 8
Needs review: 2
Errors: 0
```

Choose `Review unknowns` to correct each file. The correction prompt shows the
fields detected from OCR/model extraction before asking for edits. You can:

- choose `Save` to rename and save a correction;
- choose `Skip` to leave that file as-is;
- choose `Exit review` to stop reviewing the remaining files.

If `Save` is clicked while any enabled field still says `unknown`, the app
treats that as a skip and does not save a correction record.

Corrections are used to rename the reviewed files and are saved locally in:

```text
~/Library/Application Support/OSA PDF Renamer/corrections.jsonl
```

That file may contain real OCR text and real document details. It is private
local learning data and must not be committed to git.

`tests/regression_cases.json` remains the curated, privacy-safe test suite. Add
to it only with fictional/anonymised examples that have been manually reviewed.

## Requirements

Coworker Macs should have:

- macOS with Apple Vision OCR support
- Ollama model:
  - `qwen2.5:3b`

The packaged app bundles Python, its Python dependencies, Poppler, Ollama, and
the compiled Vision helper. Coworkers do not need Python, Conda, Homebrew, or
Xcode Command Line Tools for normal use.

The packaged app starts its bundled Ollama runtime automatically. If
`qwen2.5:3b` is missing, the app will prompt once and download the model locally
with `ollama pull qwen2.5:3b` while showing a native progress window.

## Configuration

Edit `config.toml`:

```toml
[renamer]
dry_run = false
debug_mode = "off"
vision_dpi = 225
notifications = true
health_check = true

[output]
include_date = true
include_sender = false
include_name = true
include_type = true

[ollama]
model = "qwen2.5:3b"
url = "http://localhost:11434/api/generate"
obsolete_models = ["qwen2.5:7b"]
```

Useful options:

- `dry_run`: calculate intended filenames without renaming.
- `debug_mode`: `off`, `failures`, or `all`.
- `vision_dpi`: scan rendering resolution, clamped to 150–300.
- `notifications`: show macOS batch completion notifications.
- `health_check`: verify dependencies before processing.
- `include_date`, `include_sender`, `include_name`, `include_type`: choose
  which extracted fields appear in output filenames. `include_name` currently
  means the person or subject the file relates to, usually the patient in a
  medical workflow.
- `obsolete_models`: specific old Ollama models the app may remove after the
  current model is installed.

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
It bundles the Python runtime, this project code, Poppler, Ollama, and helper
tools. The configured local model is downloaded on first use if missing.

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
Release tag. When a newer version exists, the app can download the attached
`.pkg` installer to `~/Downloads` and open it. If automatic download fails, it
offers to open the GitHub release page instead.

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
