"""
Event model, per docs/contracts/event-model.md, event-versioning.md, and
correlation-ids.md.

Per docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md S3/S6 (FINAL, not
reopened here): this module now also owns the live in-process transport --
`EventBroker`, in app/application/broker.py -- alongside the pre-existing
schema and the ephemeral, test-oriented `EventCollector`. `EventCollector`
is unchanged and remains purely a test helper (see its own docstring,
below, and PHASE4D_SSE_ARCHITECTURE_DECISION.md S9): it does NOT become the
broker, and the broker does NOT replace it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


def new_correlation_id(prefix: str) -> str:
    """e.g. new_correlation_id("an") -> 'an-8f3c1a2b9d4e'."""
    return f"{prefix}-{uuid4().hex[:12]}"


def _new_event_id() -> str:
    """e.g. '8f3c1a2b9d4e1f0a'.

    Deliberately a plain uuid4-derived id generated at `Event.create()`
    time, NOT a broker-assigned monotonic sequence number --
    PHASE4D_SSE_ARCHITECTURE_DECISION.md S6 named a sequence number as an
    alternative "for replay", but S6 also decided against implementing
    replay in this phase. A handler-side id keeps `Event` construction
    fully decoupled from whether a broker exists or how many subscribers
    it has (mirrors `correlation_id`'s own generation, which already
    happens with no broker involved) -- this is the smaller, equally
    sufficient choice for what S6 actually requires an id *for* in this
    phase: stable per-event identity for a future SSE `id:` field, not a
    global ordering key.
    """

    return uuid4().hex


@dataclass(frozen=True)
class Event:
    event: str
    version: int
    correlation_id: str
    investigation_id: int | None
    timestamp: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=_new_event_id)

    @classmethod
    def create(
        cls,
        event: str,
        correlation_id: str,
        payload: dict[str, Any],
        *,
        version: int = 1,
        investigation_id: int | None = None,
    ) -> "Event":
        return cls(
            event=event,
            version=version,
            correlation_id=correlation_id,
            investigation_id=investigation_id,
            timestamp=datetime.now(UTC).isoformat(),
            payload=payload,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventCollector:
    """In-process stand-in for the eventual SSE publisher (S8/S22)."""

    events: list[Event] = field(default_factory=list)

    def publish(self, event: Event) -> None:
        self.events.append(event)

    def as_dicts(self) -> list[dict[str, Any]]:
        return [event.to_dict() for event in self.events]
