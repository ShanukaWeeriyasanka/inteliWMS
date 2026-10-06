"""
Live updates for the Warehouse Digital Twin.

PostgreSQL triggers (database/twin/realtime.sql) send every change to
stock_locations, alerts, ui_commands and nav_edges with pg_notify. One
background thread LISTENs on that channel and fans the events out to every
browser connected to GET /twin/stream (Server-Sent Events).

When the database connection drops, subscribers get {"live": false} so the
UI can show "Live updates paused", and the thread reconnects on its own.
"""
import asyncio
import json
import select
import threading
from typing import Any, Dict, Optional, Set

import psycopg2

from config.settings import settings
from database.twin.connection import twin_database_url
from utils.logger import StructuredLogger

logger = StructuredLogger(__name__)


class TwinSubscriber:
    """One browser connection. Receives events on an asyncio queue."""

    def __init__(self, loop: asyncio.AbstractEventLoop, session_id: Optional[str]):
        self.loop = loop
        self.session_id = session_id
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=500)

    def wants(self, event: Dict[str, Any]) -> bool:
        # ui_commands are private to the browser session they were written for
        if event.get("table") == "ui_commands":
            return bool(self.session_id) and event.get("row", {}).get("session_id") == self.session_id
        return True

    def push(self, event: Dict[str, Any]) -> None:
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # a stalled client misses events; it re-fetches on reconnect


class TwinChangeBroker:
    def __init__(self) -> None:
        self._subscribers: Set[TwinSubscriber] = set()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.live = False

    # ── subscribers ──
    def subscribe(self, session_id: Optional[str]) -> TwinSubscriber:
        sub = TwinSubscriber(asyncio.get_running_loop(), session_id)
        with self._lock:
            self._subscribers.add(sub)
        self._ensure_thread()
        return sub

    def unsubscribe(self, sub: TwinSubscriber) -> None:
        with self._lock:
            self._subscribers.discard(sub)

    def _broadcast(self, event: Dict[str, Any]) -> None:
        with self._lock:
            subs = list(self._subscribers)
        for sub in subs:
            if sub.wants(event):
                sub.loop.call_soon_threadsafe(sub.push, event)

    def _set_live(self, live: bool) -> None:
        if live != self.live:
            self.live = live
            self._broadcast({"type": "status", "live": live})

    # ── listener thread ──
    def _ensure_thread(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="twin-listen", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        dsn = twin_database_url()
        channel = settings.TWIN_NOTIFY_CHANNEL
        while not self._stop.is_set():
            conn = None
            try:
                conn = psycopg2.connect(dsn)
                conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
                conn.cursor().execute(f'LISTEN "{channel}"')
                self._set_live(True)
                logger.log_event("TWIN_LISTEN_STARTED", {"channel": channel})
                while not self._stop.is_set():
                    if select.select([conn], [], [], 5) == ([], [], []):
                        continue
                    conn.poll()
                    while conn.notifies:
                        note = conn.notifies.pop(0)
                        try:
                            event = json.loads(note.payload)
                        except ValueError:
                            continue
                        event["type"] = "change"
                        self._broadcast(event)
            except Exception as exc:
                self._set_live(False)
                logger.log_event("TWIN_LISTEN_ERROR", {"error": str(exc)})
                self._stop.wait(settings.TWIN_LISTEN_RETRY_S)
            finally:
                if conn is not None:
                    try:
                        conn.close()
                    except Exception:
                        pass
        self._set_live(False)


twin_broker = TwinChangeBroker()
