"""
Context Builder for IntelliWMS Coordinator Agent (Task 2).
Extracts operational warehouse entities (SKUs, Order IDs) from user queries
and packages a structured context payload for the target specialist agent.
"""
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any

def extract_sku(message: str) -> Optional[str]:
    """Extracts warehouse SKU pattern like SKU-4521 or SKU7788 from query."""
    if not message:
        return None
    match = re.search(r"\b(SKU-?[0-9]{4,6})\b", message, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None

def extract_order_id(message: str) -> Optional[str]:
    """Extracts warehouse Order ID pattern like ORD-1001, #4521, or order 4521.
    
    All formats are normalized to ORD-XXXX so the fulfillment agent's
    extractor (which only accepts ORD- prefix) can recognize them.
    """
    if not message:
        return None
    # Match ORD-XXXX (canonical format)
    match = re.search(r"\b(ORD-[0-9]{3,6})\b", message, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    # Match #XXXX → normalize to ORD-XXXX
    match = re.search(r"#([0-9]{3,6})\b", message)
    if match:
        return f"ORD-{match.group(1)}"
    # Match 'order 4521' → normalize to ORD-4521
    match = re.search(r"\border\s+([0-9]{3,6})\b", message, re.IGNORECASE)
    if match:
        return f"ORD-{match.group(1)}"
    return None

def build_context(
    user_id: str,
    message: str,
    intent: str,
    role: str = "staff",
    session_id: Optional[str] = None,
    thread_id: Optional[str] = None,
    conversation: Optional[Dict[str, Any]] = None,
    entity_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Builds structured context payload for target specialist agent.
    
    Args:
        user_id: Unique user identifier
        message: Sanitized natural language user message
        intent: Classified domain (INVENTORY, FULFILLMENT, KNOWLEDGE)
        role: User role (staff, manager, admin)
        session_id: Browser session that receives Digital Twin map commands
        thread_id: Chat conversation this message belongs to (not a request or trace id)
        conversation: What the inventory agent last discussed in this thread (follow-ups)
        entity_text: An accepted rewrite of the message; ids found only there are used as hints
            (the rewrite guard guarantees their digits were typed by the user)

    Returns:
        Structured context payload dictionary with audit metadata
    """
    extracted_sku = extract_sku(message) or (extract_sku(entity_text) if entity_text else None)
    extracted_order = extract_order_id(message) or (extract_order_id(entity_text) if entity_text else None)

    return {
        "user_id": user_id,
        "user_role": role,
        "original_message": message,
        "query": message,  # backwards compatibility with MCP client
        "intent": intent,
        "extracted_sku": extracted_sku,
        "extracted_order_id": extracted_order,
        "session_id": session_id,
        "thread_id": thread_id,
        "conversation": conversation,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "audit_log": "routed_by_coordinator"
    }
