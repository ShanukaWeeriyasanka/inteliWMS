from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from config.settings import settings
from utils.logger import StructuredLogger
from security.sanitizer import sanitize_input
from agents.coordinator.intent_classifier import intent_classifier

app = FastAPI(
    title="IntelliWMS API",
    description="Intelligent Agentic Warehouse Management System",
    version="0.1.0"
)

logger = StructuredLogger(__name__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "message": "IntelliWMS backend is running smoothly",
        "primary_llm": settings.LLM_PRIMARY
    }

@app.post("/query")
def query_endpoint(payload: dict):
    user_query = payload.get("query", "")

    # 1. Security & Prompt Injection Check
    is_safe, sanitized_or_reason = sanitize_input(user_query)
    if not is_safe:
        logger.log_event("SECURITY_BLOCKED", {"query": user_query, "reason": sanitized_or_reason})
        return {
            "status": "blocked",
            "message": sanitized_or_reason,
            "decision": None
        }

    # 2. Intent Classification via Gemini
    decision = intent_classifier.classify(sanitized_or_reason)

    return {
        "status": "success",
        "query": sanitized_or_reason,
        "routing": decision
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
