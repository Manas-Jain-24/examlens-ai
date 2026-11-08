import copy
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfReader

from backend.app import app
from backend.core.config import settings
from backend.engine.parsers import parse_question_paper_text
from backend.engine.choices import choice_accounting, expected_outcome_coverage
from backend.evaluation import seed_examples, evaluate
from backend.models import QuestionPaper, AuditRules

SYLLABUS = 'Course: CS201 Data Structures\nUnit 1: Arrays\n- Arrays\nLO: Explain arrays\nUnit 2: Stacks\n- Stacks\nLO: Explain stacks'
PAPER = 'Section A\nQ1. Define arrays. (5 Marks)\nSection B: Answer any one\nQ2. Explain stacks. (10 Marks)\nQ3. Analyze stacks. (10 Marks)'


class TestWorkspace(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db_patch = patch.object(settings, 'HISTORY_DB_PATH', str(Path(self.temp.name) / 'history.sqlite3'))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.client = TestClient(app)

    def preview(self, paper=PAPER):
        response = self.client.post('/api/parse', data={'syllabus_text': SYLLABUS, 'paper_text': paper})
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def report(self):
        response = self.client.post('/api/audit-reviewed', json=self.preview())
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()

    def save(self, report, **kwargs):
        return self.client.post('/api/history', json={'title': 'Draft paper', 'report': report, **kwargs})

    def test_preview_correction_changes_analysis(self):
        draft = self.preview()
        self.assertEqual(draft['paper']['questions'][0]['section'], 'Section A')
        draft['paper']['questions'][0]['question_text'] = 'Explain stacks.'
        draft['paper']['questions'][0]['marks'] = 7
        result = self.client.post('/api/audit-reviewed', json=draft).json()
        self.assertEqual(result['mapped_questions'][0]['mapped_unit'], 2)
        self.assertEqual(result['mapped_questions'][0]['marks'], 7)
        self.assertEqual(result['paper_summary']['total_marks'], 17)

    def test_preview_empty_extraction_can_be_corrected(self):
        draft = self.preview('Unnumbered title')
        self.assertEqual(draft['paper']['questions'], [])
        self.assertTrue(draft['warnings'])
        self.assertEqual(self.client.post('/api/audit-reviewed', json=draft).status_code, 422)
        draft['paper']['questions'] = [{'question_id': 'Q1', 'question_text': 'Explain arrays', 'marks': 10}]
        self.assertEqual(self.client.post('/api/audit-reviewed', json=draft).status_code, 200)

    def test_or_renumbering_and_mark_bounds(self):
        paper = parse_question_paper_text('Q1. Explain arrays. (5 Marks)\nOR\nQ1. Explain stacks. (10 Marks)')
        self.assertEqual([q.question_id for q in paper.questions], ['Q1', 'Q1_ALT2'])
        weights, expected, low, high = choice_accounting(paper)
        self.assertEqual((expected, low, high), (7.5, 5, 10))
        self.assertEqual(weights['Q1'], 0.5)

    def test_any_n_and_or_chain(self):
        paper = parse_question_paper_text('Section A\nAttempt any two\nQ1. A (5 Marks)\nQ2. B (5 Marks)\nQ3. C (5 Marks)')
        self.assertEqual(paper.choice_groups[0].choose, 2)
        self.assertEqual(choice_accounting(paper)[1:], (10, 10, 10))
        chain = parse_question_paper_text('Q1. A (5 Marks)\nOR\nQ2. B (5 Marks)\nOR\nQ3. C (5 Marks)')
        self.assertEqual(len(chain.choice_groups), 1)
        self.assertEqual(len(chain.choice_groups[0].question_ids), 3)

    def test_optional_unit_is_not_guaranteed(self):
        draft = self.preview('Q1. Explain arrays. (10 Marks)\nOR\nQ2. Explain stacks. (10 Marks)')
        report = self.client.post('/api/audit-reviewed', json=draft).json()
        self.assertEqual(report['paper_summary']['printed_marks'], 20)
        self.assertEqual(report['paper_summary']['total_marks'], 10)
        self.assertEqual(report['score_breakdown']['syllabus_coverage_score'], 0)
        self.assertTrue(all(u['guaranteed_marks'] == 0 and u['possible_marks'] == 10 for u in report['unit_coverage']))
        # Each alternative tests one different outcome with probability 1/2.
        self.assertEqual(report['score_breakdown']['learning_outcomes_score'], 50)

    def test_rule_targets_drive_bloom_alerts(self):
        draft = self.preview('Q1. Define arrays. (10 Marks)')
        draft['rules']['blooms_targets'] = dict(Remember=100, Understand=0, Apply=0, Analyze=0, Evaluate=0, Create=0)
        report = self.client.post('/api/audit-reviewed', json=draft).json()
        self.assertEqual(report['score_breakdown']['blooms_cognitive_score'], 100)
        self.assertFalse(any(f['category'] == 'Blooms' for f in report['findings']))

    def test_invalid_choice_ids_overlap_and_counts(self):
        base = self.preview()
        for groups in [
            [{'group_id': 'a', 'question_ids': ['Q1', 'MISSING'], 'choose': 1}],
            [{'group_id': 'a', 'question_ids': ['Q1', 'Q2'], 'choose': 2}],
            [{'group_id': 'a', 'question_ids': ['Q1', 'Q2'], 'choose': 1}, {'group_id': 'b', 'question_ids': ['Q2', 'Q3'], 'choose': 1}],
        ]:
            draft = copy.deepcopy(base)
            draft['paper']['choice_groups'] = groups
            self.assertEqual(self.client.post('/api/audit-reviewed', json=draft).status_code, 422)

    def test_configured_scoring_and_blooms_targets(self):
        draft = self.preview()
        draft['rules']['component_weights'] = dict(coverage=0, outcomes=0, marks=0, blooms=100, syllabus=0, repetition=0)
        report = self.client.post('/api/audit-reviewed', json=draft).json()
        self.assertEqual(report['overall_quality_score'], report['score_breakdown']['blooms_cognitive_score'])
        percentage_total = sum(stat['percentage'] for stat in report['blooms_distribution'])
        draft['rules']['blooms_targets'] = {stat['level']: stat['percentage'] / percentage_total * 100 for stat in report['blooms_distribution']}
        response = self.client.post('/api/audit-reviewed', json=draft)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['overall_quality_score'], 100)

    def test_invalid_rule_distributions_and_thresholds(self):
        with self.assertRaises(ValidationError):
            AuditRules(repeat_medium=0.9, repeat_high=0.8)
        with self.assertRaises(ValidationError):
            AuditRules(unit_weights={1: 40, 2: 40})
        draft = self.preview()
        draft['rules']['unit_weights'] = {'99': 100}
        self.assertEqual(self.client.post('/api/audit-reviewed', json=draft).status_code, 422)

    def test_mapping_evidence_and_faculty_decision_survive_recalculation(self):
        report = self.report()
        q = report['mapped_questions'][0]
        self.assertIn('Arrays', q['mapping_evidence']['matched_topics'])
        self.assertTrue(q['mapping_evidence']['candidate_units'])
        q.update(review_status='corrected', review_note='Faculty confirmed Unit 2', mapped_unit=2)
        response = self.client.post('/api/recalculate', json={
            'syllabus': report['syllabus'], 'questions': report['mapped_questions'],
            'rules': report['rules'], 'choice_groups': report['choice_groups'], 'pyqs': report['pyqs']})
        self.assertEqual(response.status_code, 200, response.text)
        corrected = response.json()['mapped_questions'][0]
        self.assertEqual(corrected['review_note'], 'Faculty confirmed Unit 2')
        self.assertEqual(corrected['mapped_unit'], 2)
        self.assertEqual(corrected['mapping_evidence']['suggested_unit'], 1)

    def test_history_round_trip_and_conflict(self):
        report = self.report()
        first = self.save(report).json()
        report['mapped_questions'][0]['review_note'] = 'Checked by moderator'
        second = self.save(report, audit_id=first['audit_id'], expected_revision=1)
        self.assertEqual(second.status_code, 200, second.text)
        stale = self.save(report, audit_id=first['audit_id'], expected_revision=1)
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(len(self.client.get('/api/history').json()), 1)
        reopened = self.client.get(f"/api/history/{first['audit_id']}/revisions/1").json()
        self.assertEqual(reopened['report']['mapped_questions'][0]['review_note'], '')
        self.assertEqual(len(self.client.get(f"/api/history/{first['audit_id']}/revisions").json()), 2)

    def test_revision_comparison(self):
        report = self.report()
        first = self.save(report).json()
        changed = copy.deepcopy(report)
        changed['mapped_questions'][0]['marks'] = 9
        changed['overall_quality_score'] += 2
        self.save(changed, audit_id=first['audit_id'], expected_revision=1)
        comparison = self.client.get(f"/api/history/{first['audit_id']}/compare?before=1&after=2").json()
        self.assertEqual(comparison['score_delta'], 2)
        self.assertEqual(comparison['questions'][0]['fields']['marks'], {'before': 5, 'after': 9})
        self.assertEqual(self.client.get('/api/history/missing/revisions/1').status_code, 404)

    def test_draft_samples_are_not_reviewed_accuracy(self):
        result = self.client.get('/api/evaluation/run').json()
        self.assertEqual(result['examples_evaluated'], 0)
        self.assertIsNone(result['unit_accuracy'])
        smoke = evaluate(seed_examples(), include_drafts=True)
        self.assertEqual(smoke['examples_evaluated'], 3)
        self.assertEqual(smoke['question_count_accuracy'], 1)
        self.assertEqual(smoke['printed_marks_accuracy'], 1)
        self.assertEqual(smoke['out_of_syllabus_recall'], 1)

    def test_reviewed_label_persistence_and_evaluation(self):
        example = seed_examples()[0].model_dump()
        example['reviewer'] = 'Test reviewer fixture'
        saved = self.client.put(f"/api/evaluation/examples/{example['example_id']}", json=example)
        self.assertEqual(saved.status_code, 200, saved.text)
        self.assertTrue(saved.json()['reviewed_at'])
        result = self.client.get('/api/evaluation/run').json()
        self.assertEqual(result['examples_evaluated'], 1)
        self.assertEqual(result['counts']['labels_total'], 2)
        example['reviewer'] = ''
        example['reviewed_at'] = 'fabricated'
        saved = self.client.put(f"/api/evaluation/examples/{example['example_id']}", json=example).json()
        self.assertIsNone(saved['reviewed_at'])

    def test_failed_parse_is_in_evaluation_denominator(self):
        example = seed_examples()[0].model_copy(deep=True)
        example.paper_text = 'No questions'
        result = evaluate([example], include_drafts=True)
        self.assertEqual(result['counts']['labels_total'], len(example.labels))
        self.assertEqual(result['blooms_accuracy'], 0)

    def test_pdf_explains_choices_rules_and_escapes_document_markup(self):
        report = self.report()
        report['paper_summary']['paper_title'] = 'Draft <not a tag> & moderation'
        response = self.client.post('/api/export-pdf', json=report)
        self.assertEqual(response.status_code, 200, response.text[:100])
        text = '\n'.join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)
        self.assertIn('Expected Attempt Marks', text)
        self.assertIn('Printed marks: 25', text)
        self.assertIn('Valid attempt marks: 15', text)
        self.assertIn('Draft <not a tag> & moderation', text)
        self.assertIn('Mapping Evidence', text)


if __name__ == '__main__':
    unittest.main()
