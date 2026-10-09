"""
Ownership of Digital Twin map sessions.

A browser tab picks a random session id and receives the agent's map commands for it
(GET /twin/stream, GET/POST /twin/commands, POST /query session_id). The first signed-in
user to use a session id owns it; anyone else is refused, so one user can neither watch
another user's map commands nor push commands onto their map.

Ownership lives in process memory (one uvicorn worker). It resets on restart, which only
means the next user of an id claims it again. Old entries are evicted beyond MAX_SESSIONS.
"""
import threading
from collections import OrderedDict

MAX_SESSIONS = 10_000


class TwinSessionRegistry:
    def __init__(self, max_sessions: int = MAX_SESSIONS) -> None:
        self._owners: "OrderedDict[str, str]" = OrderedDict()
        self._lock = threading.Lock()
        self._max = max_sessions

    def claim(self, session_id: str, user_id: str) -> bool:
        """True when `user_id` owns the session (claiming it if nobody does yet)."""
        if not session_id or not user_id:
            return False
        with self._lock:
            owner = self._owners.get(session_id)
            if owner is None:
                self._owners[session_id] = user_id
                if len(self._owners) > self._max:
                    self._owners.popitem(last=False)
                return True
            self._owners.move_to_end(session_id)
            return owner == user_id

    def clear(self) -> None:
        with self._lock:
            self._owners.clear()


twin_sessions = TwinSessionRegistry()
