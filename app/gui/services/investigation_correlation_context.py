"""
Correlation display context for the SOC-IQ desktop application.

Converts a `CorrelationReport` (app/services/correlation_service.py)
into row data and copy the Correlations view can render directly,
the same way app/services/ioc_detail_context.py separates
domain state from display copy for the IOC detail flow. This module
performs no correlation itself -- `CorrelationService` is the only
place that decides what is related to what.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ioc_significance import ioc_type_title
from app.services.correlation_models import (
    RELATIONSHIP_DOMAIN_URL_HOST,
    RELATIONSHIP_DUPLICATE_IOC,
    RELATIONSHIP_THREAT_INTEL_LINK,
    CorrelationReport,
)

# Display labels for each relationship type. Kept here rather than
# on the relationship constants themselves so the domain layer
# (app/services/correlation_models.py) has no display-copy
# dependency.
_RELATIONSHIP_LABELS: dict[str, str] = {
    RELATIONSHIP_DUPLICATE_IOC: "Same Normalized IOC",
    RELATIONSHIP_DOMAIN_URL_HOST: "Same Domain",
    RELATIONSHIP_THREAT_INTEL_LINK: "Threat Intelligence Association",
}

_DEFAULT_RELATIONSHIP_LABEL = "Related"


def relationship_label(relationship_type: str) -> str:
    """
    Return the display label for a relationship type, falling back
    to a generic label for any type this view doesn't otherwise
    know how to describe.
    """

    return _RELATIONSHIP_LABELS.get(
        relationship_type,
        _DEFAULT_RELATIONSHIP_LABEL,
    )


@dataclass(frozen=True, slots=True)
class CorrelationRow:
    """
    One display-ready row for the Correlations table:
    Primary IOC | Relationship | Related Evidence | Reason.
    """

    primary_type_title: str
    primary_value: str
    relationship_label: str
    related_type_title: str
    related_value: str
    reason: str


def build_correlation_rows(report: CorrelationReport) -> list[CorrelationRow]:
    """
    Convert a `CorrelationReport`'s results into display-ready rows,
    preserving the report's existing (already-deterministic)
    ordering.
    """

    return [
        CorrelationRow(
            primary_type_title=ioc_type_title(result.primary.ioc_type),
            primary_value=result.primary.value,
            relationship_label=relationship_label(result.relationship_type),
            related_type_title=ioc_type_title(result.related.ioc_type),
            related_value=result.related.value,
            reason=result.reason,
        )
        for result in report.results
    ]


def build_correlation_summary_text(report: CorrelationReport) -> str:
    """
    Build a one-line summary of correlation coverage for this
    investigation, e.g. for display above the correlations table.
    """

    summary = report.summary

    if summary.total_evidence_count == 0:
        return "No evidence has been extracted for this investigation."

    if summary.relationship_count == 0:
        return (
            f"{summary.total_evidence_count} evidence item(s) in this "
            "investigation. No supported deterministic relationships "
            "were identified from the available evidence."
        )

    return (
        f"{summary.relationship_count} relationship(s) found across "
        f"{summary.correlated_evidence_count} of "
        f"{summary.total_evidence_count} evidence item(s) in this "
        "investigation."
    )
