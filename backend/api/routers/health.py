from fastapi import APIRouter
from backend.core.config import settings
from backend.models import HealthResponse

router = APIRouter(tags=["Health"])

@router.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for container probes and uptime monitoring."""
    return HealthResponse(
        status="ok",
        app=settings.PROJECT_NAME,
        version=settings.VERSION,
        environment="development" if settings.DEBUG else "production",
        debug=settings.DEBUG
    )
