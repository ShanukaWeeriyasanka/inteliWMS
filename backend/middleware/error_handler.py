"""
Global error handling middleware for IntelliWMS API Gateway.
Standardizes error responses across all endpoints.
"""
from datetime import datetime, timezone
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from utils import request_context
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

class AppError(HTTPException):
    """HTTP error with a specific machine-readable error_code (e.g. THREAD_NOT_FOUND)."""
    def __init__(self, status_code: int, error_code: str, detail: str):
        super().__init__(status_code=status_code, detail=detail)
        self.error_code = error_code


def _audit(request: Request) -> dict:
    """Timestamp, path and the request's correlation ids (request_id / trace_id)."""
    state = request.scope.get("state") or {}
    ids = request_context.current()
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "path": request.url.path,
        "request_id": ids.get("request_id") or state.get("request_id"),
        "trace_id": ids.get("trace_id") or state.get("trace_id"),
    }


def _plain_errors(errors) -> list:
    """Validation errors as plain JSON: a model validator's ValueError sits in `ctx` and can't be serialised."""
    plain = []
    for err in errors:
        item = {k: err.get(k) for k in ("type", "loc", "msg") if k in err}
        if "loc" in item:
            item["loc"] = [part if isinstance(part, (str, int)) else str(part) for part in item["loc"]]
        if err.get("ctx"):
            item["ctx"] = {k: v if isinstance(v, (str, int, float, bool)) or v is None else str(v)
                           for k, v in err["ctx"].items()}
        plain.append(item)
    return plain


def register_error_handlers(app):
    """Registers exception handlers on the FastAPI app instance."""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.log_event("HTTP_EXCEPTION", {
            "path": request.url.path,
            "status_code": exc.status_code,
            "error_code": getattr(exc, "error_code", None),
            "detail": exc.detail
        })

        error_code = getattr(exc, "error_code", None) or "HTTP_ERROR"
        if not getattr(exc, "error_code", None):
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
                "audit": _audit(request)
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
                "details": _plain_errors(exc.errors()),
                "audit": _audit(request)
            }
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.log_event("UNHANDLED_EXCEPTION", {
            "path": request.url.path,
            "error_type": type(exc).__name__,
            "error": str(exc)
        }, level="ERROR")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred in the Coordinator API Gateway",
                "audit": _audit(request)
            }
        )
