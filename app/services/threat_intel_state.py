"""
Threat-intelligence state classification.

Canonical home of the TI_STATE_* vocabulary and the investigation-level
threat-intelligence classification logic. This module is deliberately
plain Python with no Qt/GUI dependency of any kind, so it can be
imported by both the Qt desktop GUI (`app.gui`) and the application/API
layer (`app.application`) without either one depending on the other.

Moved here (Phase 4J-1) from `app.services.ioc_detail_context`,
where it originated as GUI-adjacent code that was in fact already
framework-independent. `app.services.ioc_detail_context` continues
to re-export the same symbols from here unchanged, so existing GUI
imports are unaffected -- see that module's docstring.

Threat-intelligence enrichment is reused as-is from
`ThreatIntelService`/`VirusTotalClient` output already stored on
`Investigation.threat_intelligence` -- this module does not call any
provider itself and does not implement a second VirusTotal client.
"""

from __future__ import annotations

from typing import Any

from app.database.models import Investigation

# Threat-intelligence states the IOC detail view (and, from Phase 4J
# onward, the API layer) can be in. Kept as plain strings (not an
# enum) to match the rest of the codebase's style (e.g.
# `coverage["status"]` in ThreatIntelService).
TI_STATE_ENRICHED = "enriched"
TI_STATE_NOT_ENRICHED = "not_enriched"
TI_STATE_NO_API_KEY = "no_api_key"
TI_STATE_PROVIDER_ERROR = "provider_error"
TI_STATE_INCOMPLETE_CHECK = "incomplete_check"
TI_STATE_UNSUPPORTED_TYPE = "unsupported_type"

# The IOC categories `ThreatIntelService.enrich_results()` actually
# enriches (see that method and `VirusTotalProvider._SUPPORTED_IOC_TYPES`).
# Keyed on the same `ioc_type` strings `Investigation.iocs` uses. This is
# the canonical copy (Phase 4J-2); `app.services.ioc_detail_context`
# re-exports it below rather than keeping its own separate
# `_ENRICHABLE_IOC_TYPES` copy, so there is exactly one definition.
ENRICHABLE_IOC_TYPES = frozenset({"sha256", "ipv4", "domains", "urls"})

# For each enrichable `ioc_type`, the (list-key, record-key) pair used to
# read that category's enriched records back off a persisted
# `Investigation.threat_intelligence` dict -- see
# `ThreatIntelService.enrich_results()`'s return shape (`"hashes"` /
# `"ips"` / `"domains"` / `"urls"`, each a list of dicts keyed by
# `"sha256"` / `"ip"` / `"domain"` / `"url"` respectively) and the
# identical mapping already inlined at
# `InvestigationWorkspacePage.load_investigation`.
_ENRICHED_RECORD_LOCATION_BY_IOC_TYPE: dict[str, tuple[str, str]] = {
    "sha256": ("hashes", "sha256"),
    "ipv4": ("ips", "ip"),
    "domains": ("domains", "domain"),
    "urls": ("urls", "url"),
}


def build_threat_intel_by_value(
    investigation: Investigation,
) -> dict[str, dict[str, Any]]:
    """
    Build a `value -> enriched record` map from an investigation's
    persisted `threat_intelligence` payload, across all enrichable IOC
    categories.

    Pure re-read of already-persisted data (no I/O, no provider call) --
    the same lookup `InvestigationWorkspacePage.load_investigation`
    performs inline for the GUI's IOC detail view, factored out here so
    the application layer can reuse it without duplicating the
    list-key/record-key mapping.
    """

    threat_intelligence = investigation.threat_intelligence or {}

    by_value: dict[str, dict[str, Any]] = {}

    for list_key, record_key in _ENRICHED_RECORD_LOCATION_BY_IOC_TYPE.values():
        for record in threat_intelligence.get(list_key, []) or []:
            value = record.get(record_key)
            if value:
                by_value[value] = record

    return by_value


def classify_indicator_ti_state(
    investigation: Investigation,
    ioc_type: str,
    value: str,
    threat_intel_by_value: dict[str, dict[str, Any]],
    api_key_configured: bool,
) -> str:
    """
    Determine the TI_STATE_* classification for a single indicator
    value.

    Mirrors the decision tree
    `app.services.ioc_detail_context._build_threat_intel_context`
    already uses for the IOC detail dialog (type support, then API-key
    configuration, then an enriched record's presence, then
    invalid-key/rate-limit coverage flags, then a "partial" check
    status, else not-enriched) -- reusing the same domain data those
    branches already reused with no interpretation invented on top --
    but returns only the `state`, since the caller-facing `message`
    text there is presentation copy for the desktop GUI dialog, not
    part of this classification.
    """

    if ioc_type not in ENRICHABLE_IOC_TYPES:
        return TI_STATE_UNSUPPORTED_TYPE

    if not api_key_configured:
        return TI_STATE_NO_API_KEY

    if threat_intel_by_value.get(value) is not None:
        return TI_STATE_ENRICHED

    coverage = (
        investigation.threat_intelligence.get("coverage", {})
        if investigation.threat_intelligence
        else {}
    ) or {}

    if coverage.get("invalid_api_key"):
        return TI_STATE_PROVIDER_ERROR

    if coverage.get("rate_limited"):
        return TI_STATE_PROVIDER_ERROR

    status = (
        investigation.threat_intelligence.get("status")
        if investigation.threat_intelligence
        else None
    )

    if status == "partial":
        return TI_STATE_INCOMPLETE_CHECK

    return TI_STATE_NOT_ENRICHED


def build_investigation_indicator_states(
    investigation: Investigation,
    api_key_configured: bool,
) -> dict[str, dict[str, str]]:
    """
    Build the per-indicator TI_STATE_* projection for every indicator
    already persisted on `investigation.iocs`, grouped by `ioc_type` to
    match that field's own shape (and to avoid collapsing two different
    categories' values into one flat namespace if they were ever to
    collide).

    Deterministic and side-effect-free: reads only
    `investigation.iocs` and `investigation.threat_intelligence`
    (already loaded on the domain object), performs no provider call,
    and fabricates nothing -- an indicator with no persisted enrichment
    information is classified as `TI_STATE_NOT_ENRICHED`, never guessed
    at.
    """

    iocs = investigation.iocs or {}

    threat_intel_by_value = build_threat_intel_by_value(investigation)

    states: dict[str, dict[str, str]] = {}

    for ioc_type, values in iocs.items():
        states[ioc_type] = {
            value: classify_indicator_ti_state(
                investigation,
                ioc_type,
                value,
                threat_intel_by_value,
                api_key_configured,
            )
            for value in values or []
        }

    return states


def build_investigation_threat_intel_overview(
    investigation: Investigation,
    api_key_configured: bool,
) -> dict[str, Any]:
    """
    Build an investigation-level summary of threat-intelligence
    coverage, for display in the Investigation Summary and the
    Threat Intelligence tab.

    This answers "what is known about this investigation, overall"
    -- as distinct from
    `app.services.ioc_detail_context.build_ioc_detail_context()`,
    which answers the same question for one specific IOC value. Both
    read the same underlying `ThreatIntelService` output
    (`Investigation.threat_intelligence`) and share the same
    TI_STATE_* vocabulary; neither performs a network call or
    fabricates a result.

    Args:
        investigation:
            The investigation to summarize.
        api_key_configured:
            Whether a VirusTotal API key is currently configured.
            Passed in rather than read here so this stays a pure
            function with no I/O of its own.

    Returns:
        A dict with:
          - "state": one of the TI_STATE_* constants.
          - "message": a full sentence describing the state, safe
            to show as-is (e.g. in an empty state or tooltip).
          - "short_label": a compact label for tight spaces (e.g.
            a KeyValueRow value).
          - "requested" / "succeeded": the underlying counts, for
            callers that want the raw numbers.
    """

    threat_intelligence = investigation.threat_intelligence or {}

    coverage = threat_intelligence.get("coverage", {}) or {}

    status = threat_intelligence.get("status")

    requested = coverage.get("requested", 0)

    succeeded = coverage.get("succeeded", 0)

    if not threat_intelligence or status is None:

        return {
            "state": TI_STATE_NOT_ENRICHED,
            "message": (
                "No threat-intelligence check has been recorded for "
                "this investigation."
            ),
            "short_label": "Not Available",
            "requested": requested,
            "succeeded": succeeded,
        }

    if status == "no_indicators" or requested == 0:

        return {
            "state": TI_STATE_NOT_ENRICHED,
            "message": (
                "No enrichable indicators were extracted from this "
                "report, so no threat-intelligence enrichment was "
                "attempted. Other IOC types are not enriched by the "
                "current provider integration."
            ),
            "short_label": "No Enrichable Indicators",
            "requested": requested,
            "succeeded": succeeded,
        }

    if not api_key_configured:

        return {
            "state": TI_STATE_NO_API_KEY,
            "message": (
                "No VirusTotal API key is configured, so none of "
                f"this investigation's {requested} indicator(s) "
                "could be checked. Add a key on the Settings page "
                "to enable enrichment."
            ),
            "short_label": "No API Key Configured",
            "requested": requested,
            "succeeded": succeeded,
        }

    if coverage.get("invalid_api_key"):

        return {
            "state": TI_STATE_PROVIDER_ERROR,
            "message": (
                "The configured VirusTotal API key was rejected "
                f"during this check. {succeeded}/{requested} hash "
                "indicator(s) were enriched before that."
            ),
            "short_label": "Provider Error (Invalid Key)",
            "requested": requested,
            "succeeded": succeeded,
        }

    if coverage.get("rate_limited"):

        return {
            "state": TI_STATE_PROVIDER_ERROR,
            "message": (
                "The VirusTotal rate limit was reached during this "
                f"check. {succeeded}/{requested} indicator(s) "
                "were enriched before that."
            ),
            "short_label": "Provider Error (Rate Limited)",
            "requested": requested,
            "succeeded": succeeded,
        }

    if status == "partial":

        return {
            "state": TI_STATE_INCOMPLETE_CHECK,
            "message": (
                f"{succeeded}/{requested} indicator(s) were "
                "successfully checked against VirusTotal; the rest "
                "could not be verified. This does NOT mean the "
                "unchecked indicators are clean."
            ),
            "short_label": f"Partial ({succeeded}/{requested})",
            "requested": requested,
            "succeeded": succeeded,
        }

    return {
        "state": TI_STATE_ENRICHED,
        "message": (
            f"{succeeded}/{requested} indicator(s) were "
            "checked against VirusTotal."
        ),
        "short_label": f"Enriched ({succeeded}/{requested})",
        "requested": requested,
        "succeeded": succeeded,
    }
