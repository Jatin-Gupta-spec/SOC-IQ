"""
Reporting models for SOC-IQ.

These models provide a reusable representation
of a completed investigation that can be
exported in multiple formats.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class InvestigationReport:
    """
    Complete investigation report.
    """

    report_name: str

    analyzed_at: str

    status: str

    severity: str

    risk_score: int

    confidence: float

    ioc_score: int

    threat_intel_score: int

    cve_score: int

    iocs: dict[str, list[str]]

    threat_intelligence: dict[str, Any]