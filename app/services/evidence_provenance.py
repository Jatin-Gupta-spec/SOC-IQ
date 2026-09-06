"""
Evidence provenance classification (A4-P1).

Canonical home of SOC-IQ's OBSERVED / ENRICHED / UNAVAILABLE evidence
model: the tiers docs/architecture/PROVENANCE.md defines to keep what
SOC-IQ *observed* in a source report distinct from what an external
threat-intelligence provider *reported*, and from what SOC-IQ *derived*
(the risk score) from both.

Deliberately plain Python with no Qt/GUI dependency (mirrors
`app.services.threat_intel_state` / `app.services.investigation_integrity`),
and deliberately does not introduce a second IOC data model: every
value here is read from the `iocs` / `threat_intelligence` /
`risk_score`/`severity` fields `app.analyzer.analyze_report` and
`app.scoring.engine.RiskScoringEngine` already produce and
`InvestigationRepository` already persists. There is exactly one
extraction path in this codebase (`app.extractor.extract_iocs`, a
single regex pass over the source report text), so every IOC value
present in `Investigation.iocs` is, by construction, OBSERVED --
directly present in the source report -- and this module records that
rather than inventing per-IOC extraction metadata this codebase's
single-extractor architecture does not otherwise track.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.database.models import Investigation

#: The IOC categories `ThreatIntelService.enrich_results()` can
#: actually enrich (see that method and
#: `app.services.threat_intel_state.ENRICHABLE_IOC_TYPES`, the
#: existing canonical definition this module reuses rather than
#: redefining). Every other `Investigation.iocs` category (`emails`,
#: `md5`, `sha1`, `cves`, `windows_file_paths`,
#: `windows_registry_keys`) is OBSERVED-only in this codebase: there
#: is no provider lookup path for them.
from app.services.threat_intel_state import ENRICHABLE_IOC_TYPES

#: `threat_intelligence["status"]` values that mean a real enrichment
#: attempt ran to completion (successfully or partially) -- as opposed
#: to the `"unavailable"` sentinel `app.analyzer.analyze_report` writes
#: itself when enrichment never ran or could not be attempted at all.
_TI_ATTEMPTED_STATUSES = frozenset({"ok", "partial", "no_indicators"})


@dataclass(frozen=True, slots=True)
class EvidenceProvenanceSummary:
    """
    A per-investigation breakdown across SOC-IQ's evidence tiers.

    observed_ioc_count:
        Total IOCs across every `Investigation.iocs` category --
        every one of them is directly present in the source report,
        by construction of this codebase's single regex extractor.

    enrichable_ioc_count:
        The subset of `observed_ioc_count` belonging to a category
        `ThreatIntelService` can enrich (`ENRICHABLE_IOC_TYPES`).

    enriched_ioc_count:
        How many of those enrichable IOCs actually received an
        external verdict, per the enrichment run's own reported
        `coverage.succeeded` -- not re-derived by counting nested
        result lists, so this always agrees with what
        `ThreatIntelService` itself reported.

    threat_intel_status / threat_intel_reason:
        The enrichment tier's own status, unchanged from
        `Investigation.threat_intelligence` (`"ok"` / `"partial"` /
        `"no_indicators"` / `"unavailable"`, with `reason` set only
        for `"unavailable"`). Exposed here rather than re-classified,
        so this summary can never disagree with the raw persisted
        payload `get_threat_intelligence` already returns unchanged.

    risk_calculated:
        Whether the DERIVED risk tier (`Investigation.risk_score`/
        `severity`) reflects a real `RiskScoringEngine` run, as
        opposed to the `"NOT_SCORED"` sentinel written when scoring
        was disabled for that analysis.
    """

    observed_ioc_count: int
    enrichable_ioc_count: int
    enriched_ioc_count: int
    threat_intel_status: str
    threat_intel_reason: str | None
    risk_calculated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_ioc_count": self.observed_ioc_count,
            "enrichable_ioc_count": self.enrichable_ioc_count,
            "enriched_ioc_count": self.enriched_ioc_count,
            "threat_intel_status": self.threat_intel_status,
            "threat_intel_reason": self.threat_intel_reason,
            "risk_calculated": self.risk_calculated,
        }


def build_evidence_provenance_summary(
    investigation: Investigation,
) -> EvidenceProvenanceSummary:
    """
    Derive an `EvidenceProvenanceSummary` from an already-loaded
    `Investigation`. Pure function: no database access, no provider
    call, no mutation.
    """

    iocs = investigation.iocs or {}

    observed_ioc_count = sum(len(values) for values in iocs.values())

    enrichable_ioc_count = sum(
        len(iocs.get(ioc_type, []))
        for ioc_type in ENRICHABLE_IOC_TYPES
    )

    threat_intelligence = investigation.threat_intelligence or {}
    threat_intel_status = threat_intelligence.get("status", "unavailable")
    threat_intel_reason = threat_intelligence.get("reason")

    enriched_ioc_count = 0

    if threat_intel_status in _TI_ATTEMPTED_STATUSES:

        coverage = threat_intelligence.get("coverage")

        if isinstance(coverage, dict):

            enriched_ioc_count = int(coverage.get("succeeded", 0))

    return EvidenceProvenanceSummary(
        observed_ioc_count=observed_ioc_count,
        enrichable_ioc_count=enrichable_ioc_count,
        enriched_ioc_count=enriched_ioc_count,
        threat_intel_status=threat_intel_status,
        threat_intel_reason=threat_intel_reason,
        risk_calculated=investigation.severity != "NOT_SCORED",
    )
