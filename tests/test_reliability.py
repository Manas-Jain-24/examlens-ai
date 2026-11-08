import copy
import io
import json
from pathlib import Path
import subprocess
import shutil
import tempfile
import time
import unittest
from httpx import ReadTimeout
from types import SimpleNamespace
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pypdf import PdfWriter
from reportlab.pdfgen.canvas import Canvas

from backend.app import app
from backend.core.config import settings
from backend.engine.choices import choice_accounting
from backend.engine.gemini_service import GeminiService
from backend.engine.pdf_extraction import extract_pdf_document, _ocr_page
from backend.models import AIRewriteRequest, AIGenerateQuestionRequest, QuestionItem


def pdf_bytes(pages):
    output = io.BytesIO()
    canvas = Canvas(output)
    for text in pages:
        if text:
            canvas.drawString(40, 720, text)
        canvas.showPage()
    canvas.save()
    return output.getvalue()


class TestProviderReliability(unittest.TestCase):
    def setUp(self):
        self.service = GeminiService(api_key='', model_name='test-model')
        self.request = AIRewriteRequest(question_text='Define arrays', target_blooms_level='Analyze', marks=5)

    def test_explicit_empty_key_does_not_use_environment_key(self):
        with patch.object(settings, 'GEMINI_API_KEY', 'not-a-real-key'):
            service = GeminiService(api_key='', model_name='test-model')
        self.assertIsNone(service.client)
        result = service.rewrite_question(self.request)
        self.assertEqual(result.fallback_reason, 'no_api_key')
        self.assertFalse(result.is_ai_generated)

    def test_model_is_required_and_timeout_is_configured(self):
        service = GeminiService(api_key='test-key', model_name='')
        self.assertIsNone(service.client)
        self.assertEqual(service.configuration_reason, 'model_not_configured')
        with patch('backend.engine.gemini_service.genai.Client') as factory:
            GeminiService(api_key='test-key', model_name='selected-model')
        options = factory.call_args.kwargs['http_options']
        self.assertEqual(options.timeout, settings.AI_TIMEOUT_SECONDS * 1000)
        self.assertEqual(options.retry_options.attempts, 1)

    def test_timeout_returns_labeled_template_without_secret(self):
        self.service.client = Mock()
        self.service.client.models.generate_content.side_effect = TimeoutError('private-key-must-not-appear')
        result = self.service.rewrite_question(self.request)
        self.assertEqual(result.fallback_reason, 'provider_timeout')
        self.assertNotIn('private-key-must-not-appear', result.model_dump_json())
        self.service.client.models.generate_content.side_effect = ReadTimeout('transport timeout')
        self.assertEqual(self.service.rewrite_question(self.request).fallback_reason, 'provider_timeout')

    def test_invalid_json_and_incomplete_output_fall_back(self):
        self.service.client = Mock()
        for text in ['not JSON', '[]', '{}', '{"unrelated": "value"}', '{"rewritten_question":"", "command_verb":"Analyze", "pedagogical_rationale":"x"}']:
            self.service.client.models.generate_content.return_value = SimpleNamespace(text=text)
            result = self.service.rewrite_question(self.request)
            self.assertFalse(result.is_ai_generated, text)
            self.assertEqual(result.fallback_reason, 'provider_error_or_invalid_response')

    def test_live_result_names_actual_model(self):
        self.service.client = Mock()
        self.service.client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({
            'rewritten_question': 'Analyze arrays with a worked example.', 'command_verb': 'Analyze',
            'pedagogical_rationale': 'Requires comparing cases.'}))
        result = self.service.rewrite_question(self.request)
        self.assertTrue(result.is_ai_generated)
        self.assertEqual(result.model_name, 'test-model')
        self.assertEqual(result.engine, 'gemini')
        self.assertIsNone(result.fallback_reason)

    def test_template_generation_respects_level_and_non_ten_marks(self):
        request = AIGenerateQuestionRequest(course_name='Biology', course_code='BIO101', unit_number=1,
            unit_title='Cells', unit_topics=['Cell membranes'], target_blooms_level='Evaluate', marks=5)
        result = self.service.generate_unit_questions(request)
        self.assertTrue(all(q.blooms_level == 'Evaluate' and q.marks == 5 for q in result.candidates))
        self.assertIn('3M', result.candidates[0].sample_solution_outline)
        self.assertIn('2M', result.candidates[0].sample_solution_outline)


class TestPdfExtraction(unittest.TestCase):
    @unittest.skipUnless(shutil.which('tesseract') and shutil.which('pdftoppm'), 'Local Tesseract/Poppler integration tools are not installed')
    def test_real_local_ocr_reads_image_only_pdf(self):
        with tempfile.TemporaryDirectory(prefix='examlens-ocr-test-') as folder:
            source = Path(folder) / 'native.pdf'
            source.write_bytes(pdf_bytes(['Q1. Define arrays. (5 Marks)']))
            prefix = Path(folder) / 'raster'
            subprocess.run([shutil.which('pdftoppm'), '-singlefile', '-scale-to', '2400', '-png', str(source), str(prefix)],
                           check=True, capture_output=True, timeout=20)
            scanned = io.BytesIO()
            canvas = Canvas(scanned)
            canvas.drawImage(str(prefix) + '.png', 0, 0, width=612, height=792)
            canvas.showPage(); canvas.save()
            with patch.object(settings, 'OCR_ENABLED', True), patch.object(settings, 'TESSERACT_CMD', 'tesseract'), patch.object(settings, 'PDF_RENDERER_CMD', 'pdftoppm'):
                result = extract_pdf_document(scanned.getvalue())
            self.assertEqual(result.pages[0]['method'], 'ocr')
            self.assertIn('arrays', result.text.lower())

    def test_native_text_never_needs_ocr(self):
        with patch.object(settings, 'OCR_ENABLED', True), patch('backend.engine.pdf_extraction._ocr_page') as ocr:
            result = extract_pdf_document(pdf_bytes(['Q1. Explain the properties of arrays. (5 Marks)']))
        self.assertIn('arrays', result.text)
        self.assertEqual(result.pages[0]['method'], 'native')
        ocr.assert_not_called()

    def test_blank_scan_reports_setup_instructions(self):
        with patch.object(settings, 'OCR_ENABLED', False):
            with self.assertRaisesRegex(ValueError, 'Tesseract'):
                extract_pdf_document(pdf_bytes(['']))

    def test_ocr_text_and_warnings_return_to_preview(self):
        with patch.object(settings, 'OCR_ENABLED', True), patch('backend.engine.pdf_extraction._ocr_page', return_value='Q1. Define arrays. (5 Marks)'):
            result = extract_pdf_document(pdf_bytes(['']))
        self.assertEqual(result.pages[0]['method'], 'ocr')
        self.assertTrue(any('verify' in warning for warning in result.warnings))

    def test_mixed_documents_do_not_silently_drop_blank_pages(self):
        with patch.object(settings, 'OCR_ENABLED', False):
            result = extract_pdf_document(pdf_bytes(['Q1. Explain arrays with a detailed example.', '']))
        self.assertEqual(len(result.pages), 2)
        self.assertTrue(any('Page 2' in warning for warning in result.warnings))

    def test_page_limit_and_encrypted_pdf(self):
        with patch.object(settings, 'MAX_PDF_PAGES', 1):
            with self.assertRaisesRegex(ValueError, 'page limit'):
                extract_pdf_document(pdf_bytes(['one', 'two']))
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.encrypt('test-password')
        output = io.BytesIO(); writer.write(output)
        with self.assertRaisesRegex(ValueError, 'Password-protected'):
            extract_pdf_document(output.getvalue())

    def test_missing_engine_and_process_timeout_are_actionable(self):
        with patch('backend.engine.pdf_extraction.shutil.which', return_value=None):
            with self.assertRaisesRegex(ValueError, 'Tesseract and Poppler'):
                _ocr_page(b'pdf', 1, time.monotonic() + 5)
        with patch('backend.engine.pdf_extraction.shutil.which', side_effect=['renderer', 'engine']), patch('backend.engine.pdf_extraction.subprocess.run', side_effect=subprocess.TimeoutExpired('renderer', 1)):
            with self.assertRaisesRegex(ValueError, 'time limit'):
                _ocr_page(b'pdf', 1, time.monotonic() + 5)


class TestBackupsAndAllocations(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.setting_patch = patch.object(settings, 'HISTORY_DB_PATH', str(Path(self.temp.name) / 'db.sqlite3'))
        self.setting_patch.start(); self.addCleanup(self.setting_patch.stop)
        self.client = TestClient(app)

    def report(self):
        return self.client.get('/api/demo').json()

    def restore(self, bundle):
        return self.client.post('/api/backups/restore', files={'file': ('backup.json', json.dumps(bundle).encode(), 'application/json')})

    def test_backup_round_trip_preserves_revisions_and_never_overwrites(self):
        report = self.report()
        first = self.client.post('/api/history', json={'title': 'Course audit', 'report': report, 'note': 'First review'}).json()
        self.client.post('/api/history', json={'title': 'Course audit', 'report': report, 'audit_id': first['audit_id'], 'expected_revision': 1})
        exported = self.client.get('/api/backups/export')
        self.assertEqual(exported.status_code, 200)
        bundle = exported.json()
        self.assertEqual(len(bundle['audits'][0]['revisions']), 2)
        restored = self.restore(bundle)
        self.assertEqual(restored.status_code, 200, restored.text)
        result = restored.json()
        self.assertEqual(result['revisions_restored'], 2)
        new_id = result['audit_id_map'][first['audit_id']]
        self.assertNotEqual(new_id, first['audit_id'])
        copied = self.client.get(f'/api/history/{new_id}/revisions/1').json()
        self.assertEqual(copied['note'], 'First review')
        self.assertEqual(copied['report'], report)
        self.assertEqual(len(self.client.get('/api/history').json()), 2)

    def test_invalid_restore_leaves_existing_data_unchanged(self):
        self.client.post('/api/history', json={'title': 'Saved', 'report': self.report()})
        bundle = self.client.get('/api/backups/export').json()
        bundle['audits'][0]['revisions'][0]['revision'] = 4
        self.assertEqual(self.restore(bundle).status_code, 422)
        self.assertEqual(len(self.client.get('/api/history').json()), 1)
        self.assertEqual(self.restore({'format': 'unknown', 'version': 99}).status_code, 422)
        bad_json = self.client.post('/api/backups/restore', files={'file': ('bad.json', b'not json')})
        self.assertEqual(bad_json.status_code, 422)

    def test_backup_never_exports_environment_keys(self):
        with patch.object(settings, 'GEMINI_API_KEY', 'private-backup-test-key'):
            exported = self.client.get('/api/backups/export')
        self.assertNotIn('private-backup-test-key', exported.text)

    def test_restore_transaction_rolls_back_if_a_later_insert_fails(self):
        from backend.storage import database
        report = self.report()
        for title in ['First audit', 'Second audit']:
            self.client.post('/api/history', json={'title': title, 'report': report})
        bundle = self.client.get('/api/backups/export').json()
        existing_id = bundle['audits'][0]['source_id']
        client = TestClient(app, raise_server_exceptions=False)
        with patch('backend.api.routers.backups.uuid4', side_effect=['rollback-test-new-id', existing_id]):
            result = client.post('/api/backups/restore', files={'file': ('backup.json', json.dumps(bundle).encode())})
        self.assertEqual(result.status_code, 500)
        with database() as connection:
            count = connection.execute('SELECT COUNT(*) FROM revisions WHERE audit_id=?', ('rollback-test-new-id',)).fetchone()[0]
        self.assertEqual(count, 0)
        self.assertEqual(len(self.client.get('/api/history').json()), 2)

    def test_restore_evaluation_examples_as_new_copies(self):
        example = self.client.get('/api/evaluation/examples').json()[0]
        self.client.put(f"/api/evaluation/examples/{example['example_id']}", json=example)
        bundle = self.client.get('/api/backups/export').json()
        restored = self.restore(bundle).json()
        self.assertEqual(restored['examples_restored'], 1)
        new_id = restored['example_id_map'][example['example_id']]
        examples = self.client.get('/api/evaluation/examples').json()
        copied = next(e for e in examples if e['example_id'] == new_id)
        self.assertIsNone(copied['reviewed_at'])

    def test_multi_unit_marks_are_not_double_counted(self):
        report = self.report()
        question = report['mapped_questions'][0]
        question['unit_allocations'] = {'1': 2, '4': 3}
        response = self.client.post('/api/recalculate', json={
            'syllabus': report['syllabus'], 'questions': report['mapped_questions'], 'pyqs': report['pyqs'],
            'rules': report['rules'], 'choice_groups': report['choice_groups']})
        self.assertEqual(response.status_code, 200, response.text)
        changed = response.json()
        self.assertEqual(changed['paper_summary']['total_marks'], report['paper_summary']['total_marks'])
        u4 = next(u for u in changed['unit_coverage'] if u['unit_number'] == 4)
        self.assertEqual(u4['guaranteed_marks'], 3)
        self.assertEqual(sum(u['total_marks'] for u in changed['unit_coverage']), changed['paper_summary']['total_marks'])

    def test_allocations_reject_unknown_units_and_wrong_totals(self):
        with self.assertRaises(ValidationError):
            QuestionItem(question_id='Q1', question_text='Explain arrays', marks=10, unit_allocations={1: 8})
        report = self.report()
        report['mapped_questions'][0]['unit_allocations'] = {'99': 5}
        response = self.client.post('/api/recalculate', json={
            'syllabus': report['syllabus'], 'questions': report['mapped_questions']})
        self.assertEqual(response.status_code, 422)

    def test_mark_splits_work_with_optional_questions(self):
        from backend.models import QuestionPaper, ChoiceGroup
        paper = QuestionPaper(paper_title='Choices', course_code='CS201', total_marks=20,
            questions=[QuestionItem(question_id='Q1', question_text='Arrays and stacks', marks=10, unit_allocations={1: 4, 2: 6}),
                       QuestionItem(question_id='Q2', question_text='Arrays', marks=10, mapped_unit=1)],
            choice_groups=[ChoiceGroup(group_id='OR1', question_ids=['Q1','Q2'], choose=1)])
        self.assertEqual(choice_accounting(paper, 1)[1:], (7, 4, 10))
        self.assertEqual(choice_accounting(paper, 2)[1:], (3, 0, 6))

    def test_rewrite_clears_stale_allocations(self):
        report = self.report()
        question = report['mapped_questions'][0]
        question['unit_allocations'] = {'1': 2, '4': 3}
        question['question_text'] = 'Explain graph representations.'
        response = self.client.post('/api/recalculate', json={'syllabus': report['syllabus'],
            'questions': report['mapped_questions'], 'changed_question_ids': [question['question_id']]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mapped_questions'][0]['unit_allocations'], {})


if __name__ == '__main__':
    unittest.main()
