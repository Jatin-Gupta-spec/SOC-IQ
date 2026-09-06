"""
`VirusTotalProvider` -- the `ThreatIntelProvider` adapter for VirusTotal.

Introduced in Phase 4C, Stage 1 per
`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md` SS13.1.

This wraps a `VirusTotalClient` (composition, not inheritance) and
translates its existing dict-shaped return values into the
provider-neutral `ProviderResult` model, per the mapping table in
SS6. `VirusTotalClient` itself (`app/threat_intel/virustotal.py`) is
**not modified** -- its HTTP/parsing/validation logic, 77 passing
tests, and public interface are preserved exactly, per SS13.1's
explicit "preserve almost verbatim" instruction. This module only
changes who calls `VirusTotalClient` and how its output is
interpreted.

Not wired into `ThreatIntelService` or any GUI consumer in Stage 1 --
see `models.py`'s module docstring.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidDomainError,
    InvalidHashError,
    InvalidIPError,
    InvalidURLError,
    MissingAPIKeyError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)
from app.threat_intel.models import IOC, IOCType, ProviderResult, Verdict
from app.threat_intel.virustotal import VirusTotalClient

logger = logging.getLogger(__name__)

#: IOC types VirusTotal can be queried for today, matching exactly
#: the four `lookup_*` methods `VirusTotalClient` implements (design
#: doc SS7 "Current (CONFIRMED)"). Widening this to MD5/SHA1 is
#: explicitly out of scope for this stage (SS7's UNKNOWN about
#: whether `VirusTotalClient`'s SHA256-only validation is intentional
#: is not resolved here).
_SUPPORTED_IOC_TYPES: set[IOCType] = {
    IOCType.SHA256,
    IOCType.IPV4,
    IOCType.DOMAIN,
    IOCType.URL,
}

# Re-raised as-is by `lookup()` rather than translated into an
# error-shaped ProviderResult, per design doc SS10: these are
# call-site bugs (a malformed IOC value), not provider-side
# failures, and the existing "skip without ever attempting a network
# call" behavior is correct and preserved unchanged.
_VALIDATION_ERRORS = (
    InvalidHashError,
    InvalidIPError,
    InvalidDomainError,
    InvalidURLError,
)


def translate_verdict(raw: dict[str, Any]) -> Verdict:
    """
    Pure found-first verdict classification for a raw
    `VirusTotalClient.lookup_*`-shaped dict.

    Extracted (Phase 4K-1) from what was previously inlined at the
    top of `VirusTotalProvider._translate` below -- byte-for-byte the
    same branching, not a rewrite -- so that a second caller
    (`app.threat_intel.verdict_from_persisted`, which classifies
    already-persisted raw responses rather than a live lookup's raw
    response) can reuse this exact decision instead of re-deriving
    it. `_translate` itself is updated to call this function rather
    than duplicating the branching inline; its other responsibilities
    (detection ratio, confidence, source URL, `ProviderResult`
    construction) are unchanged.
    """

    found = bool(raw.get("found", False))
    malicious = int(raw.get("malicious", 0) or 0)
    suspicious = int(raw.get("suspicious", 0) or 0)

    if not found:
        # Structural enforcement of SS5/SS12: not-found short-
        # circuits straight to NOT_FOUND, never reaching the
        # malicious/suspicious/clean branching below.
        return Verdict.NOT_FOUND
    if malicious > 0:
        return Verdict.MALICIOUS
    if suspicious > 0:
        return Verdict.SUSPICIOUS
    return Verdict.CLEAN


class VirusTotalProvider:
    """
    `ThreatIntelProvider` adapter wrapping `VirusTotalClient`.

    Satisfies `app.threat_intel.provider.ThreatIntelProvider`
    structurally (see that module's `runtime_checkable` Protocol).
    """

    name = "virustotal"
    supported_ioc_types: set[IOCType] = _SUPPORTED_IOC_TYPES

    def __init__(
        self,
        client: VirusTotalClient | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        Args:
            client:
                Optional pre-constructed `VirusTotalClient` for
                dependency injection during testing. If provided,
                this provider is always considered configured and
                this exact client instance is used for every lookup.
            api_key:
                Optional API key to construct a `VirusTotalClient`
                with, lazily, on first lookup. If omitted, the
                lazily-constructed client falls back to
                `SettingsService`, exactly as `VirusTotalClient`
                does today.
            timeout:
                Optional per-request timeout passed through to the
                lazily-constructed `VirusTotalClient`.
        """

        self._injected_client = client
        self._client: VirusTotalClient | None = client
        self._api_key = api_key
        self._timeout = timeout

    def is_configured(self) -> bool:
        """
        True without making a network call or constructing a full
        client, per SS4/SS8. An injected client or an explicit
        `api_key` both count as configured; otherwise this checks
        `SettingsService` directly -- the same source
        `VirusTotalClient.__init__` reads from, but without
        triggering its `MissingAPIKeyError` side effect just to find
        out whether a key exists.
        """

        if self._injected_client is not None:
            return True

        if self._api_key:
            return True

        try:
            from app.settings.service import SettingsService

            settings = SettingsService().load_settings()
        except Exception:
            logger.exception(
                "Failed to load settings while checking VirusTotal "
                "provider configuration."
            )
            return False

        return bool(settings.virustotal_api_key)

    def _get_client(self) -> VirusTotalClient:
        """
        Return the injected client, or lazily construct one on first
        use. Raises `MissingAPIKeyError` exactly as
        `VirusTotalClient()` does today if no key is configured --
        `lookup()` catches this and translates it into a
        `Verdict.NO_API_KEY` result rather than letting it propagate.
        """

        if self._client is None:
            self._client = VirusTotalClient(
                api_key=self._api_key,
                timeout=self._timeout,
            )

        return self._client

    async def lookup(self, ioc: IOC) -> ProviderResult:
        """
        Look up a single IOC against VirusTotal.

        See `ThreatIntelProvider.lookup` for the general contract.
        `VirusTotalClient` is fully synchronous (`requests`-based);
        per design doc SS13.2 option (a), each call is bridged onto
        a worker thread via `asyncio.to_thread` so `VirusTotalClient`
        itself needs zero changes.
        """

        if ioc.type not in self.supported_ioc_types:
            return self._error_result(
                ioc,
                Verdict.UNSUPPORTED,
                f"VirusTotal does not support IOC type {ioc.type.value!r}.",
            )

        try:
            client = self._get_client()
        except MissingAPIKeyError as error:
            return self._error_result(
                ioc,
                Verdict.NO_API_KEY,
                str(error),
            )

        try:
            raw = await self._dispatch(client, ioc)
        except _VALIDATION_ERRORS:
            # Call-site bug (malformed IOC value) -- propagate per
            # SS10, do not translate into a ProviderResult.
            raise
        except InvalidAPIKeyError as error:
            return self._error_result(
                ioc,
                Verdict.NO_API_KEY,
                str(error),
            )
        except RateLimitExceededError as error:
            return self._error_result(
                ioc,
                Verdict.RATE_LIMITED,
                str(error),
            )
        except (ThreatIntelTimeoutError, ThreatIntelConnectionError) as error:
            return self._error_result(
                ioc,
                Verdict.UNAVAILABLE,
                str(error),
            )
        except UnexpectedAPIResponseError as error:
            return self._error_result(
                ioc,
                Verdict.ERROR,
                str(error),
            )

        return self._translate(ioc, raw)

    async def lookup_raw(self, ioc: IOC) -> dict[str, Any]:
        """
        VT-specific escape hatch: dispatch to the matching
        `VirusTotalClient.lookup_*` method and return its raw,
        untranslated dict -- not a `ProviderResult`.

        Not part of the `ThreatIntelProvider` Protocol (see
        `provider.py`); this is deliberately *not* something every
        future provider needs to implement. It exists for Phase 4C
        Stage 2 consumers (`ThreatIntelService.enrich_results` and
        its GUI-facing single-lookup counterpart) that must preserve
        the exact legacy VirusTotal dict shape -- including the
        `malicious`/`suspicious`/`harmless`/`undetected` breakdown,
        `reputation`, and `last_analysis_date` -- none of which
        `ProviderResult` can carry losslessly (see design doc SS6's
        `last_analysis_date` UNKNOWN, unresolved until this stage).

        Unlike `lookup()`, this does NOT translate errors into an
        error-shaped result: every exception `VirusTotalClient`
        raises (`MissingAPIKeyError`, the four `Invalid*Error`
        validation errors, `InvalidAPIKeyError`,
        `RateLimitExceededError`, `ThreatIntelTimeoutError`,
        `ThreatIntelConnectionError`, `UnexpectedAPIResponseError`)
        propagates unchanged, exactly matching what calling
        `VirusTotalClient.lookup_*` directly did before Stage 2 --
        callers that need that exact legacy control flow (stop-on-
        rate-limit, skip-on-invalid, etc.) keep working unmodified.
        """

        client = self._get_client()
        return await self._dispatch(client, ioc)

    async def _dispatch(
        self,
        client: VirusTotalClient,
        ioc: IOC,
    ) -> dict[str, Any]:
        """
        Call the `VirusTotalClient` method matching `ioc.type`,
        off the event loop thread.
        """

        if ioc.type is IOCType.SHA256:
            return await asyncio.to_thread(client.lookup_sha256, ioc.value)

        if ioc.type is IOCType.IPV4:
            return await asyncio.to_thread(client.lookup_ip, ioc.value)

        if ioc.type is IOCType.DOMAIN:
            return await asyncio.to_thread(client.lookup_domain, ioc.value)

        if ioc.type is IOCType.URL:
            return await asyncio.to_thread(client.lookup_url, ioc.value)

        # Unreachable: `lookup()` already checked `supported_ioc_types`
        # before calling `_dispatch`.
        raise AssertionError(
            f"VirusTotalProvider._dispatch called with unsupported "
            f"IOC type {ioc.type!r}."
        )

    def _translate(self, ioc: IOC, raw: dict[str, Any]) -> ProviderResult:
        """
        Translate a `VirusTotalClient.lookup_*` return dict into a
        `ProviderResult`, per the mapping table in design doc SS6.
        """

        malicious = int(raw.get("malicious", 0) or 0)
        suspicious = int(raw.get("suspicious", 0) or 0)
        harmless = int(raw.get("harmless", 0) or 0)
        undetected = int(raw.get("undetected", 0) or 0)
        total = malicious + suspicious + harmless + undetected

        verdict = translate_verdict(raw)

        raw_detection_ratio = (
            f"{malicious}/{total}" if total > 0 else "N/A"
        )

        return ProviderResult(
            provider=self.name,
            ioc=ioc,
            verdict=verdict,
            confidence=self._normalize_confidence(raw.get("reputation")),
            raw_detection_ratio=raw_detection_ratio,
            source_url=raw.get("permalink"),
            queried_at=datetime.now(UTC),
            error_detail=None,
        )

    @staticmethod
    def _normalize_confidence(reputation: Any) -> float | None:
        """
        Fold VT's `reputation` field into `ProviderResult.confidence`.

        VT's reputation is an unbounded signed integer, not a 0-1
        scale (design doc SS6 UNKNOWN -- explicitly flagged as not
        resolved by the design doc). This applies a simple, clamped
        linear normalization as a provisional choice for Stage 1
        rather than leaving `confidence` unpopulated; it is not a
        statistically calibrated mapping and should be revisited
        before any UI relies on its absolute value rather than its
        relative ordering.
        """

        if reputation is None:
            return None

        try:
            reputation_value = float(reputation)
        except (TypeError, ValueError):
            return None

        normalized = (reputation_value + 100.0) / 200.0
        return max(0.0, min(1.0, normalized))

    def _error_result(
        self,
        ioc: IOC,
        verdict: Verdict,
        error_detail: str,
    ) -> ProviderResult:
        return ProviderResult(
            provider=self.name,
            ioc=ioc,
            verdict=verdict,
            confidence=None,
            raw_detection_ratio=None,
            source_url=None,
            queried_at=datetime.now(UTC),
            error_detail=error_detail,
        )

    def close(self) -> None:
        """
        Close the underlying `VirusTotalClient`, if one has been
        constructed (lazily or injected). Safe to call even if no
        lookup has happened yet.
        """

        if self._client is not None:
            self._client.close()

    async def __aenter__(self) -> "VirusTotalProvider":
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        self.close()
