"""
Investigation integrity summary (A4-P1 evidence provenance).

Canonical home of the "can SOC-IQ explain what it did?" checklist for
a single investigation -- source identification, source hashing,
IOC extraction, threat-intelligence attempt/completion, and risk
scoring. Deliberately plain Python with no Qt/GUI dependency, mirroring
`app.services.threat_intel_state`'s own framework-independence so this
module can be imported by both `app.gui` and `app.application` without
either depending on the other.

Every field here is *derived* from state `Investigation` already
persists (`status`, `source_sha256`, `threat_intelligence["status"/
"reason"]`, `severity`) -- this module invents no new tracked state and
calls no provider. It answers the questions
docs/architecture/PROVENANCE.md's "Investigation Integrity Summary"
section lists, using exactly the same sentinel values
`app.analyzer.analyze_report` already writes for a
disabled/unavailable/not-yet-run pipeline stage (`severity ==
"NOT_SCORED"`, `threat_intelligence["status"] == "unavailable"` with a
`"reason"` of `"not_attempted"` / `"disabled"` / `"missing_api_key"` /
`"error"`).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.database.models import Investigation

#: `threat_intelligence["reason"]` values that mean the enrichment
#: stage never actually ran -- as opposed to running and then failing
#: (`"missing_api_key"` / `"error"`), which did attempt it.
_TI_NOT_ATTEMPTED_REASONS = frozenset({"not_attempted", "disabled"})

#: `threat_intelligence["status"]` values `ThreatIntelService
#: .enrich_results()` produces for a real (attempted) enrichment run
#: -- see that method's own `status` assignment. `"unavailable"` is
#: the sentinel `app.analyzer.analyze_report` writes itself and is
#: deliberately excluded here.
_TI_COMPLETED_STATUSES = frozenset({"ok", "partial", "no_indicators"})

#: The one `severity` value that is not a real
#: `RiskScoringEngine`-produced classification --
#: `app.analyzer.analyze_report`'s own "risk scoring was disabled"
#: sentinel (see `RiskScoringEngine._determine_severity`, which never
#: returns this value).
_RISK_NOT_SCORED_SENTINEL = "NOT_SCORED"


@dataclass(frozen=True, slots=True)
class InvestigationIntegritySummary:
    """
    Answers, for one investigation, the checklist A4-P1's design
    calls the "Investigation Integrity Summary":

        Source report identified?
        Source hash available?
        Analysis completed?
        IOC extraction completed?
        Threat intelligence attempted?
        Threat intelligence complete?
        Risk calculation completed?

    Deliberately excludes "Export generated?" -- export is a
    per-request action this domain object has no record of, and
    fabricating a stored answer for it would violate this module's own
    "derived, never invented" rule. That question belongs to whatever
    layer actually knows an export happened (out of scope for A4-P1;
    see docs/architecture/PROVENANCE.md).
    """

    source_identified: bool
    source_hash_available: bool
    analysis_completed: bool
    ioc_extraction_completed: bool
    threat_intel_attempted: bool
    threat_intel_complete: bool
    risk_calculation_completed: bool

    def to_dict(self) -> dict[str, bool]:
        return {
            "source_identified": self.source_identified,
            "source_hash_available": self.source_hash_available,
            "analysis_completed": self.analysis_completed,
            "ioc_extraction_completed": self.ioc_extraction_completed,
            "threat_intel_attempted": self.threat_intel_attempted,
            "threat_intel_complete": self.threat_intel_complete,
            "risk_calculation_completed": self.risk_calculation_completed,
        }


def build_integrity_summary(
    investigation: Investigation,
) -> InvestigationIntegritySummary:
    """
    Derive an `InvestigationIntegritySummary` from an already-loaded
    `Investigation`. Pure function: no database access, no provider
    call, no mutation.
    """

    threat_intelligence = investigation.threat_intelligence or {}
    ti_status = threat_intelligence.get("status")
    ti_reason = threat_intelligence.get("reason")

    threat_intel_attempted = not (
        ti_status == "unavailable" and ti_reason in _TI_NOT_ATTEMPTED_REASONS
    )
    threat_intel_complete = ti_status in _TI_COMPLETED_STATUSES

    return InvestigationIntegritySummary(
        source_identified=bool(investigation.report_name),
        source_hash_available=investigation.source_sha256 is not None,
        analysis_completed=investigation.status == "COMPLETED",
        # IOC extraction is a mandatory, always-run pipeline stage in
        # every persisted `Investigation` -- even when
        # `options["extract_iocs"]` is `False`, `analyze_report`
        # still writes the same-shaped (honestly empty) result rather
        # than skipping persistence entirely (see
        # `app.analyzer._resolve_options`'s docstring). `iocs` being
        # present at all is therefore the correct, honest signal here.
        ioc_extraction_completed=investigation.iocs is not None,
        threat_intel_attempted=threat_intel_attempted,
        threat_intel_complete=threat_intel_complete,
        risk_calculation_completed=investigation.severity != _RISK_NOT_SCORED_SENTINEL,
    )
