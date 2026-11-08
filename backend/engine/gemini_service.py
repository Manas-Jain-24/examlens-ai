import json
import re
from httpx import TimeoutException
from typing import Optional, List
from google import genai
from google.genai import types

from backend.core.config import settings
from backend.core.logger import logger
from backend.models import (
    AIRewriteRequest, AIRewriteResponse,
    AIGenerateQuestionRequest, AIGenerateQuestionResponse, CandidateQuestion,
    AuditReport, AIModerationSummaryResponse
)

class GeminiService:
    def __init__(self, api_key: Optional[str] = None, model_name: Optional[str] = None):
        self.api_key = settings.GEMINI_API_KEY if api_key is None else api_key
        self.client = None
        self.model_name = settings.GEMINI_MODEL if model_name is None else model_name
        self.configuration_reason = 'no_api_key' if not self.api_key.strip() else 'model_not_configured'

        if self.api_key.strip() and self.model_name.strip():
            try:
                self.client = genai.Client(api_key=self.api_key.strip(), http_options=types.HttpOptions(
                    timeout=int(settings.AI_TIMEOUT_SECONDS * 1000),
                    retry_options=types.HttpRetryOptions(attempts=1)))
                self.configuration_reason = None
                logger.info("GeminiService initialized with Google Gemini API Client.")
            except Exception as e:
                self.configuration_reason = 'client_initialization_failed'
                logger.warning('Could not initialize Gemini client; using templates (%s).', type(e).__name__)
        else:
            logger.info('Gemini not configured (%s). Using deterministic templates.', self.configuration_reason)

    def is_live_ai_available(self) -> bool:
        return self.client is not None

    def _request_json(self, prompt, temperature, required_fields):
        response = self.client.models.generate_content(model=self.model_name, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type='application/json', temperature=temperature))
        data = json.loads(response.text or '')
        if not isinstance(data, dict) or not data:
            raise ValueError('Provider must return a nonempty JSON object.')
        if any(key not in data for key in required_fields):
            raise ValueError('Provider response is missing required fields.')
        return data

    def _fallback(self, result, reason):
        result.engine = 'heuristic'
        result.model_name = None
        result.fallback_reason = reason
        return result

    def _failure_reason(self, error):
        return 'provider_timeout' if isinstance(error, (TimeoutError, TimeoutException)) else 'provider_error_or_invalid_response'

    def rewrite_question(self, req: AIRewriteRequest) -> AIRewriteResponse:
        """
        Rewrites a problematic exam question to elevate its Bloom's cognitive level,
        resolve out-of-syllabus flaws, or prevent PYQ memorization.
        """
        reason = self.configuration_reason or 'provider_unavailable'
        if self.client:
            try:
                prompt = f"""
You are an expert examination moderation committee member and academic quality auditor.
Rewrite the following examination question to improve its academic rigor and align with the desired cognitive standard.

[ORIGINAL QUESTION]
"{req.question_text}"

[CURRENT COGNITIVE LEVEL]
{req.current_blooms_level or "Understand"}

[TARGET BLOOMS TAXONOMY LEVEL]
{req.target_blooms_level or "Apply"}

[REASON FOR MODERATION / ISSUE]
{req.issue_reason or "Enhance problem-solving rigor and prevent rote memorization."}

[SYLLABUS CONTEXT]
{req.syllabus_context or "Standard undergraduate computer science curriculum"}

[MARKS ALLOCATED]
{req.marks or 10.0} Marks

Requirements:
1. Elevate the question to explicitly target the "{req.target_blooms_level}" cognitive level using an appropriate action verb (e.g. Implement, Analyze, Evaluate, Design, Compare, Solve).
2. Ground the question in a realistic engineering or computational scenario where applicable.
3. Keep the scope strictly within the course syllabus context.
4. Output strictly a JSON object matching this schema:
{{
  "rewritten_question": "string with complete question text and mark distribution",
  "command_verb": "single leading action verb",
  "target_blooms_level": "{req.target_blooms_level}",
  "pedagogical_rationale": "2-3 sentences explaining why this rewrite improves assessment quality"
}}
"""
                data = self._request_json(prompt, 0.4, ['rewritten_question', 'command_verb', 'pedagogical_rationale'])
                if data:
                    return AIRewriteResponse(
                        original_question=req.question_text,
                        rewritten_question=data.get("rewritten_question", req.question_text),
                        target_blooms_level=req.target_blooms_level or 'Apply',
                        command_verb=data.get("command_verb", "Apply"),
                        pedagogical_rationale=data.get(
                            "pedagogical_rationale",
                            "Revised to promote higher-order cognitive evaluation over rote memorization."
                        ),
                        is_ai_generated=True, engine='gemini', model_name=self.model_name
                    )
            except Exception as e:
                reason = self._failure_reason(e)
                logger.warning('Gemini rewrite unavailable (%s); using templates.', type(e).__name__)

        # --- Deterministic Heuristic Fallback ---
        return self._fallback(self._heuristic_rewrite(req), reason)

    def generate_unit_questions(self, req: AIGenerateQuestionRequest) -> AIGenerateQuestionResponse:
        """
        Generates candidate examination questions for an unassessed or underrepresented unit.
        """
        reason = self.configuration_reason or 'provider_unavailable'
        if self.client:
            try:
                topics_str = ", ".join(req.unit_topics)
                prompt = f"""
You are an expert university professor setting a final examination paper.
Generate 2 distinct candidate examination questions for Unit {req.unit_number}: "{req.unit_title}" in {req.course_code}: {req.course_name}.

[UNIT TOPICS]
{topics_str}

[TARGET BLOOM'S TAXONOMY LEVEL]
{req.target_blooms_level or "Apply"}

[MARKS PER QUESTION]
{req.marks} Marks

[DIFFICULTY]
{req.difficulty or "Medium"}

Requirements:
- Ensure each question tests higher-order analytical or applied thinking rather than simple definitions.
- Provide a concise 2-sentence solution outline for scoring rubrics.
- Output strictly a JSON object matching this schema:
{{
  "candidates": [
    {{
      "question_text": "string with full question statement",
      "command_verb": "string verb",
      "blooms_level": "{req.target_blooms_level}",
      "marks": {req.marks},
      "sample_solution_outline": "scoring criteria and solution breakdown"
    }}
  ]
}}
"""
                data = self._request_json(prompt, 0.5, ['candidates'])
                if data:
                    candidates = [CandidateQuestion(**c) for c in data.get("candidates", [])]
                    if not candidates or any(c.blooms_level != req.target_blooms_level or abs(c.marks - req.marks) > 0.001 for c in candidates):
                        raise ValueError('Generated candidates must match requested marks and cognitive level.')
                    if candidates:
                        return AIGenerateQuestionResponse(
                            unit_number=req.unit_number,
                            unit_title=req.unit_title,
                            candidates=candidates,
                            is_ai_generated=True, engine='gemini', model_name=self.model_name
                        )
            except Exception as e:
                reason = self._failure_reason(e)
                logger.warning('Gemini generation unavailable (%s); using templates.', type(e).__name__)

        # --- Deterministic Heuristic Fallback ---
        return self._fallback(self._heuristic_generate_questions(req), reason)

    def generate_moderation_summary(self, report: AuditReport) -> AIModerationSummaryResponse:
        """
        Synthesizes an executive examination moderation note and accreditation compliance assessment.
        """
        reason = self.configuration_reason or 'provider_unavailable'
        if self.client:
            try:
                summary_data = {
                    "course": report.syllabus_summary,
                    "overall_score": report.overall_quality_score,
                    "grade": report.grade,
                    "score_breakdown": report.score_breakdown.model_dump(),
                    "findings_count": len(report.findings),
                    "high_severity_findings": [f.title for f in report.findings if f.severity == "High"]
                }

                prompt = f"""
You are assisting a faculty moderation board. Write an advisory review of the draft examination.
Do not certify accreditation compliance or invent standards. This automated report is a review aid.
Synthesize a moderation review note based on this audit telemetry:

{json.dumps(summary_data, indent=2)}

Output strictly a JSON object matching this schema:
{{
  "accreditation_summary": "3-4 paragraphs formal institutional assessment covering syllabus coverage, cognitive depth, and risk points",
  "key_strengths": ["list of 2-3 prominent strengths in this draft"],
  "urgent_action_items": ["list of 2-3 critical moderation actions required before paper approval"],
  "nba_abet_readiness": "Faculty Review Suggested | Revisions Suggested | Revision Required"
}}
"""
                data = self._request_json(prompt, 0.3, ['accreditation_summary', 'key_strengths', 'urgent_action_items', 'nba_abet_readiness'])
                if data:
                    return AIModerationSummaryResponse(
                        accreditation_summary=data.get("accreditation_summary", report.verdict_summary),
                        key_strengths=data.get("key_strengths", ["Syllabus units mapped"]),
                        urgent_action_items=data.get("urgent_action_items", ["Review flagged findings"]),
                        nba_abet_readiness=data.get("nba_abet_readiness", "Conditional Approval"),
                        is_ai_generated=True, engine='gemini', model_name=self.model_name
                    )
            except Exception as e:
                reason = self._failure_reason(e)
                logger.warning('Gemini summary unavailable (%s); using templates.', type(e).__name__)

        # --- Deterministic Heuristic Fallback ---
        return self._fallback(self._heuristic_moderation_summary(report), reason)

    # ------------------------------------------------------------------
    # Deterministic Heuristic Fallback Methods
    # ------------------------------------------------------------------

    def _template(self, concept, level):
        return {
            'Remember': ('State', f'State the key properties of {concept} and define the main terms.'),
            'Understand': ('Explain', f'Explain {concept} with an example and identify its limitations.'),
            'Apply': ('Apply', f'Apply {concept} to a concrete example. State assumptions and show each step of your solution.'),
            'Analyze': ('Analyze', f'Analyze {concept} by comparing two approaches or cases. Explain the causes of their differences.'),
            'Evaluate': ('Evaluate', f'Evaluate the suitability of {concept} for a scenario of your choice. Justify your criteria and conclusion.'),
            'Create': ('Design', f'Design a solution or model using {concept}. State constraints and explain how you would validate it.'),
        }[level]

    def _heuristic_rewrite(self, req: AIRewriteRequest) -> AIRewriteResponse:
        concept = re.sub(r'^(?:what\s+is|what\s+are|define|explain|discuss|describe)\s+', '', req.question_text.strip(), flags=re.I)
        concept = re.sub(r'[([]\s*\d+(?:\.\d+)?\s*marks?\s*[)\]]', '', concept, flags=re.I).strip(' ?.')
        verb, statement = self._template(concept, req.target_blooms_level)
        return AIRewriteResponse(original_question=req.question_text,
            rewritten_question=f'{statement} ({req.marks:g} Marks)',
            target_blooms_level=req.target_blooms_level, command_verb=verb,
            pedagogical_rationale='Template suggestion for the requested cognitive level. Faculty must verify relevance, difficulty, and syllabus alignment.',
            is_ai_generated=False)

    def _heuristic_generate_questions(self, req: AIGenerateQuestionRequest) -> AIGenerateQuestionResponse:
        topics = req.unit_topics or [req.unit_title]
        candidates = []
        for topic in (topics[0], topics[1] if len(topics) > 1 else topics[0]):
            verb, statement = self._template(topic, req.target_blooms_level)
            candidates.append(CandidateQuestion(question_text=f'{statement} ({req.marks:g} Marks)',
                command_verb=verb, blooms_level=req.target_blooms_level, marks=req.marks,
                sample_solution_outline=f'Conceptual correctness and reasoning ({req.marks * 0.6:g}M); supporting example and justification ({req.marks * 0.4:g}M). Faculty review required.'))
        return AIGenerateQuestionResponse(unit_number=req.unit_number, unit_title=req.unit_title,
            candidates=candidates, is_ai_generated=False)

    def _heuristic_moderation_summary(self, report: AuditReport) -> AIModerationSummaryResponse:
        score = report.overall_quality_score
        strengths = []
        actions = []

        if report.score_breakdown.syllabus_coverage_score >= 80:
            strengths.append(f"Strong syllabus coverage across core units ({report.score_breakdown.syllabus_coverage_score}%).")
        else:
            actions.append("Add questions addressing unassessed or underrepresented syllabus units.")

        if report.score_breakdown.blooms_cognitive_score >= 75:
            strengths.append("Balanced cognitive distribution between foundational understanding and higher-order reasoning.")
        else:
            actions.append("Rebalance cognitive levels to reduce recall-heavy items and introduce applied problem-solving.")

        if report.score_breakdown.repetition_risk_score >= 80:
            strengths.append("Low repetition risk against previous-year examination archives.")
        else:
            actions.append("Paraphrase or replace questions flagged with high previous-year similarity (>70%).")

        if not strengths:
            strengths.append("Established modular course outcomes and declared weightage frameworks.")
        if not actions:
            actions.append("Verify finalized mark allocations with respective course coordinators.")

        readiness = 'Faculty Review Suggested' if score >= 85 else ('Revisions Suggested' if score >= 70 else 'Revision Required')

        summary_text = (
            f"The draft examination paper for {report.syllabus_summary.get('course_name', 'Course')} "
            f"({report.syllabus_summary.get('course_code', '')}) achieved an automated Examination Quality Score of "
            f"{score}/100, ranking it as '{report.grade}'. "
            f"The assessment exhibits {len(report.findings)} moderation advisory findings. "
            f"This is a template-based moderation note, not an accreditation determination. "
            f"Moderation committee members should prioritize resolving all High-severity findings before formal publication."
        )

        return AIModerationSummaryResponse(
            accreditation_summary=summary_text,
            key_strengths=strengths,
            urgent_action_items=actions,
            nba_abet_readiness=readiness,
            is_ai_generated=False
        )

# Global singleton service instance
gemini_service = GeminiService()
