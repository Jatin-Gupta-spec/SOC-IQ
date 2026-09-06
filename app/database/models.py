"""
Database models for SOC-IQ.

This module defines the data models used for
persisting investigations in the database.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(slots=True)
class Investigation:
    """
    Represents a completed SOC-IQ investigation.

    Each investigation stores the analyzed report,
    extracted IOCs, threat intelligence enrichment,
    calculated risk score, and investigation metadata.
    """

    report_name: str

    iocs: dict[str, list[str]]

    threat_intelligence: dict[str, Any]

    risk_score: int

    severity: str

    confidence: float

    ioc_score: int

    threat_intel_score: int

    cve_score: int

    analyzed_at: datetime = field(
        default_factory=lambda: datetime.now(
            UTC,
        )
    )

    status: str = "COMPLETED"

    investigation_id: int | None = None

    #: A4-P1 evidence provenance (docs/architecture/PROVENANCE.md):
    #: the SHA-256 hex digest of the exact source-report bytes this
    #: investigation was analyzed from, computed once during
    #: ingestion by `app.extractor.compute_source_provenance`.
    #: `None` means one of two honest things -- a legacy investigation
    #: persisted before A4-P1 (the hash was never calculated, not
    #: merely unrecorded), or a row this process has not yet
    #: populated -- never a fabricated/backfilled value.
    source_sha256: str | None = None

    #: The size, in bytes, of the exact source-report bytes hashed
    #: into `source_sha256`. Always set together with `source_sha256`
    #: (both `None`, or both populated) -- never independently.
    source_size_bytes: int | None = None
