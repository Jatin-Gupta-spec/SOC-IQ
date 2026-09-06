"""
Derive typed `Verdict` values from already-persisted raw provider
responses -- Phase 4K-1's approved "Option 1" compatibility bridge.

`Investigation.threat_intelligence` already stores, per enriched
indicator, the raw response `VirusTotalClient.lookup_*` returned at
enrichment time (`found` / `malicious` / `suspicious` / `harmless` /
`undetected` / `reputation` / `permalink` / ...) -- the same shape
`ThreatIntelService._format_verdict` annotates with the legacy
`"Clean"` / `"Malicious"` / `"Suspicious"` / `"Not Found"` display
string. This module re-reads that already-persisted raw data and
classifies it into the provider-neutral `app.threat_intel.models.
Verdict` enum, using the exact same found-first branching
`VirusTotalProvider._translate` already applies to a live lookup
response -- extracted as `virustotal_provider.translate_verdict` so
both call sites share one definition (see that function's
docstring).

This module makes NO network call and calls none of:
  - `ThreatIntelProvider.lookup()`
  - `ThreatIntelService.lookup_indicator()` / `.enrich_results()`
  - `VirusTotalProvider.lookup_raw()`
  - `ThreatIntelService._format_verdict()`
It only reads fields already sitting in the database row
(`investigation.threat_intelligence`, `investigation.iocs`), exactly
like `app.services.threat_intel_state` (Phase 4J) already does for
the `TI_STATE_*` projection -- `build_threat_intel_by_value` is
reused from there rather than re-deriving the value->raw-record
lookup here.

Older persisted investigations may predate the `found` field (see
`tests/test_application_layer.py`'s `ti_payload` fixtures, which use
bare `{"ip": ..., "verdict": "Malicious"}` records with no raw counts
at all -- pre-Stage-3 data, per `ThreatIntelService._format_verdict`'s
own docstring). Such a record cannot be honestly classified as CLEAN
or NOT_FOUND, and it carries none of the "the provider attempted and
failed" evidence that would justify UNAVAILABLE/ERROR/RATE_LIMITED/
NO_API_KEY either. It is exposed as `None` here -- the project's
existing optional-field convention for "unknown"
(e.g. `ProviderResult.confidence: float | None`) -- rather than as a
fabricated `Verdict` member.
"""

from __future__ import annotations

from typing import Any

from app.database.models import Investigation
from app.services.threat_intel_state import build_threat_intel_by_value
from app.threat_intel.virustotal_provider import translate_verdict


def _has_raw_verdict_data(raw_record: dict[str, Any]) -> bool:
    """
    True if `raw_record` carries the field `translate_verdict` needs
    to classify honestly.

    `found` is the field every real `VirusTotalClient.lookup_*`
    response sets explicitly (see its `_build_not_found_*` /
    `_parse_success_*` helpers) -- its presence is what distinguishes
    a genuine raw provider response from older persisted data that
    predates it. `translate_verdict` itself defaults a missing
    `found` to `False` (matching `VirusTotalProvider._translate`'s
    existing, unchanged default for a *live* lookup, where every raw
    response really does include `found`); that default must not be
    reached here, since for *persisted* data a missing `found` means
    "we don't actually know", not "not found" -- silently taking the
    `False` default would fabricate NOT_FOUND from missing
    information, exactly what Phase 4K-1 forbids.
    """

    return "found" in raw_record


def derive_typed_verdict(raw_record: dict[str, Any] | None) -> str | None:
    """
    Classify one already-persisted raw provider record into a typed
    verdict string (a `Verdict.value`, e.g. `"clean"`, `"not_found"`,
    `"malicious"`), or `None` if the record does not carry enough
    information to classify honestly -- no record at all, or a
    record predating the raw `found` field.
    """

    if not raw_record:
        return None

    if not _has_raw_verdict_data(raw_record):
        return None

    return translate_verdict(raw_record).value


def build_investigation_typed_verdicts(
    investigation: Investigation,
) -> dict[str, dict[str, str | None]]:
    """
    Build a `{ioc_type: {value: typed_verdict_or_None}}` projection
    for every indicator already persisted on `investigation.iocs`,
    mirroring the shape `app.services.threat_intel_state.
    build_investigation_indicator_states` already establishes for the
    `TI_STATE_*` projection -- same grouping by `ioc_type`, and reuses
    that module's `build_threat_intel_by_value` to look up each
    indicator's already-persisted raw record rather than re-deriving
    that value->record mapping here.

    Deterministic and side-effect-free: no provider is called, and an
    indicator with no persisted record -- or a persisted record that
    predates the raw `found`/count fields -- is classified as `None`,
    never guessed at.
    """

    iocs = investigation.iocs or {}
    threat_intel_by_value = build_threat_intel_by_value(investigation)

    return {
        ioc_type: {
            value: derive_typed_verdict(threat_intel_by_value.get(value))
            for value in values or []
        }
        for ioc_type, values in iocs.items()
    }
