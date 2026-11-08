"""Offline evaluation. Draft examples are excluded from reviewed metrics by default."""
import argparse
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from backend.engine.parsers import parse_syllabus_text, parse_question_paper_text
from backend.engine.auditor import ExamAuditor


class ReferenceLabel(BaseModel):
    question_id: str
    expected_unit: int | None = None
    expected_blooms: Literal['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
    expected_out_of_syllabus: bool = False


class EvaluationExample(BaseModel):
    example_id: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    syllabus_text: str = Field(min_length=1)
    paper_text: str = Field(min_length=1)
    expected_question_count: int = Field(ge=1)
    expected_printed_marks: float = Field(gt=0, allow_inf_nan=False)
    expected_attempt_marks: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    expected_choice_groups: int | None = Field(default=None, ge=0)
    labels: list[ReferenceLabel] = Field(min_length=1)
    reviewer: str = ''
    reviewed_at: str | None = None

    @model_validator(mode='after')
    def unique_labels(self):
        if len({label.question_id for label in self.labels}) != len(self.labels):
            raise ValueError('Reference question IDs must be unique.')
        return self


def seed_examples():
    directory = Path(__file__).parent / 'data'
    return [EvaluationExample(**item) for name in ['evaluation_drafts.json', 'evaluation_challenge_drafts.json']
            for item in json.loads((directory / name).read_text(encoding='utf-8'))]


def evaluate(examples, include_drafts=False):
    selected = [e for e in examples if include_drafts or (e.reviewer.strip() and e.reviewed_at)]
    counts = dict(units_correct=0, units_total=0, blooms_correct=0, labels_total=0,
                  oos_tp=0, oos_fp=0, oos_fn=0, parsed_exact=0, marks_exact=0,
                  choices_correct=0, choices_total=0, attempt_marks_correct=0, attempt_marks_total=0)
    details = []
    for example in selected:
        try:
            syllabus = parse_syllabus_text(example.syllabus_text)
            paper = parse_question_paper_text(example.paper_text)
            report = ExamAuditor(syllabus, paper).run_full_audit()
            questions = {q.question_id: q for q in report.mapped_questions}
            counts['parsed_exact'] += len(questions) == example.expected_question_count
            counts['marks_exact'] += abs(sum(q.marks for q in paper.questions) - example.expected_printed_marks) < 0.001
            if example.expected_attempt_marks is not None:
                counts['attempt_marks_total'] += 1
                counts['attempt_marks_correct'] += abs(report.paper_summary['total_marks'] - example.expected_attempt_marks) < 0.001
            if example.expected_choice_groups is not None:
                counts['choices_total'] += 1
                counts['choices_correct'] += len(paper.choice_groups) == example.expected_choice_groups
            labels = []
            for label in example.labels:
                actual = questions.get(label.question_id)
                counts['labels_total'] += 1
                counts['blooms_correct'] += bool(actual and actual.blooms_level == label.expected_blooms)
                if label.expected_unit is not None:
                    counts['units_total'] += 1
                    counts['units_correct'] += bool(actual and actual.mapped_unit == label.expected_unit)
                detected = bool(actual and actual.is_out_of_syllabus)
                counts['oos_tp'] += detected and label.expected_out_of_syllabus
                counts['oos_fp'] += detected and not label.expected_out_of_syllabus
                counts['oos_fn'] += not detected and label.expected_out_of_syllabus
                labels.append({'reference': label.model_dump(), 'actual': actual.model_dump() if actual else None})
            details.append({'example_id': example.example_id, 'labels': labels})
        except (ValueError, KeyError) as exc:
            # Failures remain in the denominator; never silently inflate accuracy.
            counts['labels_total'] += len(example.labels)
            counts['units_total'] += sum(label.expected_unit is not None for label in example.labels)
            counts['oos_fn'] += sum(label.expected_out_of_syllabus for label in example.labels)
            counts['choices_total'] += example.expected_choice_groups is not None
            counts['attempt_marks_total'] += example.expected_attempt_marks is not None
            details.append({'example_id': example.example_id, 'error': str(exc)})
    ratio = lambda a, b: round(a / b, 4) if b else None
    return {'mode': 'draft smoke check' if include_drafts else 'reviewed examples only',
            'examples_evaluated': len(selected), 'examples_skipped': len(examples) - len(selected),
            'question_count_accuracy': ratio(counts['parsed_exact'], len(selected)),
            'printed_marks_accuracy': ratio(counts['marks_exact'], len(selected)),
            'attempt_marks_accuracy': ratio(counts['attempt_marks_correct'], counts['attempt_marks_total']),
            'choice_group_count_accuracy': ratio(counts['choices_correct'], counts['choices_total']),
            'unit_accuracy': ratio(counts['units_correct'], counts['units_total']),
            'blooms_accuracy': ratio(counts['blooms_correct'], counts['labels_total']),
            'out_of_syllabus_precision': ratio(counts['oos_tp'], counts['oos_tp'] + counts['oos_fp']),
            'out_of_syllabus_recall': ratio(counts['oos_tp'], counts['oos_tp'] + counts['oos_fn']),
            'counts': counts, 'details': details}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--include-drafts', action='store_true')
    parser.add_argument('--dataset', type=Path)
    args = parser.parse_args()
    examples = [EvaluationExample(**e) for e in json.loads(args.dataset.read_text(encoding='utf-8'))] if args.dataset else seed_examples()
    print(json.dumps(evaluate(examples, args.include_drafts), indent=2))
