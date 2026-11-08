# Evaluation examples and accuracy

The bundled `backend/data/evaluation_drafts.json` and
`backend/data/evaluation_challenge_drafts.json` contain six synthetic draft
cases, 14 question labels, and no attributed faculty reviews. They test parsing,
mapping, optional question extraction, and outside-syllabus behavior. They are
small smoke checks, not representative benchmarks.

Use **Evaluate accuracy** in the dashboard to inspect sources and edit expected
question counts, printed marks, unit labels, Bloom labels, and outside-syllabus
labels. New examples can be added in the same editor. Leave the reviewer field
empty for drafts. Only enter a person's name after that person actually reviews
the example; the server records the review timestamp. This is attribution, not
identity verification. Changing a reviewed example requires a fresh save/review.

The default evaluation includes only records with a nonblank reviewer and review
timestamp. Draft-inclusive checks are explicitly labeled. An empty eligible
dataset returns null metrics, displayed as "No eligible data". The dashboard
shows reference/actual labels so disagreements can be inspected.

Metrics:

- Question-count accuracy: fraction of examples with exactly the expected count.
- Printed-marks accuracy: fraction whose extracted marks sum matches the reference.
- Attempt-marks accuracy: fraction with matching expected attempt marks, among
  examples where this optional reference is supplied.
- Choice-group-count accuracy: fraction with the expected number of optional
  groups, among examples where this optional reference is supplied.
- Unit accuracy: correct unit assignments / labels with an expected unit.
  Null expected units are excluded, typically for outside-syllabus questions.
- Bloom accuracy: correct levels / all reference labels; missing questions fail.
- Outside-syllabus precision: true flags / all flags among reference labels.
- Outside-syllabus recall: true flags / all positive reference labels.

A denominator of zero returns null. Parsing/analysis failures remain in the
denominator and are reported per example. Metrics apply to labeled questions,
not to unlabelled extra questions (extra questions affect question-count accuracy).
There are no network model calls in this evaluator.

The dashboard stores edited examples locally in the SQLite database. Dataset
export downloads their combined current state as JSON. Offline commands:

```bash
python -m backend.evaluation --include-drafts
python -m backend.evaluation --dataset reviewed-examples.json
```

Before claiming real-world accuracy, collect diverse faculty-reviewed examples
with permission, keep an independent held-out set, and report dataset size,
subject coverage, disagreements, and failure cases alongside the metrics.
