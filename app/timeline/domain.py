"""
Investigation Timeline domain model.

Defines what a persisted timeline event *is*: its identity, the
controlled vocabulary of what it may say happened, and the
validation rules that keep it an "evidence-honest" application
record rather than a fabricated security conclusion or an
unbounded metadata dump.

Relationship to app.application.events.Event
----------------------------------------------
SOC-IQ already has an event model (`app.application.events.Event`):
an ephemeral, in-process pub/sub envelope for the future SSE stream
(docs/contracts/event-model.md, PHASE4D_SSE_ARCHITECTURE_DECISION.md).
This module does NOT replace or compete with it -- it is a
*persisted history* of application facts, not a live transport.

Where the two overlap, this module reuses `Event`'s established
conventions rather than inventing parallel ones:

  * event identity is a plain `uuid4().hex` string, generated at
    construction time -- same strategy as `Event._new_event_id`.
  * timestamps are UTC, generated via `datetime.now(UTC)`.
  * event *names* follow the `domain.action` convention fixed by
    docs/contracts/event-model.md (`analysis.*`, `investigation.*`,
    `ti.enrichment.*`, ...), including reusing that document's exact
    name (`ti.enrichment.completed`) where our vocabulary overlaps
    it, rather than a second, differently-spelled name for the same
    real-world occurrence -- the exact duplication that document
    warns against.

`investigation_id` here is `int`, matching
`app.database.models.Investigation.investigation_id` (the real,
existing investigation identity -- an autoincrement SQLite integer
primary key), NOT a new `CaseId`/`TimelineInvestigationId` type and
NOT the `str` `"inv-1029"`-style id shown as illustrative in the
event-model.md envelope example (no such string id exists anywhere
in the current codebase).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from app.exceptions import ValidationError

# ==========================================================
# Identity
# ==========================================================


def _new_timeline_event_id() -> str:
    """Same strategy as app.application.events.Event._new_event_id:
    a plain uuid4 hex string, generated at construction time. Kept
    as its own function (rather than importing the private helper)
    so this module does not depend on another module's private
    name; the two are intentionally identical in behavior.
    """

    return uuid4().hex


# ==========================================================
# Errors
# ==========================================================
#
# Timeline domain failures are ValidationError (app.exceptions),
# not a new base exception -- per the project's existing
# convention (see app.threat_intel.exceptions, app.application.errors)
# of adding a *specific* subclass under an *existing* SOCIQError
# branch rather than a parallel taxonomy.


class TimelineValidationError(ValidationError):
    """
    Raised when a TimelineEvent cannot be constructed because one
    of its fields fails domain validation (unknown event type,
    non-UTC/naive timestamp, missing summary, invalid investigation
    id, ...).
    """


class TimelineMetadataError(TimelineValidationError):
    """
    Raised specifically for metadata problems: not JSON-serializable,
    over the size bound, or containing a secret-shaped key.

    A subclass of TimelineValidationError (not a sibling) so a
    caller that only cares "was this event invalid" can catch the
    parent, while a caller that wants to react specifically to
    metadata problems (e.g. surface a clearer UI message) can catch
    this one.
    """


# ==========================================================
# Controlled event vocabulary
# ==========================================================


class TimelineEventType(str, Enum):
    """
    The complete, deliberately small set of facts the investigation
    timeline is allowed to record in this checkpoint.

    Every member describes something SOC-IQ itself did or observed
    about its own pipeline -- never an unsupported claim about
    attacker/malware behavior (see module docstring and
    docs/architecture/20-investigation-timeline-architecture.md
    S2 "Product Principle"). Do not add a member here unless the
    existing system actually establishes that fact; do not add
    speculative future events.

    Naming follows docs/contracts/event-model.md's `domain.action`
    convention. `TI_ENRICHMENT_COMPLETED`'s value is the exact
    string (`ti.enrichment.completed`) that document already
    reserves for this occurrence -- reused, not respelled.
    """

    INVESTIGATION_CREATED = "investigation.created"
    REPORT_IMPORTED = "report.imported"
    ANALYSIS_STARTED = "analysis.started"
    ANALYSIS_COMPLETED = "analysis.completed"
    IOC_EXTRACTION_COMPLETED = "ioc_extraction.completed"
    TI_ENRICHMENT_COMPLETED = "ti.enrichment.completed"
    RISK_CALCULATED = "risk.calculated"
    CORRELATION_COMPLETED = "correlation.completed"
    REPORT_EXPORTED = "report.exported"

    @classmethod
    def _missing_(cls, value: object) -> None:
        # Make an unknown/typo'd event type a clear
        # TimelineValidationError instead of Python's generic
        # `ValueError: <x> is not a valid TimelineEventType`, so
        # callers that already catch domain validation errors
        # don't also need to catch bare ValueError here.
        raise TimelineValidationError(
            f"Unknown timeline event type: {value!r}. "
            f"Must be one of: "
            f"{', '.join(member.value for member in cls)}."
        )


#: What each event type actually asserts. Kept beside the vocabulary
#: (rather than only in documentation) so the semantics travel with
#: the code and cannot silently drift from what is documented.
TIMELINE_EVENT_SEMANTICS: dict[TimelineEventType, str] = {
    TimelineEventType.INVESTIGATION_CREATED: (
        "A new SOC-IQ investigation record was created."
    ),
    TimelineEventType.REPORT_IMPORTED: (
        "A source report's bytes were read and accepted for analysis."
    ),
    TimelineEventType.ANALYSIS_STARTED: (
        "SOC-IQ's analysis pipeline began processing a report."
    ),
    TimelineEventType.ANALYSIS_COMPLETED: (
        "SOC-IQ's analysis pipeline completed successfully. This "
        "does NOT mean the analyzed malware 'completed execution' "
        "or that any attacker action occurred -- only that SOC-IQ's "
        "own analysis run finished."
    ),
    TimelineEventType.IOC_EXTRACTION_COMPLETED: (
        "SOC-IQ's IOC extractor finished parsing indicators out of "
        "the report. Does not assert those indicators are malicious."
    ),
    TimelineEventType.TI_ENRICHMENT_COMPLETED: (
        "SOC-IQ's threat-intelligence enrichment step finished "
        "querying configured providers for the extracted IOCs."
    ),
    TimelineEventType.RISK_CALCULATED: (
        "SOC-IQ's scoring engine computed a risk score for the "
        "investigation from its own extracted/enriched data."
    ),
    TimelineEventType.CORRELATION_COMPLETED: (
        "SOC-IQ's correlation service finished deriving deterministic "
        "relationships between this investigation's own extracted "
        "and enriched evidence (e.g. duplicate indicators, related "
        "threat-intelligence records). This is correlation within "
        "this one investigation's own evidence -- it does not compare "
        "against, or claim any relationship with, any other "
        "investigation SOC-IQ holds."
    ),
    TimelineEventType.REPORT_EXPORTED: (
        "SOC-IQ exported an investigation report to a file "
        "(PDF/HTML/Markdown/JSON)."
    ),
}


# ==========================================================
# Metadata policy
# ==========================================================

#: A timeline summary is a one-line, human-readable label (e.g.
#: "Analysis completed for report.exe"), not a place to paste report
#: bodies or stack traces. 512 characters is generous for that
#: purpose while keeping a single append() call bounded -- mirrors
#: MAX_METADATA_BYTES below in spirit (a small, deliberately-chosen
#: bound documented at its point of use, not an arbitrary default).
MAX_SUMMARY_LENGTH = 512

#: Bounded, JSON-compatible structured metadata only -- not a
#: document store. 4 KiB is generous for the kind of payload this
#: vocabulary actually needs (a handful of counts/ids/strings, e.g.
#: {"ioc_count": 31}), while still being small enough that timeline
#: metadata cannot become a dumping ground for entire analysis
#: objects (Investigation.iocs/threat_intelligence already have
#: their own dedicated, unbounded columns -- see
#: app/database/models.py). No existing project-wide limit governs
#: this, so this bound is established fresh for this feature and
#: documented here as the single source of truth for it.
MAX_METADATA_BYTES = 4096

#: Metadata key *names* that indicate a caller is about to leak a
#: credential into a permanent, append-only history table. This is
#: a name-based guard, not a secret scanner (SOC-IQ's actual secret
#: storage is app.secrets.RustKeystoreHandoffSecretStore, and no
#: generic value-scanning mechanism exists in the project to reuse
#: for this) -- deliberately conservative substring matching so
#: "api_key", "apiKey", "access_token", "db_password", etc. are all
#: caught.
_FORBIDDEN_METADATA_KEY_SUBSTRINGS = (
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "passwd",
    "secret",
    "private_key",
    "privatekey",
    "credential",
)


def _check_metadata_keys_for_secrets(metadata: dict[str, Any]) -> None:
    for key in metadata:
        lowered = key.lower().replace("-", "_").replace(" ", "_")
        for forbidden in _FORBIDDEN_METADATA_KEY_SUBSTRINGS:
            if forbidden in lowered:
                raise TimelineMetadataError(
                    f"Timeline metadata key {key!r} looks like it "
                    "carries a secret/credential and is not allowed "
                    "in a permanent timeline record."
                )


def _validate_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    if metadata is None:
        return {}

    if not isinstance(metadata, dict):
        raise TimelineMetadataError(
            "Timeline metadata must be a dict, "
            f"got {type(metadata).__name__}."
        )

    _check_metadata_keys_for_secrets(metadata)

    try:
        encoded = json.dumps(metadata, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise TimelineMetadataError(
            "Timeline metadata must be JSON-serializable "
            "(plain str/int/float/bool/None/dict/list values only)."
        ) from exc

    size = len(encoded.encode("utf-8"))
    if size > MAX_METADATA_BYTES:
        raise TimelineMetadataError(
            f"Timeline metadata is {size} bytes, which exceeds the "
            f"{MAX_METADATA_BYTES}-byte bound. Timeline metadata is "
            "for small structured facts (e.g. {'ioc_count': 31}), "
            "not entire analysis objects."
        )

    # Round-trip through JSON so the stored value is exactly what
    # was validated (e.g. a tuple passed in becomes the list it will
    # actually be retrieved as), rather than validating one object
    # and persisting a subtly different one.
    return json.loads(encoded)


# ==========================================================
# TimelineEvent
# ==========================================================


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """
    A single, immutable fact in an investigation's history.

    Timeline events are append-only historical records (see
    app.timeline.repository.TimelineRepository docstring): once
    constructed and persisted, a TimelineEvent is never mutated or
    deleted except as a consequence of its parent investigation
    being deleted (see the FOREIGN KEY / ON DELETE CASCADE clause
    in app/database/migrations/0003_add_timeline_events.sql).
    """

    investigation_id: int
    event_type: TimelineEventType
    summary: str
    source: str = "system"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(UTC),
    )
    event_id: str = field(default_factory=_new_timeline_event_id)

    def __post_init__(self) -> None:
        if not isinstance(self.investigation_id, int) or isinstance(
            self.investigation_id, bool
        ):
            raise TimelineValidationError(
                "TimelineEvent.investigation_id must be an int "
                f"(got {self.investigation_id!r})."
            )

        if self.investigation_id <= 0:
            raise TimelineValidationError(
                "TimelineEvent.investigation_id must be a positive "
                f"investigation id (got {self.investigation_id!r})."
            )

        if not isinstance(self.event_type, TimelineEventType):
            # str values are coerced via TimelineEventType(value);
            # TimelineEventType._missing_ raises TimelineValidationError
            # for anything not in the controlled vocabulary.
            object.__setattr__(
                self,
                "event_type",
                TimelineEventType(self.event_type),
            )

        if not self.summary or not self.summary.strip():
            raise TimelineValidationError(
                "TimelineEvent.summary must be a non-empty string."
            )

        if len(self.summary) > MAX_SUMMARY_LENGTH:
            raise TimelineValidationError(
                f"TimelineEvent.summary is {len(self.summary)} "
                f"characters, which exceeds the {MAX_SUMMARY_LENGTH}"
                "-character bound. A timeline summary is a short "
                "human-readable label, not a place to store report "
                "bodies or long text."
            )

        if not self.source or not self.source.strip():
            raise TimelineValidationError(
                "TimelineEvent.source must be a non-empty string."
            )

        if not isinstance(self.timestamp, datetime):
            raise TimelineValidationError(
                "TimelineEvent.timestamp must be a datetime "
                f"(got {type(self.timestamp).__name__})."
            )

        if self.timestamp.tzinfo is None:
            raise TimelineValidationError(
                "TimelineEvent.timestamp must be timezone-aware "
                "(UTC) -- naive datetimes are ambiguous and are "
                "rejected rather than silently assumed to be UTC."
            )

        object.__setattr__(
            self,
            "metadata",
            _validate_metadata(self.metadata),
        )

    @property
    def semantics(self) -> str:
        """Human-readable meaning of this event's type -- see
        TIMELINE_EVENT_SEMANTICS."""

        return TIMELINE_EVENT_SEMANTICS[self.event_type]
