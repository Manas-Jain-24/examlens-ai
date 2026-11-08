import io
import re
import json
from typing import List, Dict, Any, Optional
from pypdf import PdfReader
from backend.models import Syllabus, SyllabusUnit, QuestionPaper, QuestionItem, PreviousYearQuestion

def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extracts raw text from PDF bytes using pypdf."""
    from backend.engine.pdf_extraction import extract_pdf_document
    return extract_pdf_document(pdf_bytes).text

def parse_syllabus_text(text: str) -> Syllabus:
    """
    Intelligently parses syllabus text into Course, Units, Topics, and Learning Outcomes.
    Supports formats like 'Unit 1: Title\n- Topic A\n- Topic B'
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    
    # Try to detect course name and code
    course_name = "Course Syllabus"
    course_code = "SUB101"
    
    for line in lines[:8]:
        code_match = re.search(r'\b([A-Z]{2,4}\s?[0-9]{3,4})\b', line)
        if code_match:
            course_code = code_match.group(1).replace(" ", "")
        if any(term in line.lower() for term in ["course", "subject", "paper", "syllabus"]) and len(line) < 60:
            cleaned = re.sub(r'(course|subject|syllabus|name|title|code)[\s:\-]+', '', line, flags=re.I).strip()
            if cleaned:
                course_name = cleaned

    units: List[SyllabusUnit] = []
    current_unit: Optional[Dict[str, Any]] = None
    
    # Regex to detect unit headers
    unit_header_pattern = re.compile(
        r'^(?:unit|module|chapter|part)\s*([0-9ivx]+)[\s:\.\-]+(.*)', 
        re.IGNORECASE
    )

    for line in lines:
        match = unit_header_pattern.match(line)
        if match:
            # Save previous unit if exists
            if current_unit:
                units.append(SyllabusUnit(
                    unit_number=current_unit["number"],
                    title=current_unit["title"] or f"Unit {current_unit['number']}",
                    topics=current_unit["topics"] or ["General Concepts"],
                    learning_outcomes=current_unit["learning_outcomes"]
                ))
            
            raw_num = match.group(1).lower()
            # Roman numeral conversion
            roman_map = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}
            unit_num = roman_map.get(raw_num, int(raw_num) if raw_num.isdigit() else len(units) + 1)
            title = match.group(2).strip()
            
            current_unit = {
                "number": unit_num,
                "title": title,
                "topics": [],
                "learning_outcomes": []
            }
        else:
            if current_unit:
                # Detect Learning Outcomes
                if any(k in line.lower() for k in ["learning outcome", "course outcome", "co:", "lo:", "outcome"]):
                    cleaned_lo = re.sub(r'^(?:co|lo|outcome)[\s0-9:\.\-]+', '', line, flags=re.I).strip()
                    if cleaned_lo:
                        current_unit["learning_outcomes"].append(cleaned_lo)
                else:
                    # Treat as topic item
                    cleaned_topic = re.sub(r'^[\-\*\•\d\.\)]+\s*', '', line).strip()
                    if len(cleaned_topic) > 2:
                        current_unit["topics"].append(cleaned_topic)

    # Append last unit
    if current_unit:
        units.append(SyllabusUnit(
            unit_number=current_unit["number"],
            title=current_unit["title"] or f"Unit {current_unit['number']}",
            topics=current_unit["topics"] or ["General Concepts"],
            learning_outcomes=current_unit["learning_outcomes"]
        ))

    # Fallback if no explicit "Unit X" markers were found
    if not units:
        units = [
            SyllabusUnit(
                unit_number=1,
                title="Foundational Concepts",
                topics=lines[:len(lines)//2] or ["General Theory"],
                learning_outcomes=["Understand fundamental concepts"]
            ),
            SyllabusUnit(
                unit_number=2,
                title="Advanced Applications",
                topics=lines[len(lines)//2:] or ["Application and Implementation"],
                learning_outcomes=["Apply concepts to solve problems"]
            )
        ]

    return Syllabus(
        course_name=course_name,
        course_code=course_code,
        units=units
    )

def parse_question_paper_text(text: str) -> QuestionPaper:
    from backend.engine.paper_parser import parse_paper
    return parse_paper(text)


def parse_pyq_text(text: str, default_year: str = "2025") -> List[PreviousYearQuestion]:
    """Parses previous year question paper text into a structured list."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    pyqs: List[PreviousYearQuestion] = []
    q_pattern = re.compile(
        r'^(?:q(?:uestion)?[\s\.]*)?([0-9]{1,2}(?:\([a-z0-9]+\)|[a-z])?)[\.\:\)\s\-]+(.*)',
        re.IGNORECASE
    )
    
    current_year = default_year
    for line in lines:
        year_match = re.search(r'\b(20[12][0-9])\b', line)
        if year_match:
            current_year = year_match.group(1)

        match = q_pattern.match(line)
        if match:
            q_id = f"Q{match.group(1).upper()}"
            q_text = match.group(2).strip()
            pyqs.append(PreviousYearQuestion(
                paper_year=f"Final Exam {current_year}",
                question_id=q_id,
                question_text=q_text,
                marks=10.0
            ))
            
    return pyqs
