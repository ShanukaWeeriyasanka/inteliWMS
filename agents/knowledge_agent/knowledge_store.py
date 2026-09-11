"""
Vector Knowledge Store for IntelliWMS Knowledge Agent.
Manages document chunking, indexing, and vector similarity retrieval with ChromaDB
and provides an in-memory keyword overlap fallback.
"""
from typing import Dict, Any, List, Optional
import os
import json
from pathlib import Path
from agents.knowledge_agent.config import knowledge_config
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


class KnowledgeStore:
    """Manages document chunking, indexing, and vector similarity retrieval."""

    def __init__(self, persist_dir: Optional[Path] = None, collection_name: Optional[str] = None):
        self.persist_dir = persist_dir or knowledge_config.CHROMA_PERSIST_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name or knowledge_config.COLLECTION_NAME
        self._client = None
        self._collection = None
        self._fallback_docs: List[Dict[str, Any]] = []
        self._init_store()

    def _init_store(self):
        """Initializes ChromaDB client with graceful in-memory fallback."""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "IntelliWMS Warehouse SOPs and Guidelines"}
            )
            logger.log_event("CHROMADB_INITIALIZED", {"path": str(self.persist_dir)})
        except Exception as e:
            logger.log_event("CHROMADB_FALLBACK_ACTIVE", {"reason": str(e)})
            self._client = None
            self._collection = None

    def add_document(self, doc_id: str, title: str, content: str, category: str = "SOP", metadata: Optional[Dict[str, Any]] = None):
        """
        Chunks and indexes a warehouse document into the vector store.
        
        Args:
            doc_id: Unique document identifier (e.g., 'SOP-SAF-001')
            title: Human-readable document title
            content: Full text of document or guidelines
            category: Category tag (e.g., 'Safety', 'Storage', 'Receiving')
            metadata: Additional custom metadata
        """
        if not content or not content.strip():
            return

        min_len = knowledge_config.MIN_PARAGRAPH_LENGTH
        raw_paragraphs = [p.strip() for p in content.split("\n\n") if len(p.strip()) > min_len]
        chunks = raw_paragraphs if raw_paragraphs else [content.strip()]

        ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [
            {
                "doc_id": doc_id,
                "title": title,
                "category": category,
                "chunk_index": i,
                **(metadata or {})
            }
            for i in range(len(chunks))
        ]

        if self._collection is not None:
            self._collection.upsert(
                ids=ids,
                documents=chunks,
                metadatas=metadatas
            )
        else:
            # In-memory fallback: update or append
            self._fallback_docs = [d for d in self._fallback_docs if d.get("doc_id") != doc_id]
            for i, text in enumerate(chunks):
                self._fallback_docs.append({
                    "id": ids[i],
                    "text": text,
                    "title": title,
                    "category": category,
                    "doc_id": doc_id
                })

        logger.log_event("KNOWLEDGE_DOC_INDEXED", {"doc_id": doc_id, "chunks_count": len(chunks)})

    def query(self, query_text: str, n_results: Optional[int] = None, category: Optional[str] = None) -> List[Dict[str, Any]]:
        if not query_text or not query_text.strip():
            return []

        limit = n_results or knowledge_config.DEFAULT_RAG_TOP_K
        clean_query = query_text.strip()

        # Build ChromaDB where clause if category is supplied
        where_filter = {"category": category} if category else None

        if self._collection is not None and self._collection.count() > 0:
            try:
                query_kwargs = {
                    "query_texts": [clean_query],
                    "n_results": min(limit, self._collection.count())
                }
                if where_filter:
                    query_kwargs["where"] = where_filter

                results = self._collection.query(**query_kwargs)
                output = []
                if results and "documents" in results and results["documents"]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                    distances = results["distances"][0] if "distances" in results and results["distances"] else [0.0] * len(docs)

                    for i in range(len(docs)):
                        output.append({
                            "title": metas[i].get("title", "Warehouse Document"),
                            "category": metas[i].get("category", "General"),
                            "doc_id": metas[i].get("doc_id", "UNKNOWN"),
                            "content": docs[i],
                            "distance": distances[i] if i < len(distances) else None
                        })
                if output:
                    return output
            except Exception as e:
                logger.log_event("CHROMA_QUERY_ERROR", {"error": str(e)})

        # Fallback keyword overlap ranking with category filtering
        query_words = set(clean_query.lower().split())
        candidate_docs = self._fallback_docs
        if category:
            candidate_docs = [d for d in self._fallback_docs if d.get("category", "").lower() == category.lower()]

        scored_docs = []
        for d in candidate_docs:
            doc_words = set(d["text"].lower().split()) | set(d["title"].lower().split())
            overlap = len(query_words.intersection(doc_words))
            if overlap > 0:
                scored_docs.append((overlap, d))

        scored_docs.sort(key=lambda x: x[0], reverse=True)
        return [
            {
                "title": item["title"],
                "category": item["category"],
                "doc_id": item["doc_id"],
                "content": item["text"],
                "distance": None
            }
            for _, item in scored_docs[:limit]
        ]


    def count(self) -> int:
        """Returns total number of indexed chunks."""
        if self._collection is not None:
            return self._collection.count()
        return len(self._fallback_docs)


# Singleton instance
knowledge_store = KnowledgeStore()


def seed_warehouse_sops(store: Optional[KnowledgeStore] = None, fixture_path: Optional[Path] = None):
    """
    Seeds warehouse Standard Operating Procedures (SOPs) into the store from an external JSON fixture.
    Idempotent upsert allows new documents in sops.json to be indexed automatically.
    """
    target_store = store or knowledge_store

    path = fixture_path or knowledge_config.SEED_SOPS_PATH
    if not path.exists():
        logger.log_event("SOP_SEED_MISSING", {"path": str(path)})
        return

    try:
        with open(path, "r", encoding="utf-8") as f:
            sops = json.load(f)

        for sop in sops:
            target_store.add_document(
                doc_id=sop["doc_id"],
                title=sop["title"],
                content=sop["content"],
                category=sop.get("category", "SOP")
            )
        logger.log_event("SOP_SEED_COMPLETED", {"documents_count": len(sops)})
    except Exception as e:
        logger.log_event("SOP_SEED_ERROR", {"path": str(path), "error": str(e)})

