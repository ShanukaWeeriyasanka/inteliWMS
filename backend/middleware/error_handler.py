"""
Global error handling middleware for IntelliWMS API Gateway.
Standardizes error responses across all endpoints.
"""
from datetime import datetime, timezone
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

class UnauthorizedException(HTTPException):
    def __init__(self, detail: str = "Invalid or expired authentication token"):
        super().__init__(status_code=401, detail=detail)

class ForbiddenException(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions for requested action"):
        super().__init__(status_code=403, detail=detail)

class PromptInjectionException(HTTPException):
    def __init__(self, detail: str = "Query blocked by prompt injection security shield"):
        super().__init__(status_code=400, detail=detail)

def register_error_handlers(app):
    """Registers exception handlers on the FastAPI app instance."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.log_event("HTTP_EXCEPTION", {
            "path": request.url.path,
            "status_code": exc.status_code,
            "detail": exc.detail
        })

        error_code = "HTTP_ERROR"
        if exc.status_code == 401:
            error_code = "UNAUTHORIZED"
        elif exc.status_code == 403:
            error_code = "FORBIDDEN"
        elif exc.status_code == 400:
            error_code = "BAD_REQUEST"
        elif exc.status_code == 404:
            error_code = "NOT_FOUND"

        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error_code": error_code,
                "message": exc.detail,
                "audit": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path
                }
            }
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        logger.log_event("VALIDATION_ERROR", {
            "path": request.url.path,
            "errors": str(exc.errors())
        })
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid request payload format",
                "details": exc.errors(),
                "audit": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path
                }
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.log_event("UNHANDLED_EXCEPTION", {
            "path": request.url.path,
            "error": str(exc)
        })
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred in the Coordinator API Gateway",
                "audit": {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "path": request.url.path
                }
            }
        )
