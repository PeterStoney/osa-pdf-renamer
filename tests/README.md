# PDF renamer regression tests

Run the local, read-only suite with:

```bash
scripts/run_regression.command
```

Add synthetic OCR cases to `regression_cases.json`:

```json
{
  "name": "Short description",
  "ocr_text": "Fictional OCR text using invented patient details",
  "patient_name": "Alex Sample",
  "document_type": "Expected type",
  "document_date": "16-05-26"
}
```

Do not store real patient information or paths to medical files in the manifest.
The runner compares synthetic OCR against expected extraction results and does
not rename or modify any files.

After building the app, run:

```bash
scripts/smoke_test_packaged_app.command
```

That smoke test checks the packaged app bundle, bundled local tools, app
self-test, and Quick Action plist without needing coworker machines or live
patient documents.
