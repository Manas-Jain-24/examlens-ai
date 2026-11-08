# Configuration, recovery, and local operation

## Start and verify

Install runtime requirements in a virtual environment, copy `.env.example` to
`.env`, and run `python run.py`. Version 1.2.0 binds to `127.0.0.1` by default.
`GET /api/health`, `/api/capabilities`, and `/api/ai/status` report local readiness.
The AI status endpoint does not perform a provider call or claim verified health.

This remains a local application without user accounts or tenant isolation.
Authentication and private faculty workspaces are future deployment work. Do
not use CORS as authentication or expose confidential audit history publicly.

## Gemini

Set `GEMINI_API_KEY` and a `GEMINI_MODEL` available to your account. There is no
guessed model default. Restart after configuration changes. The tested SDK is
`google-genai` 2.31.0; runtime dependencies require 2.31.0 through the 2.x series.

Requests use the SDK's millisecond timeout from `AI_TIMEOUT_SECONDS` (default
20 seconds) and one attempt. A timeout, transport failure, invalid JSON, missing
fields, or mismatched generated marks/levels produces a labeled template result.
Provider exceptions are not returned verbatim to the browser. Keys are never
included in the application's backup format or status endpoint.

Response metadata: `engine`, `model_name`, `fallback_reason`, and
`is_ai_generated`. Reasons include `no_api_key`, `model_not_configured`,
`client_initialization_failed`, `provider_timeout`, and
`provider_error_or_invalid_response`. Templates respect requested levels and
marks but are generic prompts, requiring faculty editing and review.

The [official Google Gen AI SDK](https://github.com/googleapis/python-genai)
documents client options. No paid provider calls are made by the test suite.

## Local OCR

Install Tesseract, its desired language data, and Poppler's `pdftoppm`. Follow the
[Tesseract installation guide](https://tesseract-ocr.github.io/tessdoc/Installation.html)
for your platform. On Ubuntu, the CI job uses `tesseract-ocr` and `poppler-utils`
packages. This repository does not install system binaries on the user's machine.

```dotenv
OCR_ENABLED=true
OCR_LANGUAGE=eng
OCR_TIMEOUT_SECONDS=60
MAX_PDF_PAGES=50
```

The binaries must be on PATH, or use `TESSERACT_CMD` and `PDF_RENDERER_CMD` with
absolute executable paths. Verify them in `/api/capabilities`. A configured
language also needs its Tesseract trained-data files.

Native PDF text is preferred. Pages with fewer than 20 alphanumeric characters
are candidates for OCR. Rendering is capped at a 2400-pixel longest dimension;
the subprocesses share an OCR time budget for the document and use argument
arrays without a shell. Temporary PDF/image files are removed after extraction.
Encrypted, malformed, and over-limit PDFs receive actionable errors. Mixed
documents retain warnings for blank/sparse pages instead of silently dropping
them. OCR-generated wording and marks must be reviewed before auditing.

Limitations: this is a page-level heuristic. Image-only content on otherwise
text-rich pages may be missed. Handwriting, diagrams, layout, and unusual
languages/fonts may require manual correction. OCR does not validate academic
meaning. `/api/parse` returns page methods and warnings; reports and backups
preserve these diagnostics.

## Portable backups

1. Save your current audit revision.
2. Select **Export saved data** and store the downloaded JSON privately.
3. On another installation, select **Restore backup as copies** and choose it.
4. Inspect the restored audit in history and reopen the desired revision.

Backup format version 1 contains saved reports, rules, choice groups, mark splits,
review notes, revision timestamps, and locally edited reference examples. Bundled
draft samples ship with the source repository. Raw uploaded PDF bytes, unsaved
dashboard edits, environment settings, and API keys are not exported.

Restore validates schema, report contexts, distinct IDs, and consecutive revision
numbers before a transaction. It generates new audit/example IDs and never
overwrites existing records. Repeated restores create additional copies. A
malformed bundle or failed transaction leaves prior history intact. The upload
limit is `MAX_BACKUP_SIZE_MB` (default 50). Backups can contain examination text
and review notes; store them as confidential course materials.

For a complete machine-level backup, stop the app and copy the SQLite file from
`HISTORY_DB_PATH` (default `.data/examlens.sqlite3`). Keep `.env` separately using
your own secure credential storage. Neither file belongs in Git.

## Verification

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -v
node --test tests/frontend.test.cjs
python -m backend.evaluation --include-drafts
```

Tests use isolated temporary databases, mocked provider responses, synthetic
PDFs, and explicitly draft reference data. The real image-only OCR test runs
when both CLI tools are available; GitHub Actions installs them on its temporary
Ubuntu runner. A local skip is reported rather than being counted as an OCR pass.
