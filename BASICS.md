Why each folder exists:

agents/ → Where each AI agent lives (coordinator routes, specialists solve)
backend/ → FastAPI REST API server (your HTTP interface)
config/ → All settings in ONE place (LLM keys, prompts, database URL)
security/ → JWT auth, RBAC permissions, prompt injection detection
database/ → SQLAlchemy models (your database tables as Python classes)
ir/ → ChromaDB vector store for RAG (document search)
nlp/ → spaCy NER (extracts SKU numbers, quantities from text)
mcp_servers/ → How agents talk to each other (Model Context Protocol)
frontend/ → React chat UI


===================

All api keys are in .env
for now its in .env.example
