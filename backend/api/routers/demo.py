import os
import json
from fastapi import APIRouter
from backend.core.config import settings
from backend.core.logger import logger
from backend.core.exceptions import ResourceNotFoundError, AuditExecutionError
from backend.models import Syllabus, QuestionPaper, PreviousYearQuestion, AuditReport
from backend.engine.auditor import ExamAuditor

router = APIRouter(tags=["Demo"])

@router.get("/demo", response_model=AuditReport)
def get_demo_audit():
    """Returns the ready-to-inspect audit analysis for the preloaded CS201 course."""
    syl_path = os.path.join(settings.DATA_DIR, "demo_syllabus_cs201.json")
    paper_path = os.path.join(settings.DATA_DIR, "demo_paper_cs201.json")
    pyq_path = os.path.join(settings.DATA_DIR, "demo_pyq_cs201.json")

    for path, name in [(syl_path, "Syllabus"), (paper_path, "Question Paper"), (pyq_path, "PYQ Data")]:
        if not os.path.exists(path):
            logger.error(f"Demo file missing: {path}")
            raise ResourceNotFoundError(f"Demo {name} file not found at {path}")

    try:
        with open(syl_path, "r", encoding="utf-8") as f:
            syllabus = Syllabus(**json.load(f))
        with open(paper_path, "r", encoding="utf-8") as f:
            paper = QuestionPaper(**json.load(f))
        with open(pyq_path, "r", encoding="utf-8") as f:
            pyqs = [PreviousYearQuestion(**item) for item in json.load(f)]

        logger.info(f"Running demo audit for {syllabus.course_code}: {syllabus.course_name}")
        auditor = ExamAuditor(syllabus=syllabus, paper=paper, pyqs=pyqs)
        report = auditor.run_full_audit()
        logger.info(f"Demo audit completed with score: {report.overall_quality_score} ({report.grade})")
        return report

    except Exception as e:
        logger.exception(f"Failed to generate demo audit: {str(e)}")
        raise AuditExecutionError(f"Failed to generate demo audit: {str(e)}")
