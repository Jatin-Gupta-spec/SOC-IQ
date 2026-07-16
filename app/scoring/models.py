"""
Data models for the SOC-IQ risk scoring engine.

This module defines the data structures used
to represent calculated investigation risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RiskScore:
    """
    Represents the calculated risk assessment
    for a SOC-IQ investigation.

    Attributes:
        score:
            Final normalized risk score.

        severity:
            Risk classification
            (LOW, MEDIUM, HIGH, CRITICAL).

        confidence:
            Confidence level of the calculated
            score between 0.0 and 1.0.

        ioc_score:
            Score contributed by extracted IOCs.

        threat_intel_score:
            Score contributed by threat
            intelligence enrichment.

        cve_score:
            Additional score contributed by
            discovered CVEs.

        reasons:
            Human-readable explanation of how
            the final score was calculated.
    """

    score: int

    severity: str

    confidence: float

    ioc_score: int

    threat_intel_score: int

    cve_score: int

    reasons: list[str] = field(
        default_factory=list,
    )