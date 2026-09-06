"""
Evidence correlation domain models for SOC-IQ.

These are plain, GUI-independent data types shared between
`CorrelationService` (app/services/correlation_service.py) and the
GUI presentation layer (app/gui). Kept here rather than inside a
GUI widget module so the correlation domain logic never has to
import PySide6 -- see PHASE3_PART3B scope: "Do not import PySide6
into the correlation/domain layer."

Relationship type constants are plain strings (not an enum) to
match the rest of the codebase's TI_STATE_*-style vocabulary (see
app/services/ioc_detail_context.py).
"""

from __future__ import annotations

from dataclasses import dataclass, field

# ==========================================================
# Relationship Types
# ==========================================================

# Two raw IOC values within the same investigation that resolve to
# the same normalized identity (e.g. "Example.com" and
# "example.com"). Priority 1 per PHASE3_PART3B section 13: exact
# normalized IOC identity.
RELATIONSHIP_DUPLICATE_IOC = "duplicate_ioc"

# A domain value and a URL value where the URL's host resolves to
# that domain (exact host match or subdomain). Priority 2: a
# cross-category association the existing extracted data directly
# supports (PHASE3_PART3B section 8).
RELATIONSHIP_DOMAIN_URL_HOST = "domain_url_host"

# A SHA256 IOC and its own enrichment record from the investigation's
# existing `threat_intelligence` data. Priority 4: existing
# threat-intelligence association.
RELATIONSHIP_THREAT_INTEL_LINK = "threat_intel_link"

# Display order for the relationship types above, matching
# PHASE3_PART3B section 13's priority list. Lower is higher
# priority. Used to sort `CorrelationReport.results` so the most
# significant relationships surface first.
RELATIONSHIP_PRIORITY: dict[str, int] = {
    RELATIONSHIP_DUPLICATE_IOC: 1,
    RELATIONSHIP_DOMAIN_URL_HOST: 2,
    RELATIONSHIP_THREAT_INTEL_LINK: 4,
}

# Human-readable labels and reason templates are intentionally kept
# out of this module -- they belong to the presentation layer (see
# app/gui/services/investigation_correlation_context.py), matching
# how ioc_detail_context.py separates domain state from display
# copy for the IOC detail flow.


@dataclass(frozen=True, slots=True)
class CorrelatedEvidence:
    """
    One side of a correlation: a single piece of evidence
    (an extracted IOC, or an enrichment record) identified by its
    category and value.

    `normalized_value` is used only for comparison during
    correlation -- it is never written back to the investigation's
    stored IOCs (see PHASE3_PART3B section 9: "Do NOT modify the
    original stored IOC").
    """

    ioc_type: str
    value: str
    normalized_value: str


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    """
    A single deterministic relationship between two pieces of
    evidence already present in an investigation.

    `reason` is a full sentence, safe to show as-is, explaining why
    the two are related (see PHASE3_PART3B section 15: "Every
    displayed correlation should have an understandable reason.").
    """

    relationship_type: str
    primary: CorrelatedEvidence
    related: CorrelatedEvidence
    reason: str

    @property
    def priority(self) -> int:
        """
        Sort priority for this result's relationship type, per
        `RELATIONSHIP_PRIORITY`. Unknown types sort last.
        """

        return RELATIONSHIP_PRIORITY.get(
            self.relationship_type,
            max(RELATIONSHIP_PRIORITY.values()) + 1,
        )


@dataclass(frozen=True, slots=True)
class CorrelationSummary:
    """
    Investigation-level correlation counts.

    `shared_investigation_evidence_count` answers PHASE3_PART3B
    section 8's "shared investigation" relationship type and
    section 13 priority 3 ("existing investigation association")
    as a single count rather than as pairwise results -- every
    piece of evidence in an investigation is trivially related to
    every other piece of evidence in the same investigation by
    virtue of shared membership, so representing this pairwise
    would mean O(n^2) results that add no analytical value beyond
    what the IOC Summary already shows. The count is surfaced here
    instead so the correlation view can still state it explicitly.
    """

    total_evidence_count: int
    correlated_evidence_count: int
    relationship_count: int
    shared_investigation_evidence_count: int


@dataclass(frozen=True, slots=True)
class CorrelationReport:
    """
    Full correlation output for one investigation.

    `results` is already sorted by relationship priority, then by
    primary/related value, so display code does not need to
    re-sort (see PHASE3_PART3B section 23: "Ordering -- Results
    should have deterministic ordering.").
    """

    results: list[CorrelationResult] = field(default_factory=list)
    summary: CorrelationSummary = field(
        default_factory=lambda: CorrelationSummary(0, 0, 0, 0)
    )
