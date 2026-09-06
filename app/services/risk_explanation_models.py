"""
Risk explanation domain models for SOC-IQ.

These are plain, GUI-independent data types produced by
`RiskExplanationService` (app/services/risk_explanation_service.py),
the same way `app/services/correlation_models.py` separates the
correlation domain's data shapes from `CorrelationService` and from
the GUI presentation layer.

PHASE3C-1 scope: this module explains an *existing* risk
assessment. It never computes a new score or severity -- every
score/severity/confidence value here is read directly from the
`Investigation` the caller supplies, never recalculated (see
`RiskExplanationService`).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IocCategoryContribution:
    """
    One IOC category's role in the existing risk assessment.

    `points` is the category's share of `RiskExplanation.ioc_score`,
    computed as `count * weight` using
    `RiskScoringEngine.IOC_WEIGHTS` -- the same public weight table
    `_calculate_ioc_score()` itself sums over (see
    `app/services/ioc_significance.py`, which already reuses this
    table for the "Risk Significance" column). This is a
    decomposition of an already-persisted number, not a new
    calculation -- `RiskExplanationService` cross-checks that every
    category's `points` sums to the investigation's stored
    `ioc_score` before treating any of them as reliable (see
    `RiskExplanation.ioc_breakdown_verified`).
    """

    ioc_type: str
    ioc_type_title: str
    count: int
    weight: int
    significance: str
    points: int


@dataclass(frozen=True, slots=True)
class RiskExplanation:
    """
    Full explanation of one investigation's existing risk
    assessment.

    Every `score` / `severity` / `confidence` / `*_score` field
    below is copied as-is from the `Investigation` passed to
    `RiskExplanationService.explain()` -- this result can never
    disagree with the existing assessment because it never
    recalculates it.

    Attributes:
        investigation_id, report_name:
            Identify which investigation this explains.
        score, severity, confidence:
            The investigation's existing, authoritative risk
            assessment.
        ioc_score, threat_intel_score, cve_score:
            The existing assessment's three persisted component
            scores (`RiskScoringEngine.calculate()` output, stored
            on `Investigation`).
        ioc_categories:
            Per-category breakdown of `ioc_score`. Only meaningful
            when `ioc_breakdown_verified` is True (see that field).
        ioc_breakdown_verified:
            Whether `ioc_categories`' points sum exactly to
            `ioc_score`. When False, the per-category `points`
            values are NOT to be treated as reliable evidence and
            the narrative avoids stating them -- see PHASE3C-1
            section 8 ("Important Claim Rule").
        threat_intel_state / threat_intel_message /
        threat_intel_short_label / threat_intel_requested /
        threat_intel_succeeded:
            The investigation's existing threat-intelligence
            coverage state, straight from
            `build_investigation_threat_intel_overview()` -- not
            recomputed, not a new provider call.
        threat_intel_malicious_hash_count /
        threat_intel_suspicious_hash_count:
            Counts of hashes the existing enrichment already marked
            "Malicious" / "Suspicious", read directly from
            `Investigation.threat_intelligence["hashes"]`.
        correlation_evaluated:
            Whether a `CorrelationReport` was supplied to
            `explain()` at all. False means correlation context is
            simply absent from this explanation, not that zero
            relationships were checked for.
        correlation_relationship_count / correlation_summary:
            The existing Phase 3B correlation result for this
            investigation, only present when
            `correlation_evaluated` is True.
        engine_reasons:
            Any `reasons` the scoring engine itself attached to the
            investigation, if the caller's `Investigation` instance
            happens to carry them (see `RiskExplanationService`
            docstring -- this is usually empty because `reasons` is
            not part of the persisted `Investigation` schema).
        narrative:
            Human-readable sentences summarizing the explanation.
            Every sentence here is grounded in one of the fields
            above.
        warnings:
            Anything about the explanation itself the caller should
            know (e.g. an unverified IOC breakdown, an incomplete
            threat-intelligence check).
    """

    investigation_id: int | None
    report_name: str

    score: int
    severity: str
    confidence: float

    ioc_score: int
    threat_intel_score: int
    cve_score: int

    ioc_categories: list[IocCategoryContribution] = field(
        default_factory=list
    )
    ioc_breakdown_verified: bool = False

    threat_intel_state: str = ""
    threat_intel_message: str = ""
    threat_intel_short_label: str = ""
    threat_intel_requested: int = 0
    threat_intel_succeeded: int = 0
    threat_intel_malicious_hash_count: int = 0
    threat_intel_suspicious_hash_count: int = 0

    correlation_evaluated: bool = False
    correlation_relationship_count: int = 0
    correlation_summary: str = ""

    engine_reasons: list[str] = field(default_factory=list)

    narrative: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
