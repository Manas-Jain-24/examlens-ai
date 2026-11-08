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
    syllabus: Optional[Syllabus] = None
    pyqs: List[PreviousYearQuestion] = Field(default_factory=list)
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

class RecalculateRequest(BaseModel):
    changed_question_ids: List[str] = Field(default_factory=list)
    syllabus: Syllabus
    questions: List[QuestionItem]
    pyqs: Optional[List[PreviousYearQuestion]] = None
    paper_title: Optional[str] = "Draft Examination Paper"

class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: Optional[str] = "development"
    debug: bool = False

# --- AI Engine Models (Phase 2) ---

class AIRewriteRequest(BaseModel):
    question_text: str
    current_blooms_level: Optional[str] = "Understand"
    target_blooms_level: Optional[str] = "Apply"
    issue_reason: Optional[str] = None
    syllabus_context: Optional[str] = None
    marks: Optional[float] = 10.0

class AIRewriteResponse(BaseModel):
    original_question: str
    rewritten_question: str
    target_blooms_level: str
    command_verb: str
    mapped_unit: Optional[int] = None
    pedagogical_rationale: str
    is_ai_generated: bool = True

class CandidateQuestion(BaseModel):
    question_text: str
    command_verb: str
    blooms_level: str
    marks: float
    sample_solution_outline: Optional[str] = None

class AIGenerateQuestionRequest(BaseModel):
    course_name: str
    course_code: str
    unit_number: int
    unit_title: str
    unit_topics: List[str]
    target_blooms_level: Optional[str] = "Apply"
    marks: float = 10.0
    difficulty: Optional[str] = "Medium"

class AIGenerateQuestionResponse(BaseModel):
    unit_number: int
    unit_title: str
    candidates: List[CandidateQuestion]
    is_ai_generated: bool = True

class AIModerationSummaryRequest(BaseModel):
    report: AuditReport

class AIModerationSummaryResponse(BaseModel):
    accreditation_summary: str
    key_strengths: List[str]
    urgent_action_items: List[str]
    nba_abet_readiness: str  # e.g., "Accreditation Ready", "Conditional Approval", "Requires Restructuring"
    is_ai_generated: bool = True
