import os
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, model_validator, ConfigDict

BLOOM_LEVELS = ['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']

class AuditRules(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    component_weights: Dict[str, float] = Field(default_factory=lambda: {
        'coverage': 25, 'outcomes': 20, 'marks': 20, 'blooms': 15, 'syllabus': 10, 'repetition': 10
    })
    unit_weights: Dict[int, float] = Field(default_factory=dict)
    blooms_targets: Dict[str, float] = Field(default_factory=lambda: {
        'Remember': 15, 'Understand': 25, 'Apply': 25, 'Analyze': 20, 'Evaluate': 10, 'Create': 5
    })
    repeat_medium: float = Field(default=0.70, ge=0, le=1)
    repeat_high: float = Field(default=0.85, ge=0, le=1)

    @model_validator(mode='after')
    def valid_rules(self):
        expected = {'coverage', 'outcomes', 'marks', 'blooms', 'syllabus', 'repetition'}
        if set(self.component_weights) != expected or set(self.blooms_targets) != set(BLOOM_LEVELS):
            raise ValueError('Provide all six score components and all six Bloom levels.')
        for values in [self.component_weights, self.blooms_targets, self.unit_weights]:
            if values and (any(v < 0 for v in values.values()) or abs(sum(values.values()) - 100) > 0.01):
                raise ValueError('Each weight distribution must be nonnegative and total 100%.')
        if self.repeat_medium >= self.repeat_high:
            raise ValueError('Medium repetition threshold must be below the high threshold.')
        return self

class ChoiceGroup(BaseModel):
    group_id: str = Field(min_length=1)
    question_ids: List[str] = Field(min_length=2)
    choose: int = Field(ge=1)

    @model_validator(mode='after')
    def valid_choice(self):
        if len(set(self.question_ids)) != len(self.question_ids) or self.choose >= len(self.question_ids):
            raise ValueError('A choice group needs distinct question IDs and choose < group size.')
        return self

class SyllabusUnit(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)
    unit_number: int = Field(ge=1)
    title: str = Field(min_length=1)
    topics: List[str] = Field(min_length=1)
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
    model_config = ConfigDict(str_strip_whitespace=True, allow_inf_nan=False)
    question_id: str = Field(min_length=1)
    section: str = "Part A"
    question_text: str = Field(min_length=1)
    marks: float = Field(gt=0, allow_inf_nan=False)
    mapping_evidence: Dict[str, Any] = Field(default_factory=dict)
    review_status: Literal['pending', 'accepted', 'corrected', 'rejected'] = 'pending'
    review_note: str = ''
    question_type: Optional[str] = "Descriptive"
    command_verb: Optional[str] = None
    mapped_unit: Optional[int] = None
    unit_allocations: Dict[int, float] = Field(default_factory=dict)
    mapped_outcomes: List[str] = Field(default_factory=list)
    blooms_level: Optional[Literal['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']] = None
    mapping_confidence: float = 0.0
    is_out_of_syllabus: bool = False
    out_of_syllabus_reason: Optional[str] = None
    pyq_similarity: Optional[float] = None
    pyq_matched_question: Optional[str] = None

    @model_validator(mode='after')
    def valid_allocations(self):
        if self.unit_allocations and (
            any(unit < 1 or marks <= 0 for unit, marks in self.unit_allocations.items())
            or abs(sum(self.unit_allocations.values()) - self.marks) > 0.001
        ):
            raise ValueError('Unit allocations must be positive and sum to the question marks.')
        return self

class QuestionPaper(BaseModel):
    paper_title: str
    course_code: str
    total_marks: float
    duration_minutes: Optional[int] = 180
    questions: List[QuestionItem]
    choice_groups: List[ChoiceGroup] = Field(default_factory=list)
    parsing_warnings: List[str] = Field(default_factory=list)

    @model_validator(mode='after')
    def valid_groups(self):
        ids = [q.question_id for q in self.questions]
        if len(ids) != len(set(ids)):
            raise ValueError('Question IDs must be unique.')
        seen, group_ids = set(), set()
        for group in self.choice_groups:
            members = set(group.question_ids)
            if not members <= set(ids) or seen & members or group.group_id in group_ids:
                raise ValueError('Choice groups must reference existing questions and must not overlap.')
            seen |= members
            group_ids.add(group.group_id)
        return self

class ReviewedDraft(BaseModel):
    extraction_details: Dict[str, Any] = Field(default_factory=dict)
    syllabus: Syllabus
    paper: QuestionPaper
    pyqs: List['PreviousYearQuestion'] = Field(default_factory=list)
    rules: AuditRules = Field(default_factory=AuditRules)
    warnings: List[str] = Field(default_factory=list)
    source_texts: Dict[str, str] = Field(default_factory=dict)

    @model_validator(mode='after')
    def valid_draft(self):
        numbers = [u.unit_number for u in self.syllabus.units]
        if not numbers or len(numbers) != len(set(numbers)):
            raise ValueError('Provide at least one syllabus unit and use distinct unit numbers.')
        if self.rules.unit_weights and set(self.rules.unit_weights) != set(numbers):
            raise ValueError('Unit weights must include exactly the syllabus unit numbers.')
        for question in self.paper.questions:
            if not set(question.unit_allocations) <= set(numbers):
                raise ValueError(f'{question.question_id}: allocated units must exist in the syllabus.')
        return self

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
    guaranteed_marks: float = 0
    possible_marks: float = 0
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
    extraction_details: Dict[str, Any] = Field(default_factory=dict)
    document_warnings: List[str] = Field(default_factory=list)
    rules: AuditRules = Field(default_factory=AuditRules)
    choice_groups: List[ChoiceGroup] = Field(default_factory=list)
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
    extraction_details: Dict[str, Any] = Field(default_factory=dict)
    document_warnings: List[str] = Field(default_factory=list)
    rules: AuditRules = Field(default_factory=AuditRules)
    choice_groups: List[ChoiceGroup] = Field(default_factory=list)
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
    target_blooms_level: Literal['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'] = 'Apply'
    issue_reason: Optional[str] = None
    syllabus_context: Optional[str] = None
    marks: float = Field(default=10, gt=0, allow_inf_nan=False)

class EngineMetadata(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    engine: str = 'heuristic'
    model_name: Optional[str] = None
    fallback_reason: Optional[str] = None

class AIRewriteResponse(EngineMetadata):
    original_question: str
    rewritten_question: str = Field(min_length=1)
    target_blooms_level: str
    command_verb: str
    mapped_unit: Optional[int] = None
    pedagogical_rationale: str
    is_ai_generated: bool = True

class CandidateQuestion(BaseModel):
    question_text: str = Field(min_length=1)
    command_verb: str
    blooms_level: Literal['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create']
    marks: float = Field(gt=0, allow_inf_nan=False)
    sample_solution_outline: Optional[str] = None

class AIGenerateQuestionRequest(BaseModel):
    course_name: str
    course_code: str
    unit_number: int
    unit_title: str
    unit_topics: List[str]
    target_blooms_level: Literal['Remember', 'Understand', 'Apply', 'Analyze', 'Evaluate', 'Create'] = 'Apply'
    marks: float = Field(default=10, gt=0, allow_inf_nan=False)
    difficulty: Optional[str] = "Medium"

class AIGenerateQuestionResponse(EngineMetadata):
    unit_number: int
    unit_title: str
    candidates: List[CandidateQuestion]
    is_ai_generated: bool = True

class AIModerationSummaryRequest(BaseModel):
    report: AuditReport

class AIModerationSummaryResponse(EngineMetadata):
    accreditation_summary: str
    key_strengths: List[str]
    urgent_action_items: List[str]
    nba_abet_readiness: str  # e.g., "Accreditation Ready", "Conditional Approval", "Requires Restructuring"
    is_ai_generated: bool = True

ReviewedDraft.model_rebuild()
