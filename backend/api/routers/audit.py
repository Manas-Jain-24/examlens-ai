from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, status, HTTPException
from backend.core.config import settings
from backend.core.logger import logger
from backend.core.exceptions import DocumentParsingError, AuditExecutionError, PayloadTooLargeError
from backend.models import (
    Syllabus, QuestionPaper, AuditReport, RecalculateRequest, ReviewedDraft
)
from backend.engine.parsers import (
    extract_text_from_pdf, parse_syllabus_text,
    parse_question_paper_text, parse_pyq_text
)
from backend.engine.auditor import ExamAuditor
from backend.engine.blooms_classifier import classify_blooms_taxonomy

router = APIRouter(tags=["Audit"])

async def _extract_content(file: Optional[UploadFile], text: Optional[str], field_name: str) -> str:
    """Helper to validate file sizes and extract clean text from either an upload or raw text."""
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    if file:
        content = await file.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise PayloadTooLargeError(
                f"{field_name} file exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB."
            )

        filename = file.filename or ""
        if not filename.lower().endswith((".pdf", ".txt")):
            raise DocumentParsingError("Only PDF and UTF-8 .txt documents are supported.")
        logger.info(f"Processing uploaded {field_name}: {filename} ({len(content)} bytes)")

        if filename.lower().endswith(".pdf"):
            try:
                extracted = extract_text_from_pdf(content)
                if not extracted.strip():
                    raise DocumentParsingError(f"No readable text could be extracted from {filename}. It may be scanned or image-only.")
                return extracted
            except Exception as e:
                raise DocumentParsingError(f"Failed to read PDF {filename}: {str(e)}")
        else:
            try:
                return content.decode("utf-8-sig")
            except UnicodeDecodeError:
                raise DocumentParsingError(f"{field_name} must be a UTF-8 text file.")

    elif text and text.strip():
        if len(text.encode("utf-8")) > max_bytes:
            raise PayloadTooLargeError(f"{field_name} text exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.")
        return text.strip()

    return ""

@router.post("/audit", response_model=AuditReport)
async def audit_examination(
    syllabus_file: Optional[UploadFile] = File(None),
    syllabus_text: Optional[str] = Form(None),
    paper_file: Optional[UploadFile] = File(None),
    paper_text: Optional[str] = Form(None),
    pyq_file: Optional[UploadFile] = File(None),
    pyq_text: Optional[str] = Form(None)
):
    """
    Uploads syllabus and question paper documents (PDF or text) and executes
    comprehensive examination quality, coverage, cognitive balance, and PYQ audit.
    """
    # 1. Extract syllabus text
    raw_syl = await _extract_content(syllabus_file, syllabus_text, "Syllabus")
    if not raw_syl:
        raise DocumentParsingError("Syllabus document (file upload or pasted text) is required.")

    # 2. Extract question paper text
    raw_paper = await _extract_content(paper_file, paper_text, "Question Paper")
    if not raw_paper:
        raise DocumentParsingError("Question paper document (file upload or pasted text) is required.")

    # 3. Extract PYQ text (optional)
    raw_pyq = await _extract_content(pyq_file, pyq_text, "Previous Year Question Paper")

    try:
        logger.info("Parsing uploaded syllabus and question paper documents...")
        syllabus = parse_syllabus_text(raw_syl)
        paper = parse_question_paper_text(raw_paper)
        if not paper.questions:
            raise DocumentParsingError('No numbered questions detected. Use document preview to add or correct questions.')
        pyqs = parse_pyq_text(raw_pyq) if raw_pyq else []

        logger.info(
            f"Audit parsed: Syllabus '{syllabus.course_code}' with {len(syllabus.units)} units; "
            f"Paper with {len(paper.questions)} questions ({paper.total_marks} Marks); "
            f"{len(pyqs)} PYQs."
        )

        auditor = ExamAuditor(syllabus=syllabus, paper=paper, pyqs=pyqs)
        report = auditor.run_full_audit()
        logger.info(f"Audit completed: Overall Score = {report.overall_quality_score} ({report.grade})")
        return report

    except DocumentParsingError:
        raise
    except Exception as e:
        logger.exception(f"Unexpected audit execution error: {str(e)}")
        raise AuditExecutionError(f"Audit execution failed: {str(e)}")

@router.post("/recalculate", response_model=AuditReport)
def recalculate_audit(req: RecalculateRequest):
    """
    Recalculates syllabus coverage, cognitive metrics, and exam quality score
    after faculty overrides or edits in the review table.
    """
    try:
        total_marks = sum(q.marks for q in req.questions)
        paper = QuestionPaper(
            paper_title=req.paper_title or "Examination Paper",
            course_code=req.syllabus.course_code,
            total_marks=total_marks,
            questions=req.questions,
            choice_groups=req.choice_groups
        )
        ReviewedDraft(syllabus=req.syllabus, paper=paper, pyqs=req.pyqs or [], rules=req.rules)
        if not req.questions:
            raise ValueError('At least one question is required.')
        units = {u.unit_number: u for u in req.syllabus.units}
        for q in req.questions:
            if q.mapped_unit not in units:
                raise ValueError(f'{q.question_id}: choose an existing syllabus unit.')
            # Outcomes must belong to the faculty-selected unit.
            q.mapped_outcomes = [lo for lo in q.mapped_outcomes if lo in units[q.mapped_unit].learning_outcomes]
        logger.info(f"Recalculating audit with {len(req.questions)} questions ({total_marks} Marks)...")
        auditor = ExamAuditor(syllabus=req.syllabus, paper=paper, pyqs=req.pyqs or [], rules=req.rules)
        # A rewrite is a new question: re-check its alignment and cognitive level
        # rather than trusting the old question's annotations.
        changed = [q for q in req.questions if q.question_id in req.changed_question_ids]
        auditor.mapper.map_questions(changed)
        for q in changed:
            q.blooms_level, q.command_verb, _ = classify_blooms_taxonomy(q.question_text)
            q.review_status = 'pending'
        report = auditor.recalculate_with_overrides(req.questions)
        logger.info(f"Recalculation complete: New Score = {report.overall_quality_score}")
        return report

    except ValueError as e:
        raise HTTPException(422, str(e))
    except Exception as e:
        logger.exception(f"Recalculation error: {str(e)}")
        raise AuditExecutionError(f"Recalculation failed: {str(e)}")
