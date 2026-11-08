import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.app import app, create_app
from backend.core.config import settings


class TestAuditRegressions(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_unchanged_recalculation_preserves_context_and_score(self):
        report = self.client.get('/api/demo').json()
        self.assertTrue(report['pyqs'])
        self.assertTrue(report['syllabus']['units'][0]['topics'])
        response = self.client.post('/api/recalculate', json={
            'syllabus': report['syllabus'],
            'questions': report['mapped_questions'],
            'pyqs': report['pyqs'],
            'paper_title': report['paper_summary']['paper_title'],
        })
        self.assertEqual(response.status_code, 200)
        updated = response.json()
        self.assertEqual(updated['score_breakdown'], report['score_breakdown'])
        self.assertEqual(updated['syllabus'], report['syllabus'])
        self.assertEqual(updated['pyqs'], report['pyqs'])

    def test_rewrite_is_reaudited_and_generated_question_is_counted(self):
        report = self.client.get('/api/demo').json()
        questions = report['mapped_questions']
        rewritten = questions[0]
        rewritten['question_text'] = 'Explain interstellar quantum teleportation wormholes.'
        rewritten['is_out_of_syllabus'] = False
        added = dict(questions[1], question_id='NEW1')
        questions.append(added)
        response = self.client.post('/api/recalculate', json={
            'syllabus': report['syllabus'], 'questions': questions,
            'pyqs': report['pyqs'],
            'changed_question_ids': [rewritten['question_id'], 'NEW1'],
        })
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result['paper_summary']['total_questions'], len(questions))
        self.assertEqual(result['paper_summary']['total_marks'], sum(q['marks'] for q in questions))
        self.assertTrue(result['mapped_questions'][0]['is_out_of_syllabus'])
        self.assertEqual(result['mapped_questions'][0]['blooms_level'], 'Understand')

    def test_reject_unsupported_upload(self):
        response = self.client.post('/api/audit', files={
            'syllabus_file': ('syllabus.exe', b'not text', 'application/octet-stream')
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn('Only PDF', response.json()['message'])

    def test_upload_and_pasted_text_size_limits(self):
        # A zero-byte test limit lets us exercise both application checks
        # without first hitting Starlette's independent form-field limit.
        with patch.object(settings, 'MAX_UPLOAD_SIZE_MB', 0):
            oversized = 'not empty'
            for kwargs in [
                {'files': {'syllabus_file': ('large.txt', oversized.encode(), 'text/plain')}},
                {'data': {'syllabus_text': oversized}},
            ]:
                response = self.client.post('/api/audit', **kwargs)
                self.assertEqual(response.status_code, 413)

    def test_invalid_text_encoding_is_actionable(self):
        response = self.client.post('/api/audit', files={
            'syllabus_file': ('syllabus.txt', b'\xff\xfe', 'text/plain')
        })
        self.assertEqual(response.status_code, 422)
        self.assertIn('UTF-8', response.json()['message'])

    def test_cors_allows_only_configured_origin(self):
        with patch.object(settings, 'CORS_ORIGINS', ['http://localhost:8000']):
            client = TestClient(create_app())
        for origin, expected in [('http://localhost:8000', 200), ('https://untrusted.example', 400)]:
            response = client.options('/api/health', headers={
                'Origin': origin, 'Access-Control-Request-Method': 'GET'
            })
            self.assertEqual(response.status_code, expected)


if __name__ == '__main__':
    unittest.main()
