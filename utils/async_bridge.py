"""
Run an async function from synchronous code.

The inventory agent is async (it talks to its MCP server). Older synchronous
callers (tests, scripts, mcp_servers/coordinator_client.py) still call it
through a sync facade, sometimes from inside a running event loop. In that case
the coroutine runs on a short-lived worker thread with its own loop, carrying
over the caller's contextvars so request / trace ids stay on the log lines.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, Optional, TypeVar

import anyio

from utils import request_context
from utils.logger import StructuredLogger

T = TypeVar("T")
logger = StructuredLogger(__name__)


def run_sync(async_fn: Callable[[], Awaitable[T]], timeout_s: Optional[float] = None) -> T:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return anyio.run(async_fn)
    logger.log_event("SYNC_FACADE_IN_EVENT_LOOP", {"function": getattr(async_fn, "__name__", "callable")},
                     level="DEBUG")
    # Copy only the correlation ids: copying the whole context would also copy sniffio's
    # "asyncio is running here" marker and anyio.run would refuse to start.
    correlation = request_context.current()

    def runner() -> T:
        tokens = request_context.bind(**correlation)
        try:
            return anyio.run(async_fn)
        finally:
            request_context.reset(tokens)

    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="async-bridge") as pool:
        return pool.submit(runner).result(timeout=timeout_s)
