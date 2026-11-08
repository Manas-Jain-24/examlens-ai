# Changelog

## 1.2.0 - 2026-11-09

- Added supervised unit-level mark allocations with total/unknown-unit validation.
  Choice-aware coverage bounds use allocated marks rather than duplicating questions.
- Added portable, versioned JSON backup/export and transactional restore as new
  copies. Revision timestamps, review notes, report rules, and local reference
  edits are preserved without overwriting current history.
- Added optional local OCR, sparse-page warnings, extraction provenance, PDF page
  limits, and subprocess timeouts. OCR is disabled until system tools are configured.
- Replaced the hard-coded Gemini model with explicit configuration, SDK timeouts,
  one-attempt requests, response validation, and per-response fallback metadata.
- Made template suggestions subject-neutral and consistent with requested marks
  and Bloom levels. Removed template claims of accreditation compliance.
- Expanded draft evaluation data across computer science, calculus, and biology;
  added attempted-marks and choice-group-count metrics.
- Added regression coverage for backup recovery, unit allocation with optional
  questions, malformed provider results, OCR errors, and real OCR in CI.

## Prior foundation - 2026-11-08

- Added document correction, optional-question groups, configurable scoring,
  mapping evidence and faculty decisions, immutable audit revisions/comparison,
  draft evaluation tools, automated tests, and PDF export improvements.
