from fastapi import APIRouter, Response
from backend.core.logger import logger
from backend.core.exceptions import AuditExecutionError
from backend.models import AuditReport
from backend.engine.pdf_generator import generate_pdf_report

router = APIRouter(tags=["Reports"])

@router.post("/export-pdf")
def export_pdf(report: AuditReport):
    """Generates and streams a formal institutional PDF audit certificate report."""
    try:
        course_code = report.syllabus_summary.get("course_code", "Report")
        logger.info(f"Generating PDF audit report for course: {course_code}...")
        pdf_bytes = generate_pdf_report(report)
        logger.info(f"PDF audit report successfully generated ({len(pdf_bytes)} bytes).")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=ExamLens_Audit_{course_code}.pdf"
            }
        )
    except Exception as e:
        logger.exception(f"PDF generation error: {str(e)}")
        raise AuditExecutionError(f"PDF generation failed: {str(e)}")
