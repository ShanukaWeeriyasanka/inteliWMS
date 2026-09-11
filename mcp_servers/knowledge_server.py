"""
MCP Gateway Entrypoint for Knowledge Agent.
Re-exports the microservice app from the self-contained agents.knowledge_agent package.
"""
import uvicorn
from agents.knowledge_agent.server import app
from agents.knowledge_agent.config import knowledge_config

if __name__ == "__main__":
    uvicorn.run(
        "mcp_servers.knowledge_server:app",
        host=knowledge_config.HOST,
        port=knowledge_config.PORT,
        reload=True
    )
