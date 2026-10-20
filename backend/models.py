import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SyllabusUnit(BaseModel):
    unit_number: int
    title: str
    topics: List[str]
    learning_outcomes: List[str] = Field(default_factory=list)
    recommended_weightage_percent: Optional[float] = None

class Syllabus(BaseModel):
    course_name: str
    course_code: str
    department: Optional[str] = "Computer Science and Engineering"
    semester: Optional[int] = 3
    total_credits: Optional[int] = 4
    units: List[SyllabusUnit]

class QuestionItem(BaseModel):
    question_id: str
    section: str = "Part A"
    question_text: str
    marks: float
    question_type: Optional[str] = "Descriptive"
    command_verb: Optional[str] = None
    mapped_unit: Optional[int] = None
    mapped_outcomes: List[str] = Field(default_factory=list)
    blooms_level: Optional[str] = None
    mapping_confidence: float = 0.0
    is_out_of_syllabus: bool = False
    out_of_syllabus_reason: Optional[str] = None
    pyq_similarity: Optional[float] = None
    pyq_matched_question: Optional[str] = None

class QuestionPaper(BaseModel):
    paper_title: str
    course_code: str
    total_marks: float
    duration_minutes: Optional[int] = 180
    questions: List[QuestionItem]

class PreviousYearQuestion(BaseModel):
    paper_year: str
    question_id: str
    question_text: str
    marks: float
    unit: Optional[int] = None

class AuditFinding(BaseModel):
    finding_id: str
    category: str  # "Coverage", "Weightage", "Blooms", "Out-of-Syllabus", "Repetition", "Balance"
    severity: str  # "High", "Medium", "Low", "Info"
    title: str
    message: str
    related_units: List[int] = Field(default_factory=list)
    related_questions: List[str] = Field(default_factory=list)
    recommended_action: str

class UnitCoverageStat(BaseModel):
    unit_number: int
    unit_title: str
    topics_count: int
    questions_count: int
    total_marks: float
    marks_percentage: float
    expected_weightage_percent: float
    coverage_status: str  # "Well Covered", "Underrepresented", "Not Assessed", "Overrepresented"

class BloomsDistributionStat(BaseModel):
    level: str  # Remember, Understand, Apply, Analyze, Evaluate, Create
    marks: float
    percentage: float
    question_count: int

class ScoreBreakdown(BaseModel):
    syllabus_coverage_score: float  # 0-100 (weight: 25%)
    learning_outcomes_score: float  # 0-100 (weight: 20%)
    marks_distribution_score: float # 0-100 (weight: 20%)
    blooms_cognitive_score: float   # 0-100 (weight: 15%)
    out_of_syllabus_score: float    # 0-100 (weight: 10%)
    repetition_risk_score: float    # 0-100 (weight: 10%)

class AuditReport(BaseModel):
    overall_quality_score: float
    grade: str
    verdict_summary: str
    score_breakdown: ScoreBreakdown
    syllabus_summary: Dict[str, Any]
    paper_summary: Dict[str, Any]
    unit_coverage: List[UnitCoverageStat]
    blooms_distribution: List[BloomsDistributionStat]
    findings: List[AuditFinding]
    mapped_questions: List[QuestionItem]
