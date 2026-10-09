"""
Vector Knowledge Store for IntelliWMS Fulfillment Agent.

Manages SOP ingestion, chunking, metadata indexing, semantic similarity retrieval,
and fallback search using a dedicated ChromaDB collection ('fulfillment_sop_knowledge').
"""
from typing import Dict, Any, List, Optional
import json
import re
from pathlib import Path

from config.settings import settings
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)

# Constants
COLLECTION_NAME = "fulfillment_sop_knowledge"
DEFAULT_SIMILARITY_THRESHOLD = 0.35  # Threshold below which retrieved chunks are considered irrelevant
DEFAULT_TOP_K = 3


class FulfillmentKnowledgeStore:
    """
    Dedicated vector knowledge store for warehouse fulfillment procedures and SOPs.
    
    Provides isolated semantic search over fulfillment SOPs while keeping vector
    data isolated from general warehouse knowledge.
    """

    def __init__(
        self,
        persist_dir: Optional[Path] = None,
        collection_name: Optional[str] = None
    ):
        self.persist_dir = persist_dir or (settings.DATA_DIR / "chroma_db")
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name or COLLECTION_NAME
        self._client = None
        self._collection = None
        self._fallback_docs: List[Dict[str, Any]] = []
        self._init_store()

    def _init_store(self):
        """Initializes ChromaDB persistent client and dedicated collection with fallback support."""
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.persist_dir))
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "IntelliWMS Dedicated Fulfillment SOPs and Procedures"}
            )
            logger.log_event("FULFILLMENT_CHROMADB_INITIALIZED", {
                "collection": self.collection_name,
                "persist_dir": str(self.persist_dir)
            })
        except Exception as e:
            logger.log_event("FULFILLMENT_CHROMADB_INIT_FAILED", {"reason": str(e)})
            self._client = None
            self._collection = None

    def ingest_from_file(self, json_path: Optional[Path] = None) -> int:
        """
        Loads and indexes SOPs from the specified JSON file.
        Removes any stale chunks for updated or deleted documents.
        
        Returns total number of chunks indexed.
        """
        path = json_path or (Path(__file__).resolve().parent / "data" / "fulfillment_sops.json")
        if not path.exists():
            logger.log_event("FULFILLMENT_SOP_FILE_MISSING", {"path": str(path)})
            return 0

        with open(path, "r", encoding="utf-8") as f:
            documents = json.load(f)

        return self.sync_documents(documents)

    def sync_documents(self, documents: List[Dict[str, Any]]) -> int:
        """
        Syncs a list of SOP document dictionaries into the store.
        Handles addition, updates, and removes stale chunks for the synced documents.
        """
        total_chunks = 0
        current_doc_ids = set()

        for doc in documents:
            sop_id = doc.get("sop_id")
            if not sop_id:
                continue
            current_doc_ids.add(sop_id)
            total_chunks += self.add_sop_document(doc)

        logger.log_event("FULFILLMENT_SOPS_SYNCED", {
            "documents_count": len(current_doc_ids),
            "total_chunks": total_chunks
        })
        return total_chunks

    def add_sop_document(self, doc: Dict[str, Any]) -> int:
        """
        Chunks and indexes an individual SOP document.
        Removes previous chunks for this SOP before inserting new ones to prevent stale chunks.
        
        Returns the number of chunks added.
        """
        sop_id = doc.get("sop_id")
        title = doc.get("title", "Fulfillment SOP")
        category = doc.get("category", "General")
        version = doc.get("version", "1.0")
        status = doc.get("status", "demonstration")
        disclaimer = doc.get("disclaimer", "")
        sections = doc.get("sections", [])

        # If sections are missing but content is provided, create a single fallback section
        if not sections and "content" in doc:
            sections = [{"section_id": "SEC-GEN", "heading": "General Procedure", "content": doc["content"]}]

        chunks_text: List[str] = []
        chunk_ids: List[str] = []
        metadatas: List[Dict[str, Any]] = []

        for idx, sec in enumerate(sections):
            sec_id = sec.get("section_id", f"SEC-{idx+1}")
            heading = sec.get("heading", "Procedure")
            content = sec.get("content", "").strip()

            if not content:
                continue

            # Section-aware chunk formatting: combines heading and content
            chunk_content = f"{heading}: {content}"
            chunk_id = f"{sop_id}_{sec_id}"

            chunk_ids.append(chunk_id)
            chunks_text.append(chunk_content)
            metadatas.append({
                "sop_id": sop_id,
                "title": title,
                "category": category,
                "version": version,
                "status": status,
                "disclaimer": disclaimer,
                "section_id": sec_id,
                "heading": heading,
                "chunk_index": idx
            })

        if not chunk_ids:
            return 0

        # Remove stale chunks for this sop_id first
        self.delete_by_sop_id(sop_id)

        # Ingest to ChromaDB
        if self._collection is not None:
            self._collection.upsert(
                ids=chunk_ids,
                documents=chunks_text,
                metadatas=metadatas
            )
        else:
            # Fallback in-memory tracking
            self._fallback_docs = [d for d in self._fallback_docs if d.get("sop_id") != sop_id]
            for i, text in enumerate(chunks_text):
                self._fallback_docs.append({
                    "id": chunk_ids[i],
                    "text": text,
                    "sop_id": sop_id,
                    "title": title,
                    "category": category,
                    "version": version,
                    "status": status,
                    "disclaimer": disclaimer,
                    "section_id": metadatas[i]["section_id"],
                    "heading": metadatas[i]["heading"]
                })

        return len(chunk_ids)

    def delete_by_sop_id(self, sop_id: str):
        """Removes all indexed chunks associated with a specific SOP ID."""
        if self._collection is not None:
            try:
                # Query all IDs matching this sop_id
                existing = self._collection.get(where={"sop_id": sop_id})
                if existing and existing.get("ids"):
                    self._collection.delete(ids=existing["ids"])
            except Exception as e:
                logger.log_event("FULFILLMENT_DELETE_SOP_ERROR", {"sop_id": sop_id, "error": str(e)})

        # Always update in-memory fallback
        self._fallback_docs = [d for d in self._fallback_docs if d.get("sop_id") != sop_id]

    def query(
        self,
        query_text: str,
        top_k: int = DEFAULT_TOP_K,
        similarity_threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieves relevant SOP chunks using vector similarity or keyword fallback.
        
        Args:
            query_text: Natural language query.
            top_k: Maximum number of excerpts to return.
            similarity_threshold: Minimum normalized similarity score [0.0, 1.0].
                                 Results below this threshold are filtered out.
            category: Optional category filter.
            
        Returns:
            List of structured result dictionaries with content and source metadata.
        """
        if not query_text or not query_text.strip():
            return []

        clean_query = query_text.strip()
        where_filter = {"category": category} if category else None

        # 1. Primary Vector Search via ChromaDB
        if self._collection is not None and self._collection.count() > 0:
            try:
                query_kwargs = {
                    "query_texts": [clean_query],
                    "n_results": min(top_k * 2, self._collection.count())  # Fetch candidate buffer
                }
                if where_filter:
                    query_kwargs["where"] = where_filter

                results = self._collection.query(**query_kwargs)
                hits: List[Dict[str, Any]] = []

                if results and "documents" in results and results["documents"]:
                    docs = results["documents"][0]
                    metas = results["metadatas"][0] if "metadatas" in results else [{}] * len(docs)
                    distances = results["distances"][0] if "distances" in results and results["distances"] else [1.0] * len(docs)

                    for doc_text, meta, dist in zip(docs, metas, distances):
                        # Distance to similarity calculation:
                        # Chroma default uses L2 squared distance (or cosine distance).
                        # For normalized embeddings: similarity = max(0.0, 1.0 - (dist / 2.0)) or max(0.0, 1.0 - dist)
                        # We preserve both raw distance and estimated similarity score.
                        raw_dist = float(dist) if dist is not None else 1.0
                        similarity_score = round(max(0.0, 1.0 - (raw_dist / 2.0)), 4)

                        if similarity_score >= similarity_threshold:
                            hits.append({
                                "sop_id": meta.get("sop_id", "UNKNOWN"),
                                "title": meta.get("title", "Fulfillment SOP"),
                                "category": meta.get("category", "General"),
                                "version": meta.get("version", "1.0"),
                                "status": meta.get("status", "demonstration"),
                                "disclaimer": meta.get("disclaimer", ""),
                                "section_id": meta.get("section_id", "SEC-0"),
                                "heading": meta.get("heading", "Procedure"),
                                "content": doc_text,
                                "raw_distance": raw_dist,
                                "similarity_score": similarity_score,
                                "source_type": "vector_chromadb"
                            })

                if hits:
                    # Sort descending by similarity
                    hits.sort(key=lambda x: x["similarity_score"], reverse=True)
                    return hits[:top_k]

            except Exception as e:
                logger.log_event("FULFILLMENT_CHROMA_QUERY_ERROR", {"error": str(e)})

        # 2. Fallback Keyword Search
        return self._keyword_search_fallback(
            clean_query=clean_query,
            top_k=top_k,
            category=category,
            similarity_threshold=similarity_threshold
        )

    def _keyword_search_fallback(
        self,
        clean_query: str,
        top_k: int,
        category: Optional[str] = None,
        similarity_threshold: float = 0.2
    ) -> List[Dict[str, Any]]:
        """Fallback keyword overlap matcher when ChromaDB is unavailable or yields zero results."""
        query_words = set(re.findall(r"\w+", clean_query.lower()))
        # Remove low-value stop words
        stopwords = {"the", "a", "an", "is", "in", "at", "of", "and", "or", "for", "to", "what", "how", "should", "i", "do", "when"}
        meaningful_words = query_words - stopwords
        if not meaningful_words:
            meaningful_words = query_words

        candidates = self._fallback_docs
        if category:
            candidates = [d for d in candidates if d.get("category", "").lower() == category.lower()]

        scored_items = []
        for item in candidates:
            item_text = (item["text"] + " " + item["title"] + " " + item["heading"]).lower()
            item_words = set(re.findall(r"\w+", item_text))

            overlap = len(meaningful_words.intersection(item_words))
            if overlap > 0:
                score = round(overlap / max(1, len(meaningful_words)), 4)
                if score >= similarity_threshold:
                    scored_items.append((score, item))

        scored_items.sort(key=lambda x: x[0], reverse=True)
        results = []
        for score, item in scored_items[:top_k]:
            results.append({
                "sop_id": item["sop_id"],
                "title": item["title"],
                "category": item["category"],
                "version": item["version"],
                "status": item["status"],
                "disclaimer": item["disclaimer"],
                "section_id": item["section_id"],
                "heading": item["heading"],
                "content": item["text"],
                "raw_distance": None,
                "similarity_score": score,
                "source_type": "keyword_fallback"
            })
        return results

    def count(self) -> int:
        """Returns total count of indexed chunks in the collection."""
        if self._collection is not None:
            return self._collection.count()
        return len(self._fallback_docs)

    def clear(self):
        """Clears all records in the collection and in-memory cache."""
        if self._collection is not None and self._client is not None:
            try:
                self._client.delete_collection(self.collection_name)
                self._collection = self._client.get_or_create_collection(
                    name=self.collection_name,
                    metadata={"description": "IntelliWMS Dedicated Fulfillment SOPs and Procedures"}
                )
            except Exception as e:
                logger.log_event("FULFILLMENT_CLEAR_ERROR", {"error": str(e)})
        self._fallback_docs.clear()


# Default singleton instance for fulfillment knowledge
fulfillment_knowledge_store = FulfillmentKnowledgeStore()
