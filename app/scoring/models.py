"""
Data models for the SOC-IQ risk scoring engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class RiskScore:
    """
    Represents the calculated investigation risk.
    """

    score: int
    severity: str
    confidence: float

    ioc_score: int
    threat_intel_score: int
    cve_score: int

    reasons: list[str] = field(default_factory=list)