from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from backend.core.logger import logger

class ExamLensException(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR, details: dict = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}

class DocumentParsingError(ExamLensException):
    """Raised when syllabus or question paper text extraction fails."""
    def __init__(self, message: str, details: dict = None):
        status_code = getattr(status, "HTTP_422_UNPROCESSABLE_CONTENT", 422)
        super().__init__(message=message, status_code=status_code, details=details)


class AuditExecutionError(ExamLensException):
    """Raised when engine audit or calculation encounters an error."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, details=details)

class ResourceNotFoundError(ExamLensException):
    """Raised when a requested resource or file is not found."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, details=details)

class PayloadTooLargeError(ExamLensException):
    """Raised when an uploaded document exceeds size limits."""
    def __init__(self, message: str, details: dict = None):
        super().__init__(message=message, status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, details=details)

def register_exception_handlers(app: FastAPI):
    """Registers unified JSON exception handlers on the FastAPI application."""
    @app.exception_handler(ExamLensException)
    async def examlens_exception_handler(request: Request, exc: ExamLensException):
        logger.error(f"Application error on {request.method} {request.url.path}: {exc.message} | Details: {exc.details}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.__class__.__name__,
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception(f"Unhandled server error on {request.method} {request.url.path}: {str(exc)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "InternalServerError",
                "message": "An unexpected error occurred during processing. Please try again.",
                "details": {"error_type": exc.__class__.__name__, "info": str(exc)}
            }
        )
