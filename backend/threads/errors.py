"""Explicit, machine-readable thread errors (rendered by backend/middleware/error_handler.py)."""
from backend.middleware.error_handler import AppError


class InvalidThreadId(AppError):
    def __init__(self):
        super().__init__(400, "INVALID_THREAD_ID", "thread_id must be a UUID returned by this API")


class ThreadNotFound(AppError):
    """Missing thread, or a thread owned by someone else (not distinguished, to avoid leaking ids)."""
    def __init__(self):
        super().__init__(404, "THREAD_NOT_FOUND", "Conversation not found")


class ThreadAuthRequired(AppError):
    def __init__(self):
        super().__init__(401, "THREAD_AUTH_REQUIRED", "Sign in to use saved conversations")
