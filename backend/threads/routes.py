"""
Chat thread API — the sidebar list, loading a conversation, deleting conversations.

All endpoints need a signed-in user and only ever touch that user's threads.
New threads are created by POST /query on the first message of a conversation.
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, Query, Response

from backend.auth import Identity
from backend.threads.deps import get_thread_store, require_identity
from backend.threads.store import ThreadStore
from utils import request_context
from utils.logger import StructuredLogger
from utils.metrics import THREAD_OPERATIONS

logger = StructuredLogger(__name__)
router = APIRouter(prefix="/threads", tags=["Chat Threads"])


@router.get("")
def list_threads(limit: int = Query(50, ge=1, le=200),
                 identity: Identity = Depends(require_identity),
                 store: ThreadStore = Depends(get_thread_store)) -> Dict[str, Any]:
    threads = store.list(identity.user_id, limit=limit)
    return {"status": "success", "threads": [t.model_dump() for t in threads]}


@router.get("/{thread_id}")
def get_thread(thread_id: str,
               limit: int = Query(200, ge=1, le=500),
               identity: Identity = Depends(require_identity),
               store: ThreadStore = Depends(get_thread_store)) -> Dict[str, Any]:
    tid = store.parse_thread_id(thread_id)
    tokens = request_context.bind(thread_id=tid)
    try:
        thread = store.get_owned(tid, identity.user_id)
        messages, has_more = store.messages(thread, limit=limit)
        THREAD_OPERATIONS.inc(op="select", outcome="ok")
        logger.log_event("THREAD_SELECTED", {"message_count": len(messages), "has_more": has_more})
        return {
            "status": "success",
            "thread": store.summary(thread).model_dump(),
            "messages": [m.model_dump() for m in messages],
            "has_more": has_more,
        }
    finally:
        request_context.reset(tokens)


@router.delete("/{thread_id}", status_code=204)
def delete_thread(thread_id: str,
                  identity: Identity = Depends(require_identity),
                  store: ThreadStore = Depends(get_thread_store)) -> Response:
    store.delete(store.parse_thread_id(thread_id), identity.user_id)
    return Response(status_code=204)


@router.delete("")
def delete_all_threads(identity: Identity = Depends(require_identity),
                       store: ThreadStore = Depends(get_thread_store)) -> Dict[str, Any]:
    return {"status": "success", "deleted": store.delete_all(identity.user_id)}
