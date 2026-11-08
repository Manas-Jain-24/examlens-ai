import os
from typing import List
from pydantic import BaseModel, Field

def load_dotenv(filepath: str = ".env"):
    """Lightweight .env loader without requiring external python-dotenv."""
    if not os.path.exists(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


def parse_cors_origins(value: str | None) -> List[str]:
    """Return a normalized, explicit list of browser origins.

    Keeping the default local-only prevents a deployed API from silently
    accepting credentialed requests from arbitrary websites.
    """
    if not value:
        return ["http://127.0.0.1:8000", "http://localhost:8000"]
    return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]

# Determine root directories
CORE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(CORE_DIR)
BASE_DIR = os.path.dirname(BACKEND_DIR)

# Load .env from project root
load_dotenv(os.path.join(BASE_DIR, ".env"))

class Settings(BaseModel):
    PROJECT_NAME: str = "ExamLens AI"
    VERSION: str = "1.0.0"
    API_PREFIX: str = "/api"
    HOST: str = os.getenv("HOST", "127.0.0.1")
    PORT: int = int(os.getenv("PORT", "8000"))
    DEBUG: bool = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    CORS_ORIGINS: List[str] = Field(
        default_factory=lambda: parse_cors_origins(os.getenv("CORS_ORIGINS"))
    )
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "15"))
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # Path mappings
    BASE_DIR: str = BASE_DIR
    FRONTEND_DIR: str = os.path.join(BASE_DIR, "frontend")
    DATA_DIR: str = os.path.join(BACKEND_DIR, "data")
    SAMPLE_DOCS_DIR: str = os.path.join(BASE_DIR, "sample_documents")

settings = Settings()
