"""Choice accounting without enumerating exponentially many valid papers.

Groups are disjoint. Expected marks assume uniform selection within each group;
minimum and maximum marks are exact bounds, including unequal-mark options.
"""
from backend.models import QuestionPaper
from math import comb


def choice_accounting(paper: QuestionPaper, unit=None):
    weights = {q.question_id: 1.0 for q in paper.questions}
    grouped = {qid for g in paper.choice_groups for qid in g.question_ids}
    values = {q.question_id: q.marks if unit is None or q.mapped_unit == unit else 0.0
              for q in paper.questions}
    minimum = maximum = sum(v for qid, v in values.items() if qid not in grouped)
    for group in paper.choice_groups:
        marks = sorted(values[qid] for qid in group.question_ids)
        minimum += sum(marks[:group.choose])
        maximum += sum(marks[-group.choose:])
        for qid in group.question_ids:
            weights[qid] = group.choose / len(group.question_ids)
    expected = sum(values[qid] * weight for qid, weight in weights.items())
    return weights, round(expected, 4), round(minimum, 4), round(maximum, 4)


def expected_outcome_coverage(paper, syllabus):
    """Expected number of approved outcomes assessed under uniform choices."""
    grouped = {qid for group in paper.choice_groups for qid in group.question_ids}
    approved = {(unit.unit_number, lo) for unit in syllabus.units for lo in unit.learning_outcomes}
    total = 0.0
    for number, outcome in approved:
        mapped = {q.question_id for q in paper.questions if q.mapped_unit == number and outcome in q.mapped_outcomes}
        if mapped - grouped:
            total += 1
            continue
        not_tested = 1.0
        for group in paper.choice_groups:
            size = len(group.question_ids)
            absent = size - len(mapped & set(group.question_ids))
            not_tested *= comb(absent, group.choose) / comb(size, group.choose) if absent >= group.choose else 0
        total += 1 - not_tested
    return total, len(approved)
