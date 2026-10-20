import os
import json
from typing import Optional, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from backend.models import Syllabus, QuestionPaper, PreviousYearQuestion, AuditReport, QuestionItem
from backend.engine.parsers import (
    extract_text_from_pdf, parse_syllabus_text, 
    parse_question_paper_text, parse_pyq_text
)
from backend.engine.auditor import ExamAuditor
from backend.engine.pdf_generator import generate_pdf_report

app = FastAPI(
    title="ExamLens AI API",
    description="Intelligent Examination Quality & Syllabus-Alignment Auditor API",
    version="1.0.0"
)

# Enable CORS for local dev / client flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Locate directories
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(BASE_DIR, "backend", "data")

class RecalculateRequest(BaseModel):
    syllabus: Syllabus
    questions: List[QuestionItem]
    pyqs: Optional[List[PreviousYearQuestion]] = None
    paper_title: Optional[str] = "Draft Examination Paper"

@app.get("/api/health")
def health_check():
    return {"status": "ok", "app": "ExamLens AI", "version": "1.0.0"}

@app.get("/api/demo")
def get_demo_audit():
    """Returns the ready-to-inspect audit analysis for the CS201 demo course."""
    try:
        syl_path = os.path.join(DATA_DIR, "demo_syllabus_cs201.json")
        paper_path = os.path.join(DATA_DIR, "demo_paper_cs201.json")
        pyq_path = os.path.join(DATA_DIR, "demo_pyq_cs201.json")

        with open(syl_path, "r", encoding="utf-8") as f:
            syllabus = Syllabus(**json.load(f))
        with open(paper_path, "r", encoding="utf-8") as f:
            paper = QuestionPaper(**json.load(f))
        with open(pyq_path, "r", encoding="utf-8") as f:
            pyqs = [PreviousYearQuestion(**item) for item in json.load(f)]

        auditor = ExamAuditor(syllabus=syllabus, paper=paper, pyqs=pyqs)
        report = auditor.run_full_audit()
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate demo audit: {str(e)}")

@app.post("/api/audit")
async def audit_examination(
    syllabus_file: Optional[UploadFile] = File(None),
    syllabus_text: Optional[str] = Form(None),
    paper_file: Optional[UploadFile] = File(None),
    paper_text: Optional[str] = Form(None),
    pyq_file: Optional[UploadFile] = File(None),
    pyq_text: Optional[str] = Form(None)
):
    """
    Uploads syllabus and question paper documents (PDF or Text) and executes full audit.
    """
    try:
        # 1. Process Syllabus
        raw_syl = ""
        if syllabus_file:
            content = await syllabus_file.read()
            if syllabus_file.filename.lower().endswith(".pdf"):
                raw_syl = extract_text_from_pdf(content)
            else:
                raw_syl = content.decode("utf-8", errors="ignore")
        elif syllabus_text:
            raw_syl = syllabus_text
        else:
            raise HTTPException(status_code=400, detail="Syllabus file or text is required.")

        syllabus = parse_syllabus_text(raw_syl)

        # 2. Process Question Paper
        raw_paper = ""
        if paper_file:
            content = await paper_file.read()
            if paper_file.filename.lower().endswith(".pdf"):
                raw_paper = extract_text_from_pdf(content)
            else:
                raw_paper = content.decode("utf-8", errors="ignore")
        elif paper_text:
            raw_paper = paper_text
        else:
            raise HTTPException(status_code=400, detail="Question paper file or text is required.")

        paper = parse_question_paper_text(raw_paper)

        # 3. Process PYQ (Optional)
        pyqs = []
        raw_pyq = ""
        if pyq_file:
            content = await pyq_file.read()
            if pyq_file.filename.lower().endswith(".pdf"):
                raw_pyq = extract_text_from_pdf(content)
            else:
                raw_pyq = content.decode("utf-8", errors="ignore")
            pyqs = parse_pyq_text(raw_pyq)
        elif pyq_text and pyq_text.strip():
            pyqs = parse_pyq_text(pyq_text)

        # 4. Run Audit
        auditor = ExamAuditor(syllabus=syllabus, paper=paper, pyqs=pyqs)
        report = auditor.run_full_audit()
        return report

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit execution error: {str(e)}")

@app.post("/api/recalculate")
def recalculate_audit(req: RecalculateRequest):
    """Recalculates coverage and quality score after faculty overrides."""
    try:
        total_marks = sum(q.marks for q in req.questions)
        paper = QuestionPaper(
            paper_title=req.paper_title or "Examination Paper",
            course_code=req.syllabus.course_code,
            total_marks=total_marks,
            questions=req.questions
        )
        auditor = ExamAuditor(syllabus=req.syllabus, paper=paper, pyqs=req.pyqs or [])
        report = auditor.recalculate_with_overrides(req.questions)
        return report
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Recalculation error: {str(e)}")

@app.post("/api/export-pdf")
def export_pdf(report: AuditReport):
    """Generates and streams a formal PDF audit certificate report."""
    try:
        pdf_bytes = generate_pdf_report(report)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename=ExamLens_Audit_{report.syllabus_summary.get('course_code', 'Report')}.pdf"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF generation error: {str(e)}")

# Mount frontend static directory
if os.path.exists(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_frontend():
    index_file = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "ExamLens AI backend is active. Frontend is loading..."}
