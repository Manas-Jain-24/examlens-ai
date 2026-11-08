import re
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from backend.api.routers.audit import _extract_content
from backend.engine.parsers import parse_syllabus_text, parse_question_paper_text, parse_pyq_text
from backend.engine.auditor import ExamAuditor
from backend.models import ReviewedDraft, AuditReport

router = APIRouter(tags=['Document review'])


@router.post('/parse', response_model=ReviewedDraft)
async def preview_documents(
    syllabus_file: Optional[UploadFile] = File(None), syllabus_text: Optional[str] = Form(None),
    paper_file: Optional[UploadFile] = File(None), paper_text: Optional[str] = Form(None),
    pyq_file: Optional[UploadFile] = File(None), pyq_text: Optional[str] = Form(None)
):
    sources = {
        'syllabus': await _extract_content(syllabus_file, syllabus_text, 'Syllabus'),
        'paper': await _extract_content(paper_file, paper_text, 'Question Paper'),
        'pyq': await _extract_content(pyq_file, pyq_text, 'Previous Year Questions'),
    }
    if not sources['syllabus'] or not sources['paper']:
        raise HTTPException(422, 'Syllabus and question paper are required.')
    syllabus = parse_syllabus_text(sources['syllabus'])
    paper = parse_question_paper_text(sources['paper'])
    warnings = list(paper.parsing_warnings)
    if not re.search(r'^\s*(unit|module|chapter|part)\s*[0-9ivx]+', sources['syllabus'], re.I | re.M):
        warnings.append('No unit headings detected. The inferred syllabus structure must be corrected before auditing.')
    if not any(u.learning_outcomes for u in syllabus.units):
        warnings.append('No learning outcomes detected; add them to enable meaningful outcome scoring.')
    if sources['pyq'] and not parse_pyq_text(sources['pyq']):
        warnings.append('No previous-year questions detected. Correct them in the review.')
    return ReviewedDraft(syllabus=syllabus, paper=paper, pyqs=parse_pyq_text(sources['pyq']),
                         warnings=warnings, source_texts=sources)


@router.post('/audit-reviewed', response_model=AuditReport)
def audit_reviewed(draft: ReviewedDraft):
    if not draft.paper.questions:
        raise HTTPException(422, 'Add at least one question before auditing.')
    # Never trust analysis annotations in a corrected source document.
    for question in draft.paper.questions:
        question.blooms_level = None
        question.review_status = 'pending'
    try:
        return ExamAuditor(draft.syllabus, draft.paper, draft.pyqs, draft.rules).run_full_audit()
    except ValueError as exc:
        raise HTTPException(422, str(exc))
