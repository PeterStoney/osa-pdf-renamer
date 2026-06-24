# PDF renamer regression tests

Run the local, read-only suite with:

```bash
/opt/miniconda3/bin/python tests/run_regression.py
```

Add synthetic OCR cases to `regression_cases.json`:

```json
{
  "name": "Short description",
  "ocr_text": "Fictional OCR text using invented patient details",
  "patient_name": "Alex Sample",
  "document_type": "Expected type"
}
```

Do not store real patient information or paths to medical files in the manifest.
The runner compares synthetic OCR against expected extraction results and does
not rename or modify any files.
