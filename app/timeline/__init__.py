"""
Investigation Timeline foundation for SOC-IQ (Phase A4-P2-P3, Part 1/6).

This package is the persistence-and-domain foundation for the
investigation timeline. It defines what a timeline event *is*
(app.timeline.domain), and how it is stored and retrieved
(app.timeline.repository).

It deliberately does NOT wire any of SOC-IQ's existing pipelines
(analysis, IOC extraction, threat intel, reporting) to emit timeline
events yet -- that is Part 2's job. Nothing in this package is
imported by app.analyzer, app.extractor, app.reporting, or
app.threat_intel as of this checkpoint.

See docs/architecture/20-investigation-timeline-architecture.md for
the full design rationale.
"""

from __future__ import annotations

from app.timeline.domain import (
    MAX_METADATA_BYTES,
    TimelineEvent,
    TimelineEventType,
    TimelineMetadataError,
    TimelineValidationError,
)
from app.timeline.repository import TimelineRepository

__all__ = [
    "MAX_METADATA_BYTES",
    "TimelineEvent",
    "TimelineEventType",
    "TimelineMetadataError",
    "TimelineRepository",
    "TimelineValidationError",
]
