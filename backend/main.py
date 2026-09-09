"""
IntelliWMS API Gateway - Coordinator Agent Entrypoint.
Orchestrates:
- Task 1: Security & JWT Validation
- Task 2: Intent Classification & Routing
- Task 3: API Gateway & MCP Delegation
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from utils.logger import StructuredLogger
from backend.routes.query import router as query_router
from backend.middleware.error_handler import register_error_handlers

app = FastAPI(
    title="IntelliWMS API Gateway",
    description="Intelligent Agentic Warehouse Management System - Coordinator Agent",
    version="0.3.0"
)

logger = StructuredLogger(__name__)

# Register Global Exception & Error Handlers
register_error_handlers(app)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Routes
app.include_router(query_router)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "IntelliWMS API Gateway is running smoothly",
        "primary_llm": settings.LLM_PRIMARY
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
