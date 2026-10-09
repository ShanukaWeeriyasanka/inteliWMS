"""
Unit and Integration Tests for Fulfillment Knowledge Store and RAG Retrieval Foundation.

Tests cover:
- Successful SOP ingestion from JSON.
- Vector retrieval of packing procedures (SOP-FLF-001).
- Vector retrieval of delay-handling procedures (SOP-FLF-002).
- Vector retrieval of dispatch/shipping procedures (SOP-FLF-003).
- Correct SOP source metadata and demonstration flags.
- Repeat ingestion without duplicates.
- Updating and removing stale chunks.
- Unrelated queries yielding no false matches.
- Empty knowledge base handling.
- Graceful ChromaDB fallback when storage is unavailable.
- Isolation between fulfillment_sop_knowledge and warehouse_knowledge collections.
"""
import pytest
from pathlib import Path
from agents.fulfillment.knowledge_store import FulfillmentKnowledgeStore


@pytest.fixture
def temp_store(tmp_path):
    """Provides an isolated FulfillmentKnowledgeStore instance backed by temporary storage."""
    store = FulfillmentKnowledgeStore(
        persist_dir=tmp_path / "chroma_test_fulfillment",
        collection_name="fulfillment_sop_knowledge_test"
    )
    return store


@pytest.fixture
def seeded_store(temp_store):
    """Pre-seeds the temporary store with the official demonstration fulfillment SOPs."""
    json_path = Path(__file__).resolve().parent.parent / "agents" / "fulfillment" / "data" / "fulfillment_sops.json"
    temp_store.ingest_from_file(json_path)
    return temp_store


# ==================== 1. Ingestion and Indexing Tests ====================

def test_successful_sop_ingestion(seeded_store):
    """Verifies that all 3 SOP documents and their individual sections are indexed."""
    # SOP-001 has 6 sections, SOP-002 has 6 sections, SOP-003 has 5 sections = 17 chunks
    count = seeded_store.count()
    assert count == 17, f"Expected 17 chunks from 3 SOPs, but got {count}"


def test_repeat_ingestion_no_duplicates(seeded_store):
    """Verifies that re-running ingestion does not create duplicate chunks."""
    initial_count = seeded_store.count()
    json_path = Path(__file__).resolve().parent.parent / "agents" / "fulfillment" / "data" / "fulfillment_sops.json"
    seeded_store.ingest_from_file(json_path)
    assert seeded_store.count() == initial_count


def test_update_and_remove_stale_chunks(temp_store):
    """Verifies that updating an SOP replaces old chunks and removes stale ones."""
    sample_v1 = {
        "sop_id": "SOP-TEST-001",
        "title": "Test Procedure",
        "category": "Testing",
        "version": "1.0",
        "status": "demonstration",
        "sections": [
            {"section_id": "SEC-1", "heading": "Old Step 1", "content": "Old content 1"},
            {"section_id": "SEC-2", "heading": "Old Step 2", "content": "Old content 2"}
        ]
    }
    temp_store.add_sop_document(sample_v1)
    assert temp_store.count() == 2

    # Update with only 1 section and different text
    sample_v2 = {
        "sop_id": "SOP-TEST-001",
        "title": "Test Procedure Updated",
        "category": "Testing",
        "version": "2.0",
        "status": "demonstration",
        "sections": [
            {"section_id": "SEC-1", "heading": "New Step 1", "content": "Updated content 1"}
        ]
    }
    temp_store.add_sop_document(sample_v2)
    assert temp_store.count() == 1

    # Verify retrieval returns the new version
    hits = temp_store.query("Updated content", top_k=2)
    assert len(hits) == 1
    assert hits[0]["version"] == "2.0"
    assert "New Step 1" in hits[0]["heading"]


# ==================== 2. Retrieval of Fulfillment Procedures ====================

def test_retrieve_packing_procedure(seeded_store):
    """Query: 'What is the procedure for packing an order?' should retrieve SOP-FLF-001."""
    hits = seeded_store.query("What is the procedure for packing an order?", top_k=3)
    assert len(hits) > 0
    top = hits[0]
    assert top["sop_id"] == "SOP-FLF-001"
    assert top["category"] == "Picking & Packing"
    assert "packing" in top["content"].lower() or "labeling" in top["content"].lower()
    assert top["status"] == "demonstration"
    assert top["disclaimer"] != ""


def test_retrieve_delay_handling_procedure(seeded_store):
    """Query: 'What should I do when an order is delayed?' should retrieve SOP-FLF-002."""
    hits = seeded_store.query("What should I do when an order is delayed?", top_k=3)
    assert len(hits) > 0
    top = hits[0]
    assert top["sop_id"] == "SOP-FLF-002"
    assert top["category"] == "Order Delays"
    assert "delay" in top["content"].lower() or "escalation" in top["content"].lower()
    assert "Order Delay Investigation" in top["title"]


def test_retrieve_dispatch_checks(seeded_store):
    """Query: 'What checks are required before dispatch?' should retrieve SOP-FLF-003."""
    hits = seeded_store.query("What checks are required before dispatch?", top_k=3)
    assert len(hits) > 0
    top = hits[0]
    assert top["sop_id"] == "SOP-FLF-003"
    assert top["category"] == "Dispatch & Shipping"
    assert "dispatch" in top["content"].lower() or "manifest" in top["content"].lower()


# ==================== 3. Source Metadata and Unrelated Queries ====================

def test_source_metadata_structure(seeded_store):
    """Verifies that all retrieved documents contain complete structured metadata."""
    hits = seeded_store.query("How to handle damaged stock during picking?", top_k=1)
    assert len(hits) > 0
    hit = hits[0]
    required_keys = [
        "sop_id", "title", "category", "version", "status",
        "disclaimer", "section_id", "heading", "content",
        "raw_distance", "similarity_score", "source_type"
    ]
    for key in required_keys:
        assert key in hit, f"Missing metadata key: {key}"
    assert hit["status"] == "demonstration"


def test_unrelated_query_no_results(seeded_store):
    """Irrelevant query should return empty list due to similarity threshold."""
    # Using a strict threshold for an unrelated query
    hits = seeded_store.query("How do I bake a chocolate cake with strawberries?", top_k=3, similarity_threshold=0.6)
    assert len(hits) == 0


def test_empty_knowledge_base_handling(temp_store):
    """Querying an empty store returns an empty list without raising exceptions."""
    hits = temp_store.query("Where is order ORD-1001?")
    assert hits == []
    assert temp_store.count() == 0


# ==================== 4. ChromaDB Failure & Fallback Tests ====================

def test_keyword_fallback_when_chromadb_unavailable(tmp_path):
    """When ChromaDB collection is None, the store gracefully uses in-memory keyword fallback."""
    store = FulfillmentKnowledgeStore(persist_dir=tmp_path / "fallback_dir", collection_name="fallback_coll")
    # Simulate Chroma failure
    store._collection = None
    store._client = None

    sample_doc = {
        "sop_id": "SOP-FLF-002",
        "title": "Order Delay Investigation",
        "category": "Order Delays",
        "version": "1.0",
        "status": "demonstration",
        "sections": [
            {"section_id": "SEC-2.6", "heading": "Escalation", "content": "Escalate to the fulfillment shift supervisor."}
        ]
    }
    store.add_sop_document(sample_doc)
    assert store.count() == 1

    hits = store.query("escalate to the supervisor", top_k=1)
    assert len(hits) == 1
    assert hits[0]["source_type"] == "keyword_fallback"
    assert hits[0]["sop_id"] == "SOP-FLF-002"
    assert "supervisor" in hits[0]["content"].lower()


# ==================== 5. Collection Isolation Test ====================

def test_isolation_from_general_knowledge_store(tmp_path):
    """
    Verifies that the Fulfillment store operates strictly on 'fulfillment_sop_knowledge'
    and never modifies or reads 'warehouse_knowledge'.
    """
    import chromadb
    client = chromadb.PersistentClient(path=str(tmp_path / "chroma_shared"))
    
    # 1. Create a dummy warehouse_knowledge collection simulating Knowledge Agent
    general_coll = client.get_or_create_collection("warehouse_knowledge")
    general_coll.add(
        ids=["SOP-HAZ-001_chunk_0"],
        documents=["Hazardous battery storage bay 15 rules."],
        metadatas=[{"sop_id": "SOP-HAZ-001", "category": "Safety"}]
    )

    # 2. Instantiate Fulfillment store on same client directory
    ff_store = FulfillmentKnowledgeStore(
        persist_dir=tmp_path / "chroma_shared",
        collection_name="fulfillment_sop_knowledge"
    )
    
    # Seed sample fulfillment SOP
    ff_store.add_sop_document({
        "sop_id": "SOP-FLF-001",
        "title": "Packing Guide",
        "category": "Picking & Packing",
        "version": "1.0",
        "status": "demonstration",
        "sections": [
            {"section_id": "SEC-1", "heading": "Packing Steps", "content": "Use bubble wrap and H-taping method."}
        ]
    })

    # 3. Fulfillment store should ONLY find its own chunks
    assert ff_store.count() == 1
    ff_hits = ff_store.query("Hazardous battery storage bay 15", top_k=2)
    # Since ff_store only searches fulfillment_sop_knowledge, it should NOT find SOP-HAZ-001
    for hit in ff_hits:
        assert hit["sop_id"] != "SOP-HAZ-001"

    # 4. Check that general_coll remains untouched
    assert general_coll.count() == 1
    general_docs = general_coll.get()
    assert general_docs["ids"] == ["SOP-HAZ-001_chunk_0"]
