"""
Provider-neutral data models for the Threat Intelligence layer.

Introduced in Phase 4C, Stage 1 (Threat Intel Provider Abstraction
Foundation) per `docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md`
SS5-SS9. These models are the vocabulary every `ThreatIntelProvider`
adapter (see `app/threat_intel/provider.py`) speaks, independent of
any single provider's response shape.

Nothing in this module is wired into `ThreatIntelService` or any GUI
consumer yet -- that migration is explicitly out of scope for Stage 1
(see the design doc SS13/SS14) and is planned for a later stage.
`VirusTotalClient` (`app/threat_intel/virustotal.py`) and
`ThreatIntelService` (`app/threat_intel/service.py`) are unmodified.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class IOCType(str, Enum):
    """
    Normalized Indicator-of-Compromise categories.

    Mirrors the ten categories `app/extractor.py::IOC_PATTERNS`
    extracts (see design doc SS2.5/SS7). Not every category is
    "enrichable" by every provider -- `ThreatIntelProvider.
    supported_ioc_types` is how a provider declares which of these
    it can actually look up. A provider that does not support a
    given IOC's type is simply not called for it (see SS7's
    `Verdict.UNSUPPORTED`), not silently dropped the way today's
    `ThreatIntelService` drops the six categories it never sends to
    VirusTotal at all.
    """

    SHA256 = "sha256"
    IPV4 = "ipv4"
    DOMAIN = "domain"
    URL = "url"
    EMAIL = "email"
    MD5 = "md5"
    SHA1 = "sha1"
    CVE = "cve"
    WINDOWS_FILE_PATH = "windows_file_path"
    WINDOWS_REGISTRY_KEY = "windows_registry_key"


@dataclass(frozen=True)
class IOC(object):
    """
    A single Indicator of Compromise to be looked up against one or
    more threat intelligence providers.
    """

    type: IOCType
    value: str


class Verdict(str, Enum):
    """
    Canonical per-lookup / aggregated verdict.

    Per design doc SS5, this is the load-bearing decision of the
    whole subsystem: `NOT_FOUND` is a distinct, first-class member,
    never collapsed into `CLEAN`. A provider adapter that receives a
    "no record" response from its upstream API must construct
    `Verdict.NOT_FOUND` directly -- there is no code path by which
    "not found" can produce `Verdict.CLEAN`, because the two are set
    by different branches, not derived from a shared "compute from
    detection counts" function the way today's
    `ThreatIntelService._format_verdict` does.
    """

    MALICIOUS = "malicious"
    SUSPICIOUS = "suspicious"
    CLEAN = "clean"
    NOT_FOUND = "not_found"      # provider has no record -- explicitly NOT "clean"
    UNSUPPORTED = "unsupported"  # provider doesn't support this IOC type
    NO_API_KEY = "no_api_key"
    UNAVAILABLE = "unavailable"  # timeout / connection error
    RATE_LIMITED = "rate_limited"
    ERROR = "error"              # unexpected/malformed provider response


# Legacy display-string mapping (design doc SS5 "Legacy string
# compatibility"). Not used by anything yet in Stage 1 -- provided
# now so the later consumer-migration stage has a single, tested
# source of truth to import rather than re-deriving this mapping
# ad hoc. `"Malicious"` / `"Suspicious"` / `"Clean"` are preserved
# byte-for-byte to match today's `ThreatIntelService._format_verdict`
# output, since existing GUI/scoring/correlation code does exact
# string matches against them (SS5, SS12, SS14). `"Not Found"` is a
# new, distinct string that cannot collide with any of those existing
# exact-match checks.
LEGACY_VERDICT_STRINGS: dict[Verdict, str] = {
    Verdict.MALICIOUS: "Malicious",
    Verdict.SUSPICIOUS: "Suspicious",
    Verdict.CLEAN: "Clean",
    Verdict.NOT_FOUND: "Not Found",
}


@dataclass(frozen=True)
class ProviderResult(object):
    """
    The result of one provider's lookup of one IOC.

    Per design doc SS6. `error_detail` is populated when `verdict`
    is one of the non-content states (`UNAVAILABLE`, `ERROR`,
    `RATE_LIMITED`, `NO_API_KEY`, `UNSUPPORTED`) to carry a
    human-readable explanation without overloading `verdict` itself
    with free text.
    """

    provider: str
    ioc: IOC
    verdict: Verdict
    confidence: float | None
    raw_detection_ratio: str | None
    source_url: str | None
    queried_at: datetime
    error_detail: str | None = None


# Verdicts that represent a genuine, positive lookup outcome (the
# provider actually reached a data-backed conclusion), in descending
# severity order. Used by `aggregate()` below.
_CONTENT_PRECEDENCE: tuple[Verdict, ...] = (
    Verdict.MALICIOUS,
    Verdict.SUSPICIOUS,
    Verdict.CLEAN,
)

# Verdicts that represent "the check did not really happen" for one
# reason or another, in the precedence order `aggregate()` applies
# when no provider produced a content verdict and not every provider
# agreed on NOT_FOUND. This resolves design doc SS9's explicit
# UNKNOWN ("exact precedence among UNAVAILABLE/RATE_LIMITED/ERROR/
# UNSUPPORTED/NO_API_KEY when mixed with each other").
#
# Decision (Stage 1, documented here since this is the first
# implementation of `aggregate()` -- flagged for promotion to a
# short ADR amendment per SS9/SS16 before Phase 4C is called done):
#   RATE_LIMITED > NO_API_KEY > UNAVAILABLE > ERROR > NOT_FOUND > UNSUPPORTED
# Rationale: RATE_LIMITED and NO_API_KEY are operator-actionable and
# indicate a fixable reason the check didn't happen, so they surface
# above generic failures. UNAVAILABLE (network-level) and ERROR
# (malformed response) are both "the provider tried and failed";
# UNAVAILABLE is ranked slightly above ERROR because a connection or
# timeout failure is more likely to be transient/retryable than a
# response the provider adapter could not parse at all. NOT_FOUND
# outranks UNSUPPORTED because NOT_FOUND means at least one provider
# genuinely attempted and completed the lookup with "no record" --
# strictly more information than a provider that never attempted the
# lookup because it doesn't support the IOC type at all.
_ABSENCE_PRECEDENCE: tuple[Verdict, ...] = (
    Verdict.RATE_LIMITED,
    Verdict.NO_API_KEY,
    Verdict.UNAVAILABLE,
    Verdict.ERROR,
    Verdict.NOT_FOUND,
    Verdict.UNSUPPORTED,
)


def aggregate(results: list[ProviderResult]) -> Verdict:
    """
    Combine zero or more per-provider `ProviderResult`s into a
    single display `Verdict`, per design doc SS9.

    With exactly one configured provider (Phase 4C's actual
    shipped state -- see SS9 "single-provider degenerate case"),
    this reduces to "return that provider's verdict, unchanged."
    The function is written generally over N providers from the
    start so it does not need to be rewritten when a second
    provider is added in a later phase (SS18).

    An empty `results` list (no provider was configured or
    supported the IOC's type at all) returns `Verdict.UNSUPPORTED`,
    matching the "no configured provider supports this IOC type"
    case described in SS7.
    """

    if not results:
        return Verdict.UNSUPPORTED

    verdicts = {result.verdict for result in results}

    for content_verdict in _CONTENT_PRECEDENCE:
        if content_verdict in verdicts:
            return content_verdict

    if verdicts == {Verdict.NOT_FOUND}:
        return Verdict.NOT_FOUND

    for absence_verdict in _ABSENCE_PRECEDENCE:
        if absence_verdict in verdicts:
            return absence_verdict

    # Unreachable given the exhaustive `Verdict` enum and the checks
    # above, but kept as a defensive fallback rather than allowing an
    # unhandled combination to raise out of `aggregate()`.
    return Verdict.ERROR
