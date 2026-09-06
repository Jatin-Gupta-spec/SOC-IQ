"""
IOC detail context service for the SOC-IQ desktop application.

Assembles everything the IOC detail view needs to show for a single
selected IOC value: investigation context, risk significance, and
threat-intelligence status -- without performing any network calls
or fabricating data. This is deliberately plain Python (no Qt
dependency) so it can be unit tested directly and reused outside
the GUI layer if needed.

Also re-exports `build_investigation_threat_intel_overview()` and the
TI_STATE_* constants from `app.services.threat_intel_state` (Phase
4J-1), the investigation-level (rather than single-IOC) equivalent
used by the Investigation Summary and Threat Intelligence tab -- kept
as a re-export here, rather than a second definition, so both this
module and the application layer share one canonical TI_STATE_*
vocabulary instead of each inventing its own.

Threat-intelligence enrichment is reused as-is from
`ThreatIntelService`/`VirusTotalClient` output already stored on
`Investigation.threat_intelligence` -- this module does not call
any provider itself and does not implement a second VirusTotal
client.
"""

from __future__ import annotations

from typing import Any

from app.database.models import Investigation
from app.services.ioc_significance import (
    ioc_type_significance,
    ioc_type_title,
)

# Canonical TI-state vocabulary and investigation-level classification
# now live in app.services.threat_intel_state (Phase 4J-1), so the
# application/API layer can use them without importing app.gui. This
# module re-exports them unchanged so existing GUI imports of
# app.services.ioc_detail_context.TI_STATE_* /
# .build_investigation_threat_intel_overview keep working exactly as
# before.
from app.services.threat_intel_state import (
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    TI_STATE_UNSUPPORTED_TYPE,
    build_investigation_threat_intel_overview,
)

# All four Phase 3E IOC categories carry threat-intelligence
# enrichment: `ThreatIntelService.enrich_results()` submits SHA256
# values to `VirusTotalClient.lookup_sha256()`, IPv4 values to
# `lookup_ip()`, domains to `lookup_domain()`, and URLs to
# `lookup_url()` (see app/threat_intel/service.py and
# app/threat_intel/virustotal.py). Any category outside this set
# is honestly reported as unsupported rather than shown with an
# empty/fake threat-intelligence section -- do not narrow this back
# to SHA256-only; that was the pre-Phase-3E behavior.
_ENRICHABLE_IOC_TYPES = frozenset({"sha256", "ipv4", "domains", "urls"})


def build_ioc_detail_context(
    investigation: Investigation,
    ioc_type: str,
    value: str,
    threat_intel_by_value: dict[str, dict[str, Any]],
    api_key_configured: bool,
) -> dict[str, Any]:
    """
    Build the display context for a single selected IOC value.

    Args:
        investigation:
            The investigation the IOC belongs to.
        ioc_type:
            The raw IOC category key (e.g. "sha256", "ipv4").
        value:
            The specific IOC value selected by the analyst.
        threat_intel_by_value:
            Mapping of SHA256 hash -> enriched threat-intelligence
            record for this investigation (see
            `InvestigationWorkspacePage._threat_intel_by_value`).
        api_key_configured:
            Whether a VirusTotal API key is currently configured.
            Passed in rather than read here so this stays a pure
            function with no I/O of its own.

    Returns:
        A dictionary consumed by `IOCDetailDialog`.
    """

    return {
        "value": value,
        "ioc_type": ioc_type,
        "ioc_type_title": ioc_type_title(ioc_type),
        "significance": ioc_type_significance(ioc_type),
        "investigation": _build_investigation_context(investigation),
        "threat_intel": _build_threat_intel_context(
            investigation,
            ioc_type,
            value,
            threat_intel_by_value,
            api_key_configured,
        ),
    }


def _build_investigation_context(
    investigation: Investigation,
) -> dict[str, Any]:
    """
    Build the "which investigation does this belong to" context.
    """

    return {
        "investigation_id": investigation.investigation_id,
        "report_name": investigation.report_name,
        "analyzed_at": investigation.analyzed_at,
        "status": investigation.status,
        "severity": investigation.severity,
    }


def _build_threat_intel_context(
    investigation: Investigation,
    ioc_type: str,
    value: str,
    threat_intel_by_value: dict[str, dict[str, Any]],
    api_key_configured: bool,
) -> dict[str, Any]:
    """
    Determine the threat-intelligence state for a single IOC value
    and the record/message that goes with it.
    """

    if ioc_type not in _ENRICHABLE_IOC_TYPES:

        return {
            "state": TI_STATE_UNSUPPORTED_TYPE,
            "record": None,
            "message": (
                f"Threat-intelligence lookups for "
                f"{ioc_type_title(ioc_type)} indicators are not "
                "yet implemented in the current provider "
                "integration. SHA256, IPv4, domains, and URLs are enriched "
                "today."
            ),
        }

    if not api_key_configured:

        return {
            "state": TI_STATE_NO_API_KEY,
            "record": None,
            "message": (
                "No VirusTotal API key is configured. Add one on "
                "the Settings page to enable enrichment for this "
                "indicator."
            ),
        }

    record = threat_intel_by_value.get(value)

    if record is not None:

        return {
            "state": TI_STATE_ENRICHED,
            "record": record,
            "message": "",
        }

    coverage = (
        investigation.threat_intelligence.get("coverage", {})
        if investigation.threat_intelligence
        else {}
    )

    if coverage.get("invalid_api_key"):

        return {
            "state": TI_STATE_PROVIDER_ERROR,
            "record": None,
            "message": (
                "The configured VirusTotal API key was rejected "
                "during this investigation's threat-intelligence "
                "check, so this indicator was not enriched."
            ),
        }

    if coverage.get("rate_limited"):

        return {
            "state": TI_STATE_PROVIDER_ERROR,
            "record": None,
            "message": (
                "The VirusTotal rate limit was reached during this "
                "investigation's threat-intelligence check, so "
                "this indicator was not enriched."
            ),
        }

    status = (
        investigation.threat_intelligence.get("status")
        if investigation.threat_intelligence
        else None
    )

    if status == "partial":

        return {
            "state": TI_STATE_INCOMPLETE_CHECK,
            "record": None,
            "message": (
                "This investigation's threat-intelligence check did "
                "not complete for every indicator. This indicator's "
                "enrichment result is unavailable -- that does NOT "
                "mean it is clean, only that it was not checked."
            ),
        }

    return {
        "state": TI_STATE_NOT_ENRICHED,
        "record": None,
        "message": (
            "This indicator has no threat-intelligence record for "
            "this investigation."
        ),
    }
