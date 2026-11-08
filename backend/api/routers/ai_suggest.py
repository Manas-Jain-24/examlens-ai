from fastapi import APIRouter
from backend.core.config import settings
from backend.core.logger import logger
from backend.models import (
    AIRewriteRequest, AIRewriteResponse,
    AIGenerateQuestionRequest, AIGenerateQuestionResponse,
    AIModerationSummaryRequest, AIModerationSummaryResponse
)
from backend.engine.gemini_service import gemini_service

router = APIRouter(prefix="/ai", tags=["AI Remediation & Generation"])

@router.get("/status")
def get_ai_status():
    """Checks whether Google Gemini API is live or running in fallback mode."""
    live = gemini_service.is_live_ai_available()
    return {
        "live_ai_available": live,
        "model": gemini_service.model_name if live else "deterministic_heuristic_fallback",
        "has_api_key": bool(settings.GEMINI_API_KEY.strip())
    }

@router.post("/rewrite", response_model=AIRewriteResponse)
def rewrite_question(req: AIRewriteRequest):
    """
    Rewrites a flagged or suboptimal question to elevate cognitive level (Bloom's)
    and align strictly with course outcomes.
    """
    logger.info(f"AI rewrite requested for: '{req.question_text[:50]}...' (Target: {req.target_blooms_level})")
    result = gemini_service.rewrite_question(req)
    logger.info(f"AI rewrite completed (AI Generated: {result.is_ai_generated})")
    return result

@router.post("/generate-question", response_model=AIGenerateQuestionResponse)
def generate_unit_questions(req: AIGenerateQuestionRequest):
    """
    Generates balanced candidate examination questions for an unassessed or underrepresented syllabus unit.
    """
    logger.info(f"AI question generation requested for Unit {req.unit_number}: '{req.unit_title}'")
    result = gemini_service.generate_unit_questions(req)
    logger.info(f"Generated {len(result.candidates)} candidate questions (AI Generated: {result.is_ai_generated})")
    return result

@router.post("/moderation-summary", response_model=AIModerationSummaryResponse)
def generate_moderation_summary(req: AIModerationSummaryRequest):
    """
    Generates an executive accreditation audit commentary and moderation review note.
    """
    logger.info("AI moderation summary requested for audit report...")
    result = gemini_service.generate_moderation_summary(req.report)
    logger.info(f"AI moderation summary generated: Readiness = {result.nba_abet_readiness}")
    return result
