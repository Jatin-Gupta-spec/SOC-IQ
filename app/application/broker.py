"""
EventBroker -- live in-process event distribution, per
docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md S6 (FINAL architecture
decision, not reopened here).

This is the "smallest correct architecture" that document resolved on:
synchronous command handlers publish `Event` objects (app.application.
events.Event) into this broker; any number of independent subscribers
each get their own bounded, FIFO, drop-oldest queue of the events
published while they were subscribed. There is no replay (S6: "no replay
in the first implementation, and this is a deliberate, justified cut"),
no cross-subscriber ordering guarantee (S6 Ordering: "per-subscriber FIFO
only"), and no dependency on any transport.

Deliberately excluded from this module, per PHASE4D_SSE_ARCHITECTURE_
DECISION.md S17 and the Part 1 task scope that introduced this file:
no FastAPI/Starlette import, no SSE framing, no heartbeat, no frontend
concern. Those are S10/S7 concerns and belong to a later part. This
module has zero import of `fastapi`, `starlette`, `PySide6`, `app.gui`,
or anything Tauri/Rust-related -- verified by grep, see
docs/phase4/PHASE4D_SSE_PART1_IMPLEMENTATION.md.

Usage (illustrative -- no caller exists in production code yet in this
Part; only tests and, later, the SSE transport in a subsequent Part,
construct and use this):

    broker = EventBroker()
    subscription = broker.subscribe()
    ...
    broker.publish(event)                    # from a command handler
    ...
    event = subscription.get(timeout=1.0)     # from an SSE route, later
    ...
    broker.unsubscribe(subscription)          # on client disconnect
"""

from __future__ import annotations

import threading
from collections import deque
from contextlib import contextmanager
from typing import Iterator

from app.application.events import Event

DEFAULT_SUBSCRIBER_CAPACITY = 32


class Subscription:
    """
    One subscriber's bounded, FIFO, drop-oldest queue of `Event`s.

    Created only by `EventBroker.subscribe()` -- never construct this
    directly, since an un-registered `Subscription` would receive nothing
    (see `EventBroker.subscribe()`'s docstring).

    Thread safety: `_put()` (called by `EventBroker.publish()`, from
    whichever thread the publishing command handler runs on) and `get()`/
    `get_nowait()` (called by whichever thread eventually consumes this
    subscription -- the future SSE route) may run concurrently. Both are
    guarded by the same lock; `get()`'s wait uses a `threading.Condition`
    on that lock so a blocking consumer is woken promptly by a publish
    without polling.
    """

    def __init__(self, capacity: int = DEFAULT_SUBSCRIBER_CAPACITY) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity!r}")

        self._capacity = capacity
        # `deque(maxlen=capacity)` is the drop-oldest mechanism itself:
        # appending past `maxlen` silently discards from the opposite end
        # (the oldest, left-hand item) with no separate eviction logic
        # needed -- see `_put()` for how the dropped-count is still
        # tracked despite that silence.
        self._events: deque[Event] = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._closed = False
        self._dropped_count = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def dropped_count(self) -> int:
        """
        Number of events silently evicted by the drop-oldest policy
        because this subscriber fell more than `capacity` events behind.
        Exposed so a caller (or a test) can detect backpressure rather
        than have it be invisible, per
        PHASE4D_SSE_ARCHITECTURE_DECISION.md S6/S13's requirement that
        drops be counted/logged, not swallowed silently.
        """

        with self._lock:
            return self._dropped_count

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def _put(self, event: Event) -> None:
        """Called only by `EventBroker.publish()`. Never blocks."""

        with self._not_empty:
            if self._closed:
                return
            was_full = len(self._events) == self._events.maxlen
            self._events.append(event)
            if was_full:
                self._dropped_count += 1
            self._not_empty.notify()

    def get(self, timeout: float | None = None) -> Event | None:
        """
        Block until an event is available, the subscription is closed, or
        `timeout` seconds elapse (`None` = wait indefinitely). Returns
        `None` if the wait timed out, or if the subscription was closed
        with nothing left queued -- either way, a `None` return means
        "nothing to deliver right now", not "an event happened to be
        None."
        """

        with self._not_empty:
            while not self._events and not self._closed:
                if not self._not_empty.wait(timeout=timeout):
                    return None
            if self._events:
                return self._events.popleft()
            return None

    def get_nowait(self) -> Event | None:
        """Non-blocking variant of `get()` -- returns `None` if empty."""

        with self._lock:
            if self._events:
                return self._events.popleft()
            return None

    def drain(self) -> list[Event]:
        """Return and remove every currently-queued event, oldest first."""

        with self._lock:
            drained = list(self._events)
            self._events.clear()
            return drained

    def close(self) -> None:
        """
        Mark this subscription closed. Idempotent. Any thread blocked in
        `get()` is woken and returns `None` once the queue drains. Does
        NOT discard already-queued, not-yet-delivered events -- a
        consumer that is mid-`drain()`/`get()` when `close()` is called
        can still receive what was already queued; `close()` only stops
        *future* deliveries (`_put()` becomes a no-op) and unblocks
        waiters once nothing is left.
        """

        with self._not_empty:
            if self._closed:
                return
            self._closed = True
            self._not_empty.notify_all()

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)


class EventBroker:
    """
    Owns the set of live subscribers and fans out published `Event`s to
    each of them. One instance is intended to live for the lifetime of
    the process (see PHASE4D_SSE_ARCHITECTURE_DECISION.md S6/S10: created
    once, owned by the process entrypoint) -- this module does not itself
    create or manage that singleton; that wiring is transport-layer
    concern, out of scope for this Part.
    """

    def __init__(self, capacity: int = DEFAULT_SUBSCRIBER_CAPACITY) -> None:
        self._capacity = capacity
        self._subscribers: set[Subscription] = set()
        self._lock = threading.Lock()
        self._shut_down = False

    def subscribe(self) -> Subscription:
        """
        Register a new subscriber and return its `Subscription`. Safe to
        call from any thread, including concurrently with `publish()`
        and other `subscribe()`/`unsubscribe()` calls.

        If called after `shutdown()`, returns an already-closed
        `Subscription` (consistent with "no new subscribers after
        shutdown") rather than raising -- a caller racing shutdown gets a
        subscription that immediately reports closed/empty rather than an
        exception.
        """

        subscription = Subscription(self._capacity)
        with self._lock:
            if self._shut_down:
                subscription.close()
                return subscription
            self._subscribers.add(subscription)
        return subscription

    def unsubscribe(self, subscription: Subscription) -> None:
        """
        Remove and close a subscription. Idempotent -- unsubscribing a
        subscription that isn't (or is no longer) registered is a no-op
        beyond ensuring it's closed, so double-unsubscribe (e.g. an
        explicit call racing a `shutdown()`) is safe.
        """

        with self._lock:
            self._subscribers.discard(subscription)
        subscription.close()

    def publish(self, event: Event) -> None:
        """
        Deliver `event` to every currently-registered subscriber.

        The broker's own lock is held only long enough to snapshot the
        current subscriber set -- never while pushing into an individual
        `Subscription` (each of which has its own, separate lock). This
        is deliberate: it keeps `publish()` from a slow/blocked
        subscriber able to stall either another subscriber's delivery or
        a concurrent `subscribe()`/`unsubscribe()` call, and it avoids
        ever holding two different locks in nested order (broker lock,
        then a subscription lock) across a call that could block --
        `Subscription._put()` never blocks (drop-oldest, not
        block-on-full), so even the brief nested acquisition here cannot
        deadlock against a `Subscription.close()`/`get()` call, which
        only ever acquires the subscription's own lock, never the
        broker's.

        A no-op, not an error, if there are no subscribers (an
        `analyze_report` or `enrich_ioc` call with no SSE client attached
        must never fail or behave differently because nothing is
        listening -- the command's own HTTP response is unaffected
        either way, per PHASE4D_SSE_ARCHITECTURE_DECISION.md S8).
        """

        with self._lock:
            if self._shut_down:
                return
            subscribers = list(self._subscribers)

        for subscription in subscribers:
            subscription._put(event)

    def shutdown(self) -> None:
        """
        Close every current subscription and stop accepting new ones.
        Idempotent. Intended for process shutdown
        (PHASE4D_SSE_ARCHITECTURE_DECISION.md S6 Shutdown) -- after this
        call, `publish()` is a no-op and `subscribe()` returns
        pre-closed subscriptions, so no command handler blocks or errors
        because the broker is going away mid-shutdown.
        """

        with self._lock:
            if self._shut_down:
                return
            self._shut_down = True
            subscribers = list(self._subscribers)
            self._subscribers.clear()

        for subscription in subscribers:
            subscription.close()

    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._subscribers)

    @contextmanager
    def subscription(self) -> Iterator[Subscription]:
        """
        Convenience context manager: `subscribe()` on enter,
        `unsubscribe()` on exit (including on exception) -- primarily for
        tests and any future non-HTTP consumer; the eventual SSE route
        will likely manage this lifecycle itself (tied to the HTTP
        connection's own lifetime) rather than use this helper, since it
        needs to unsubscribe specifically on client disconnect, not on
        leaving a `with` block.
        """

        sub = self.subscribe()
        try:
            yield sub
        finally:
            self.unsubscribe(sub)


# ---------------------------------------------------------------------------
# Process-lifetime singleton, per PHASE4D_SSE_PART2_IMPLEMENTATION.md
# ("There must be ONE application-level EventBroker instance for the live
# application"). Introduced in Part 2 -- Part 1 deliberately left this
# unwired ("no caller exists in production code yet in this Part", module
# docstring above); Part 2 is the first Part with a production publisher
# (the command handlers), so this is the first Part that needs somewhere
# for them to publish to.
#
# Lives here, not in app/api/entrypoint.py, because the command handlers
# (app/application/handlers.py) must be able to publish events today,
# before any FastAPI transport wiring exists (that wiring is Part 3+
# scope, explicitly deferred -- see PHASE4D_SSE_PART2_IMPLEMENTATION.md).
# When the SSE transport is added, `app/api/entrypoint.py` can simply call
# `get_application_broker()` too, rather than constructing a second
# broker -- there is still exactly one instance either way.
# ---------------------------------------------------------------------------

_application_broker: EventBroker | None = None
_application_broker_lock = threading.Lock()


def get_application_broker() -> EventBroker:
    """
    Return the one process-lifetime `EventBroker` used by production
    command handlers. Lazily constructed on first call, then reused for
    the life of the process -- never recreated, never more than one at a
    time.

    Tests should NOT rely on this singleton to assert on broker behavior
    in isolation (its state persists across tests in the same process,
    per unittest's default single-process execution) -- construct a
    fresh `EventBroker()` directly instead, and inject it into a
    handler's `broker=` parameter. This function exists for production
    wiring (handlers' default `broker=None` falls back to it) and for
    any test that specifically wants to assert against the *real*
    production broker (e.g. "handlers publish to the application broker
    by default when none is injected").
    """

    global _application_broker
    with _application_broker_lock:
        if _application_broker is None:
            _application_broker = EventBroker()
        return _application_broker
