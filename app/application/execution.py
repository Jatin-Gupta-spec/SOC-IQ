"""
Narrow thread-execution boundary for the one existing blocking-I/O span in
the application layer, per
docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md S3 (Option A, with
Option C's background-worker pattern "explicitly reserved for
`enrich_ioc`'s blocking network span ... not adopted project-wide") and
docs/phase4/PHASE4D_SSE_PART2_IMPLEMENTATION.md's execution-model fix.

THE PROBLEM (confirmed against current source, not assumed):

    EnrichIocCommandHandler.handle()
      -> ThreatIntelService.lookup_indicator()
        -> ThreatIntelService._lookup_raw()
          -> asyncio.run(provider.lookup_raw(ioc))      # service.py:223

`asyncio.run()` always creates a brand-new event loop on whatever thread
calls it, and raises `RuntimeError: asyncio.run() cannot be called from a
running event loop` if that thread already has one running. `app/api/app.py`'s
`POST /commands/{name}` route is `async def` and calls the dispatch table
directly, on the request coroutine's own thread -- so once FastAPI is
actually running (it is not installed in this sandbox), a live call to
`enrich_ioc` would hit exactly that `RuntimeError`.

THE FIX -- smallest correct boundary, not a rewrite of ThreatIntelService:

Run the *entire* synchronous `lookup_indicator(...)` call (asyncio.run()
bridge included) on a dedicated worker thread, via a small
`concurrent.futures.ThreadPoolExecutor`, and block the *calling* thread on
the future's result. This is the standard-library mechanism already
appropriate here -- no custom thread-pool framework, no new dependency.

Why this is sufficient and closes the bug, without touching
ThreatIntelService/VirusTotalProvider/VirusTotalClient at all:

- `asyncio.run()` only fails when a *running loop already exists on the
  calling thread*. A `ThreadPoolExecutor` worker thread never has one
  (it's a plain OS thread started by the pool, not the FastAPI event-loop
  thread) -- so `asyncio.run()` inside `_lookup_raw` is always safe there,
  regardless of what thread submitted the work or whether *that* thread
  has a running loop of its own.
- The calling handler still blocks and returns a plain result or raises,
  exactly like every other synchronous handler in this codebase --
  `EnrichIocCommandHandler.handle()`'s signature and synchronous-caller
  contract are unchanged (Stage 4, requirement 1).
- `concurrent.futures.ThreadPoolExecutor` is stdlib, and this codebase
  already uses a background-thread pattern for this exact operation
  (`app/gui/pages/threat_intel_page.py`'s `_VirusTotalLookupWorker`, a
  `QThread` subclass, per `EnrichIocRequest`'s own docstring) -- routing
  the blocking span through a small stdlib executor instead of inventing
  a new framework is the narrowest change consistent with that existing
  precedent.

THE POOL IS BOUNDED AND PROCESS-LIFETIME, NOT PER-CALL:

One module-level `ThreadPoolExecutor` (small, fixed `max_workers`),
created lazily on first use and never explicitly shut down (mirrors the
process-lifetime `EventBroker` singleton in `app/application/broker.py`;
SOC-IQ's process itself is the natural owner/lifetime for both). This
means calling `enrich_ioc` a thousand times reuses a bounded set of
worker threads rather than spawning a new one per call -- no thread
leak. `run_blocking()` is generic (not VirusTotal-specific) so it could
serve a future narrowly-scoped blocking call elsewhere without
introducing a second pool, but nothing outside `EnrichIocCommandHandler`
uses it yet.
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, ParamSpec, TypeVar

P = ParamSpec("P")
T = TypeVar("T")

DEFAULT_MAX_WORKERS = 4

_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(
                max_workers=DEFAULT_MAX_WORKERS,
                thread_name_prefix="soc-iq-blocking-io",
            )
        return _executor


def run_blocking(fn: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """
    Execute `fn(*args, **kwargs)` on a dedicated worker thread (never the
    calling thread) and block the calling thread until it finishes,
    returning its result or re-raising whatever exception it raised.

    Safe to call from a thread that already has a running asyncio event
    loop -- the submitted callable never runs on that thread, only on a
    separate pool worker, so a `RuntimeError` from a nested
    `asyncio.run()` cannot occur regardless of the caller's own loop
    state. This is the whole point of the boundary: `fn` itself does not
    need to know or care whether it was called from sync code, from
    inside a running event loop, or from another thread.
    """

    future = _get_executor().submit(fn, *args, **kwargs)
    return future.result()
