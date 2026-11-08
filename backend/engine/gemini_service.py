import json
import re
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
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.client = None
        self.model_name = "gemini-3.8-flash"

        if self.api_key and self.api_key.strip():
            try:
                self.client = genai.Client(api_key=self.api_key.strip())
                logger.info("GeminiService initialized with Google Gemini API Client.")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini Client: {e}. Falling back to heuristic engine.")
        else:
            logger.info("No GEMINI_API_KEY detected. Running in heuristic/deterministic fallback mode.")

    def is_live_ai_available(self) -> bool:
        return self.client is not None

    def rewrite_question(self, req: AIRewriteRequest) -> AIRewriteResponse:
        """
        Rewrites a problematic exam question to elevate its Bloom's cognitive level,
        resolve out-of-syllabus flaws, or prevent PYQ memorization.
        """
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
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.4
                    )
                )

                if response.text:
                    data = json.loads(response.text)
                    return AIRewriteResponse(
                        original_question=req.question_text,
                        rewritten_question=data.get("rewritten_question", req.question_text),
                        target_blooms_level=data.get("target_blooms_level", req.target_blooms_level or "Apply"),
                        command_verb=data.get("command_verb", "Apply"),
                        pedagogical_rationale=data.get(
                            "pedagogical_rationale",
                            "Revised to promote higher-order cognitive evaluation over rote memorization."
                        ),
                        is_ai_generated=True
                    )
            except Exception as e:
                logger.warning(f"Gemini live call failed in rewrite_question: {e}. Falling back to heuristic rewrite.")

        # --- Deterministic Heuristic Fallback ---
        return self._heuristic_rewrite(req)

    def generate_unit_questions(self, req: AIGenerateQuestionRequest) -> AIGenerateQuestionResponse:
        """
        Generates candidate examination questions for an unassessed or underrepresented unit.
        """
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
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.5
                    )
                )

                if response.text:
                    data = json.loads(response.text)
                    candidates = [CandidateQuestion(**c) for c in data.get("candidates", [])]
                    if candidates:
                        return AIGenerateQuestionResponse(
                            unit_number=req.unit_number,
                            unit_title=req.unit_title,
                            candidates=candidates,
                            is_ai_generated=True
                        )
            except Exception as e:
                logger.warning(f"Gemini live call failed in generate_unit_questions: {e}. Using heuristic generation.")

        # --- Deterministic Heuristic Fallback ---
        return self._heuristic_generate_questions(req)

    def generate_moderation_summary(self, report: AuditReport) -> AIModerationSummaryResponse:
        """
        Synthesizes an executive examination moderation note and accreditation compliance assessment.
        """
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
You are the Chairman of an Academic Examination Moderation Board reviewing a draft examination paper against NBA / ABET accreditation standards.
Synthesize an executive moderation review note based on this audit telemetry:

{json.dumps(summary_data, indent=2)}

Output strictly a JSON object matching this schema:
{{
  "accreditation_summary": "3-4 paragraphs formal institutional assessment covering syllabus coverage, cognitive depth, and risk points",
  "key_strengths": ["list of 2-3 prominent strengths in this draft"],
  "urgent_action_items": ["list of 2-3 critical moderation actions required before paper approval"],
  "nba_abet_readiness": "Accreditation Ready | Conditional Approval | Revision Required"
}}
"""
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.3
                    )
                )

                if response.text:
                    data = json.loads(response.text)
                    return AIModerationSummaryResponse(
                        accreditation_summary=data.get("accreditation_summary", report.verdict_summary),
                        key_strengths=data.get("key_strengths", ["Syllabus units mapped"]),
                        urgent_action_items=data.get("urgent_action_items", ["Review flagged findings"]),
                        nba_abet_readiness=data.get("nba_abet_readiness", "Conditional Approval"),
                        is_ai_generated=True
                    )
            except Exception as e:
                logger.warning(f"Gemini live call failed in generate_moderation_summary: {e}. Using heuristic summary.")

        # --- Deterministic Heuristic Fallback ---
        return self._heuristic_moderation_summary(report)

    # ------------------------------------------------------------------
    # Deterministic Heuristic Fallback Methods
    # ------------------------------------------------------------------

    def _heuristic_rewrite(self, req: AIRewriteRequest) -> AIRewriteResponse:
        text = req.question_text.strip()
        target_lvl = req.target_blooms_level or "Apply"

        # Extract concept by stripping leading verbs and punctuation
        concept = re.sub(r'^(?:what\s+is|what\s+are|define|explain|discuss|describe|write\s+short\s+notes\s+on)\s+', '', text, flags=re.I).strip(" ?.")

        if target_lvl == "Apply":
            rewritten = (
                f"Design and implement a solution utilizing {concept} to handle dynamically incoming data streams. "
                f"Provide pseudo-code and trace the operation step-by-step. ({int(req.marks or 10)} Marks)"
            )
            verb = "Implement"
            rationale = "Shifted question from passive definitions to algorithmic implementation and step-by-step trace."
        elif target_lvl == "Analyze":
            rewritten = (
                f"Conduct an in-depth asymptotic analysis of {concept}. Compare its time and space complexity trade-offs "
                f"against alternative linear or hierarchical structures under worst-case input conditions. ({int(req.marks or 10)} Marks)"
            )
            verb = "Analyze"
            rationale = "Elevated cognitive demand to comparative asymptotic evaluation and worst-case trade-off analysis."
        elif target_lvl == "Evaluate":
            rewritten = (
                f"Critique the suitability of {concept} in mission-critical applications with strict latency bounds. "
                f"Justify your architectural choice with empirical performance metrics. ({int(req.marks or 10)} Marks)"
            )
            verb = "Justify"
            rationale = "Requires students to defend design decisions and evaluate empirical constraints."
        else:
            rewritten = (
                f"Develop an architectural design incorporating {concept} tailored for high-concurrency systems. "
                f"Illustrate data flow and node transitions. ({int(req.marks or 10)} Marks)"
            )
            verb = "Design"
            rationale = "Constructive synthesis problem requiring novel architectural design."

        return AIRewriteResponse(
            original_question=req.question_text,
            rewritten_question=rewritten,
            target_blooms_level=target_lvl,
            command_verb=verb,
            pedagogical_rationale=rationale,
            is_ai_generated=False
        )

    def _heuristic_generate_questions(self, req: AIGenerateQuestionRequest) -> AIGenerateQuestionResponse:
        candidates = []
        topics = req.unit_topics or ["Core Principles", "Practical Implementation"]
        t1 = topics[0] if len(topics) > 0 else "fundamental algorithms"
        t2 = topics[1] if len(topics) > 1 else topics[0]

        candidates.append(CandidateQuestion(
            question_text=(
                f"Analyze the performance of {t1} when applied to large-scale datasets. "
                f"Derive its recurrence relation and prove its asymptotic time complexity bounds. ({int(req.marks)} Marks)"
            ),
            command_verb="Analyze",
            blooms_level="Analyze",
            marks=req.marks,
            sample_solution_outline=f"Recurrence formulation (4M), asymptotic induction proof (3M), boundary case discussion (3M)."
        ))

        candidates.append(CandidateQuestion(
            question_text=(
                f"Design an optimized algorithm implementing {t2} under constrained memory conditions. "
                f"Demonstrate how your approach avoids redundant operations with an annotated example. ({int(req.marks)} Marks)"
            ),
            command_verb="Design",
            blooms_level="Apply",
            marks=req.marks,
            sample_solution_outline=f"Algorithmic design (4M), memory footprint analysis (3M), annotated trace (3M)."
        ))

        return AIGenerateQuestionResponse(
            unit_number=req.unit_number,
            unit_title=req.unit_title,
            candidates=candidates,
            is_ai_generated=False
        )

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

        readiness = "Accreditation Ready" if score >= 85 else ("Conditional Approval" if score >= 70 else "Revision Required")

        summary_text = (
            f"The draft examination paper for {report.syllabus_summary.get('course_name', 'Course')} "
            f"({report.syllabus_summary.get('course_code', '')}) achieved an automated Examination Quality Score of "
            f"{score}/100, ranking it as '{report.grade}'. "
            f"The assessment exhibits {len(report.findings)} moderation advisory findings. "
            f"Following standard NBA and ABET outcome-based education (OBE) guidelines, {readiness.lower()} status is assigned. "
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
