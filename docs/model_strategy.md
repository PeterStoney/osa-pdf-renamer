# Model and compatibility strategy

The app should remain local-first and portable across macOS, Windows, and
Linux. Model choices should be treated as product decisions, not just developer
preferences.

## Current default

The default model is `qwen2.5:3b`.

This is a smaller local Ollama model than the original `qwen2.5:7b`, with lower
download size and lower runtime load. It is only acceptable because extraction
now combines:

- deterministic local rules for strong evidence;
- OCR layout/text evidence;
- model output validation;
- synthetic regression and model benchmark tests.

The model is not trusted blindly. If the model proposes a name, type, or date
that is not supported by OCR text or deterministic evidence, the app should
prefer `unknown` over a confident-looking wrong filename.

## When changing models

Before changing the default model:

1. Run the normal regression suite.
2. Run the synthetic model benchmark against both the current and candidate
   model.
3. Confirm install size, speed, and memory use are acceptable on older machines.
4. Add the old model to `obsolete_models` only when we intentionally want the
   app to remove it during upgrade.

Useful command:

```bash
python tests/benchmark_models.py --models qwen2.5:3b qwen2.5:7b
```

## Cross-platform direction

The core renaming logic should stay platform-neutral. Platform-specific pieces
should be replaceable:

- macOS: Apple Vision OCR helper and Finder Quick Action.
- Windows: future OCR/installer/shell integration.
- Linux: future OCR/installer/file-manager integration.

The extraction layer should not assume the target field is always a patient
name. Future workflows should be configurable, for example:

- medical scanning: date, patient name, document type;
- finance scanning: date, supplier/customer, invoice/receipt type;
- general admin: date, subject/entity, document type.

For older scanner computers, prefer cheap local steps first:

1. existing embedded PDF text;
2. deterministic title/date/name extraction;
3. OCR only when needed;
4. the local model only when deterministic evidence is incomplete.
