import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.core.config import settings
from backend.core.logger import logger
from backend.core.exceptions import register_exception_handlers
from backend.api.routers import health, demo, audit, reports, ai_suggest, drafts, history, evaluation, backups

def create_app() -> FastAPI:
    """Application factory for ExamLens AI backend."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="Enterprise Examination Quality & Syllabus-Alignment Auditor API",
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc"
    )

    # 1. CORS Middleware configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials="*" not in settings.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Register unified application error handlers
    register_exception_handlers(app)

    # 3. Mount modular API routers under /api
    app.include_router(health.router, prefix=settings.API_PREFIX)
    app.include_router(demo.router, prefix=settings.API_PREFIX)
    app.include_router(audit.router, prefix=settings.API_PREFIX)
    app.include_router(reports.router, prefix=settings.API_PREFIX)
    app.include_router(ai_suggest.router, prefix=settings.API_PREFIX)
    app.include_router(drafts.router, prefix=settings.API_PREFIX)
    app.include_router(history.router, prefix=settings.API_PREFIX)
    app.include_router(evaluation.router, prefix=settings.API_PREFIX)
    app.include_router(backups.router, prefix=settings.API_PREFIX)


    # 4. Mount frontend static assets
    if os.path.exists(settings.FRONTEND_DIR):
        app.mount("/static", StaticFiles(directory=settings.FRONTEND_DIR), name="static")

    # 5. Serve frontend single-page dashboard at root
    @app.get("/", include_in_schema=False)
    def serve_frontend():
        index_file = os.path.join(settings.FRONTEND_DIR, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return JSONResponse(
            content={"message": f"{settings.PROJECT_NAME} backend is active. Frontend files not found."},
            status_code=200
        )

    logger.info(f"{settings.PROJECT_NAME} v{settings.VERSION} initialized (Debug: {settings.DEBUG})")
    return app

app = create_app()
