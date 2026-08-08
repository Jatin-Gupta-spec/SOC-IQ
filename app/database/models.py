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
