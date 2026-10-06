"""
Chat thread persistence.

Every read and write is scoped to the owning user's id, so messages from
different users or threads can never be mixed. Thread ids are canonical UUIDs
created here; they are independent of request ids, trace ids and the twin
map's browser session id.
"""
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.threads.errors import InvalidThreadId, ThreadNotFound
from backend.threads.schemas import MessageOut, ThreadContext, ThreadSummary, iso_utc
from database.models import ChatMessageRecord, ChatThread
from utils.logger import StructuredLogger
from utils.metrics import THREAD_OPERATIONS

logger = StructuredLogger(__name__)

_UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
MAX_META_BYTES = 32 * 1024
HISTORY_SNIPPET_CHARS = 300
# Large / derivable payloads that are never stored with a message
_META_DROP_KEYS = {"warehouse_layout"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _trim_meta(meta: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Keep what the UI needs to re-render a message; cap the stored size."""
    if not meta:
        return None
    clean = json.loads(json.dumps(meta, default=str))
    inv = clean.get("inventory_details")
    if isinstance(inv, dict):
        for k in _META_DROP_KEYS:
            inv.pop(k, None)
        if isinstance(inv.get("items"), list):
            inv["items"] = inv["items"][:10]
    for k in _META_DROP_KEYS:
        clean.pop(k, None)
    if len(json.dumps(clean)) > MAX_META_BYTES:
        # Fall back to the routing summary only — the text answer is stored separately
        clean = {k: clean[k] for k in ("routing", "agent_used", "status") if k in clean}
        clean["meta_truncated"] = True
    return clean


class ThreadStore:
    def __init__(self, session: Session):
        self.db = session

    # ── ids & lookup ────────────────────────────────────────────────────────
    @staticmethod
    def parse_thread_id(raw: Optional[str]) -> str:
        if not raw or not _UUID.match(raw.strip()):
            THREAD_OPERATIONS.inc(op="lookup", outcome="invalid")
            logger.log_event("THREAD_LOOKUP", {"outcome": "invalid_id"}, level="WARNING")
            raise InvalidThreadId()
        return str(uuid.UUID(raw.strip()))

    def get_owned(self, thread_id: str, owner_id: str) -> ChatThread:
        thread = self.db.get(ChatThread, thread_id)
        if thread is None or thread.user_id != owner_id:
            reason = "missing" if thread is None else "not_owner"
            THREAD_OPERATIONS.inc(op="lookup", outcome=reason)
            logger.log_event("THREAD_LOOKUP", {"outcome": "not_found", "reason": reason},
                             level="WARNING" if reason == "not_owner" else "INFO")
            raise ThreadNotFound()
        THREAD_OPERATIONS.inc(op="lookup", outcome="ok")
        logger.log_event("THREAD_LOOKUP", {"outcome": "ok", "message_count": thread.message_count})
        return thread

    # ── create / read ───────────────────────────────────────────────────────
    def create(self, owner_id: str, title: str) -> ChatThread:
        """New thread (added to the session; committed together with its first exchange)."""
        title = " ".join((title or "").split())[:60] or "New conversation"
        thread = ChatThread(id=str(uuid.uuid4()), user_id=owner_id, title=title, message_count=0,
                            context_json=ThreadContext().model_dump(), created_at=_now(), updated_at=_now())
        self.db.add(thread)
        return thread

    def list(self, owner_id: str, limit: int = 50) -> List[ThreadSummary]:
        rows = (self.db.query(ChatThread)
                .filter(ChatThread.user_id == owner_id)
                .order_by(ChatThread.updated_at.desc(), ChatThread.created_at.desc())
                .limit(limit).all())
        THREAD_OPERATIONS.inc(op="list", outcome="ok")
        return [self.summary(t) for t in rows]

    @staticmethod
    def summary(t: ChatThread) -> ThreadSummary:
        return ThreadSummary(id=t.id, title=t.title, last_agent=t.last_agent, message_count=t.message_count or 0,
                             created_at=iso_utc(t.created_at), updated_at=iso_utc(t.updated_at))

    def messages(self, thread: ChatThread, limit: int = 200) -> Tuple[List[MessageOut], bool]:
        rows = (self.db.query(ChatMessageRecord)
                .filter(ChatMessageRecord.thread_id == thread.id, ChatMessageRecord.user_id == thread.user_id)
                .order_by(ChatMessageRecord.id.desc())
                .limit(limit + 1).all())
        has_more = len(rows) > limit
        rows = list(reversed(rows[:limit]))
        return [MessageOut(id=r.id, role=r.role, content=r.content, agent_used=r.agent_used, status=r.status,
                           request_id=r.request_id, meta=r.meta_json, created_at=iso_utc(r.created_at))
                for r in rows], has_more

    def recent_history(self, thread: ChatThread, n: int) -> List[Dict[str, Any]]:
        """Last n messages (oldest first), shortened — conversation context for the agents."""
        rows = (self.db.query(ChatMessageRecord)
                .filter(ChatMessageRecord.thread_id == thread.id, ChatMessageRecord.user_id == thread.user_id)
                .order_by(ChatMessageRecord.id.desc())
                .limit(max(0, n)).all())
        return [{"role": r.role, "agent": r.agent_used, "content": (r.content or "")[:HISTORY_SNIPPET_CHARS]}
                for r in reversed(rows)]

    def context(self, thread: ChatThread) -> ThreadContext:
        try:
            return ThreadContext.model_validate(thread.context_json or {})
        except ValidationError:
            logger.log_event("THREAD_CONTEXT_RESET", {"reason": "invalid_context_json"}, level="WARNING")
            return ThreadContext()

    # ── write ───────────────────────────────────────────────────────────────
    def append_exchange(self, thread: ChatThread, *, user_text: str, assistant_text: str,
                        agent_used: Optional[str], status: str, request_id: Optional[str],
                        meta: Optional[Dict[str, Any]], context: ThreadContext) -> None:
        """Store the user message and the reply in one commit and update the thread state."""
        is_new = thread.message_count in (None, 0) and thread in self.db.new
        if not is_new:
            # The thread may have been deleted (e.g. "clear history" in another tab) mid-request
            still_there = (self.db.query(ChatThread.id)
                           .filter(ChatThread.id == thread.id, ChatThread.user_id == thread.user_id).first())
            if still_there is None:
                THREAD_OPERATIONS.inc(op="append", outcome="missing")
                raise ThreadNotFound()
        now = _now()
        self.db.add(ChatMessageRecord(thread_id=thread.id, user_id=thread.user_id, role="user",
                                      content=user_text, request_id=request_id, created_at=now))
        self.db.add(ChatMessageRecord(thread_id=thread.id, user_id=thread.user_id, role="assistant",
                                      content=assistant_text or "", agent_used=agent_used, status=status,
                                      request_id=request_id, meta_json=_trim_meta(meta), created_at=now))
        thread.message_count = (thread.message_count or 0) + 2
        thread.updated_at = now
        if agent_used:
            thread.last_agent = agent_used
        thread.context_json = context.model_dump()
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            THREAD_OPERATIONS.inc(op="append", outcome="error")
            raise
        THREAD_OPERATIONS.inc(op="create" if is_new else "append", outcome="ok")
        if is_new:
            logger.log_event("THREAD_CREATED", {"thread_id": thread.id})

    def delete(self, thread_id: str, owner_id: str) -> None:
        thread = self.get_owned(thread_id, owner_id)
        # SQLite does not enforce ON DELETE CASCADE unless foreign keys are switched on
        self.db.query(ChatMessageRecord).filter(ChatMessageRecord.thread_id == thread.id).delete()
        self.db.delete(thread)
        self.db.commit()
        THREAD_OPERATIONS.inc(op="delete", outcome="ok")
        logger.log_event("THREAD_DELETED", {"thread_id": thread_id})

    def delete_all(self, owner_id: str) -> int:
        ids = [t.id for t in self.db.query(ChatThread.id).filter(ChatThread.user_id == owner_id).all()]
        if ids:
            self.db.query(ChatMessageRecord).filter(ChatMessageRecord.thread_id.in_(ids)).delete(
                synchronize_session=False)
            self.db.query(ChatThread).filter(ChatThread.id.in_(ids)).delete(synchronize_session=False)
            self.db.commit()
        THREAD_OPERATIONS.inc(op="delete_all", outcome="ok")
        logger.log_event("THREADS_CLEARED", {"count": len(ids)})
        return len(ids)
