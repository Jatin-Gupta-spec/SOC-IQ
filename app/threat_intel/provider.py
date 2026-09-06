"""
The `ThreatIntelProvider` protocol.

Introduced in Phase 4C, Stage 1 per
`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` SS4. Every
threat-intelligence provider adapter (`VirusTotalProvider` today;
AbuseIPDB/OTX/etc. in later, out-of-scope phases per SS18) implements
this protocol so that an orchestrator (a future `ThreatIntelService`,
per SS3 -- not wired up in Stage 1) can treat every provider
uniformly: route an IOC to whichever configured providers support its
type, collect their `ProviderResult`s, and hand them to
`app.threat_intel.models.aggregate()`.

Nothing in this module is wired into `ThreatIntelService` yet -- see
`models.py`'s module docstring for the same note.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.threat_intel.models import IOC, IOCType, ProviderResult


@runtime_checkable
class ThreatIntelProvider(Protocol):
    """
    Structural contract every threat-intelligence provider adapter
    implements. See design doc SS4 for the full rationale behind
    each member.
    """

    #: Short, stable, lowercase identifier for this provider, e.g.
    #: ``"virustotal"``. Echoed into every `ProviderResult` this
    #: provider produces.
    name: str

    #: Which `IOCType`s this provider can look up. The orchestrator
    #: uses this to route each IOC only to providers that declare
    #: support for its type, rather than every provider needing its
    #: own IOC-type `if` branches.
    supported_ioc_types: set[IOCType]

    async def lookup(self, ioc: IOC) -> ProviderResult:
        """
        Look up a single IOC against this provider.

        MUST NOT raise for "not found" -- that is a normal, expected
        outcome represented as `Verdict.NOT_FOUND` in the returned
        `ProviderResult`, not an exception. MAY raise a
        `ThreatIntelError` subclass for genuine failures (timeout,
        connection error, rate limit, invalid/missing key, malformed
        provider response); per design doc SS10, a well-behaved
        adapter instead translates those into an error-shaped
        `ProviderResult` (`UNAVAILABLE` / `RATE_LIMITED` / `ERROR` /
        `NO_API_KEY`, with `error_detail` populated) wherever it can,
        so the orchestrator does not need a bespoke `except` clause
        per provider per failure mode. Validation failures on the
        IOC's own value (a call-site bug, not a provider-side
        failure) remain real exceptions raised before any network
        call, per SS10.
        """
        ...

    def is_configured(self) -> bool:
        """
        Return True if this provider has everything it needs to
        attempt a lookup (e.g. an API key is present) without making
        a network call. The orchestrator uses this to skip
        unconfigured providers up front -- reflecting that in
        coverage/status as `Verdict.NO_API_KEY` -- rather than
        attempting a lookup that is guaranteed to fail on a
        missing-key error.
        """
        ...
