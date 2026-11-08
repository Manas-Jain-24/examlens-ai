# Scoring and optional questions

Scoring version 2.0 keeps the six components and default weights (25/20/20/15/10/10)
while allowing course-specific weights, unit targets, Bloom targets, and repetition
thresholds. Saving a revision preserves the selected rules with the result.

## Choice groups

A group is a list of distinct question IDs and a number to attempt. `Q1 OR Q2`
becomes choose 1 of Q1/Q2. `Answer any two` in a section becomes choose 2 of its
questions. Compulsory questions belong to no group. Groups cannot overlap.
Standalone OR lines and numeric/word counts one through ten are recognized;
nested choice instructions are flagged for manual correction.

For a group of N questions where k must be answered, each question has inclusion
weight k/N. Expected marks sum each question's marks times its inclusion weight.
Minimum and maximum attempt marks sum the k smallest/largest marks per group,
plus compulsory marks. These bounds remain exact for unequal-mark options.

Unit minimum/maximum marks use the same calculation after setting questions
outside that unit to zero. This exposes units that a student can skip entirely.
The coverage score counts only units whose minimum is greater than zero.

For example, `Q1 (10 marks, Unit 1) OR Q2 (10 marks, Unit 2)` has 20 printed marks,
10 attempted marks, and 5 expected marks per unit. Neither unit is guaranteed:
each has a 0-10 mark range. Expected percentages describe an assumed uniform
selection, not a prediction of student behavior. Bounds are per unit and need
not all be achievable simultaneously.

## Components

- Coverage: percentage of units guaranteed to receive marks under every valid selection.
- Outcomes: expected fraction of declared, mapped outcomes assessed under uniform
  choices. The probability of testing an outcome is computed from combinations
  within groups. Missing outcomes receive a zero score and a preview warning.
- Marks balance: `max(0, 100 - 2.5 * average absolute percentage-point deviation)`
  from configured unit targets (or syllabus targets/equal weights).
- Bloom alignment: `100 - total variation distance` between the actual expected
  marks distribution and configured targets. Total variation is half the sum of
  absolute percentage-point differences. Deviations over 20 points are flagged.
- Out-of-syllabus: starts at 100, deducting 25 times each flagged question's
  inclusion weight. All flagged printed questions remain visible for review.
- Repetition: starts at 100, deducting 30 per high match or 12 per medium match,
  weighted by inclusion probability. Default medium/high thresholds are 0.70/0.85.

Component scores are rounded to one decimal before weighting. The overall score
is the weighted sum, rounded to one decimal. These are prototype heuristics;
faculty must validate targets and thresholds for their own assessment context.
Older scores may change because version 2 removes unsupported outcome fallback
assignments and uses explicit Bloom targets instead of a fixed lower-order band.

## Mapping review

Evidence retains the original suggested unit, topic matches, cosine score, and
top three candidate units. A faculty correction changes the selected unit without
rewriting the original evidence. Outcomes incompatible with the selected unit are
removed on recalculation. A changed question is reclassified and its review is
reset to pending. A rejected decision is an annotation; change the mapping/flag
or remove the question in document review to change the analysis.

PDFs include the applied weights, targets, choice assumptions, bounds, evidence,
and review notes. They do not certify accreditation or academic validity.
