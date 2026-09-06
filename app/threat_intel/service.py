"""
Threat intelligence service.

This module coordinates threat intelligence enrichment for
Indicators of Compromise (IOCs) extracted by SOC-IQ.

Phase 4C, Stage 2 (`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md`
SS13.3/SS14): `ThreatIntelService` now depends on the
`ThreatIntelProvider` abstraction introduced in Stage 1
(`app/threat_intel/provider.py`) rather than directly on
`VirusTotalClient`. Concretely, it holds `providers:
list[ThreatIntelProvider]` (defaulting to `[VirusTotalProvider()]`,
mirroring the previous `virustotal: VirusTotalClient | None = None`
default-construction pattern exactly) instead of a bare
`VirusTotalClient` instance.

Per SS14's compatibility strategy, `enrich_results`'s public
signature and output dict shape are unchanged -- including the raw
`malicious`/`suspicious`/`harmless`/`undetected`/`reputation`/
`last_analysis_date`/`permalink` fields, which `ProviderResult`
cannot carry losslessly (SS6's flagged UNKNOWN). Internally this is
resolved by dispatching through `VirusTotalProvider.lookup_raw()` --
a VT-specific escape hatch documented in that module -- rather than
through the protocol's provider-neutral `lookup()`/`ProviderResult`,
which remains reserved for future multi-provider aggregation
(`app.threat_intel.models.aggregate()`, not yet wired up anywhere,
consistent with Stage 1).

The previous `virustotal: VirusTotalClient | None = None` DI
parameter is preserved as an additional, optional constructor
argument for exact backward compatibility with existing callers/
tests that inject a fake raw client: passing it wraps the client in
a `VirusTotalProvider(client=...)` under the hood, so the service's
actual internal dependency is still on `ThreatIntelProvider`, never
on a stored `VirusTotalClient` reference used directly.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidDomainError,
    InvalidHashError,
    InvalidIPError,
    InvalidURLError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)
from app.threat_intel.models import IOC, IOCType
from app.threat_intel.provider import ThreatIntelProvider
from app.threat_intel.virustotal import VirusTotalClient
from app.threat_intel.virustotal_provider import VirusTotalProvider

logger = logging.getLogger(__name__)

#: Maps the GUI's/worker's plain query-type strings onto `IOCType`.
#: Matches exactly the four categories `VirusTotalProvider` supports
#: (see its `_SUPPORTED_IOC_TYPES`) -- the same four categories
#: `enrich_results` has always enriched.
_QUERY_TYPE_TO_IOC_TYPE: dict[str, IOCType] = {
    "sha256": IOCType.SHA256,
    "ipv4": IOCType.IPV4,
    "domain": IOCType.DOMAIN,
    "url": IOCType.URL,
}


class ThreatIntelService:
    """
    Service responsible for enriching extracted
    Indicators of Compromise (IOCs) using
    external threat intelligence providers.
    """

    def __init__(
        self,
        providers: list[ThreatIntelProvider] | None = None,
        virustotal: VirusTotalClient | None = None,
    ) -> None:
        """
        Initialize the threat intelligence service.

        Args:
            providers:
                Optional list of `ThreatIntelProvider` adapters for
                dependency injection during testing, or to configure
                which providers are active. Defaults to a single
                `VirusTotalProvider()` -- Phase 4C's single-provider
                degenerate case (design doc SS9) -- mirroring the
                previous zero-argument `ThreatIntelService()`
                default-construction behavior exactly.
            virustotal:
                Optional raw `VirusTotalClient` (or VT-shaped fake)
                for dependency injection during testing, preserved
                from before Stage 2 for exact backward compatibility.
                Wrapped as `VirusTotalProvider(client=virustotal)`
                internally -- the service's actual stored dependency
                is always `ThreatIntelProvider`, never a bare
                `VirusTotalClient`. Mutually exclusive with
                `providers`.

        Raises:
            TypeError:
                If both `providers` and `virustotal` are given --
                ambiguous which should take effect.
        """

        if providers is not None and virustotal is not None:
            raise TypeError(
                "ThreatIntelService accepts at most one of "
                "`providers` or `virustotal`, not both."
            )

        if providers is not None:
            self._providers: list[ThreatIntelProvider] = providers
        elif virustotal is not None:
            self._providers = [VirusTotalProvider(client=virustotal)]
        else:
            self._providers = [VirusTotalProvider()]

        logger.debug(
            "ThreatIntelService initialized."
        )

    def _virustotal_provider(self) -> VirusTotalProvider | None:
        """
        Return the configured `VirusTotalProvider`, if one is
        present, for VT-specific legacy-dict-shape lookups
        (`enrich_results`, `lookup_indicator`). Phase 4C only ever
        configures one provider, so this is the single-provider
        degenerate case (design doc SS9) rather than a real
        multi-provider selection policy -- a later phase's second
        provider (SS18) does not change `enrich_results`'s VT-shaped
        contract, since that legacy shape is inherently
        VirusTotal-specific.
        """

        for provider in self._providers:
            if isinstance(provider, VirusTotalProvider):
                return provider

        return None

    @staticmethod
    def _format_verdict(
        result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Compute and attach verdict and detection_ratio fields.

        Phase 4C, Stage 3 (design doc SS12, "the central requirement
        of this phase"): `found` is read as an explicit, first-class
        signal *before* any count-based branching, so a not-found
        result short-circuits straight to the new `"Not Found"`
        legacy string and can never fall through to `"Clean"` --
        structurally, not just as a one-off patch (SS5/SS12). Every
        real `VirusTotalClient`/`VirusTotalProvider.lookup_raw()`
        result always includes `found` (SS1/SS12); `.get("found",
        True)` only matters for pre-Stage-3 test doubles that never
        populated it and were exercising the malicious/suspicious/
        clean branches, not the found/not-found one -- defaulting
        those to `True` preserves their existing behavior exactly.
        """

        found = result.get("found", True)

        malicious = int(result.get("malicious", 0) or 0)
        suspicious = int(result.get("suspicious", 0) or 0)
        harmless = int(result.get("harmless", 0) or 0)
        undetected = int(result.get("undetected", 0) or 0)
        total = (
            malicious
            + suspicious
            + harmless
            + undetected
        )

        if not found:
            verdict = "Not Found"
        elif malicious > 0:
            verdict = "Malicious"
        elif suspicious > 0:
            verdict = "Suspicious"
        else:
            verdict = "Clean"

        result["verdict"] = verdict
        result["detection_ratio"] = (
            f"{malicious}/{total}"
            if total > 0
            else "N/A"
        )
        return result

    def _lookup_raw(self, ioc_type: IOCType, value: str) -> dict[str, Any]:
        """
        Dispatch a single raw (untranslated) lookup through the
        configured `VirusTotalProvider`, bridging its `async
        lookup_raw()` onto this method's synchronous callers exactly
        as `enrich_results`/`lookup_indicator` need. Every exception
        `VirusTotalProvider.lookup_raw()` raises propagates
        unchanged -- see that method's docstring.
        """

        provider = self._virustotal_provider()

        if provider is None:
            # Phase 4C always configures a VirusTotalProvider (the
            # only provider that exists yet); this is a defensive
            # guard against future misconfiguration, not a code path
            # exercised in Phase 4C.
            raise UnexpectedAPIResponseError(
                "No VirusTotal provider is configured."
            )

        ioc = IOC(type=ioc_type, value=value)
        return asyncio.run(provider.lookup_raw(ioc))

    def is_configured(self) -> bool:
        """
        True if any configured provider is ready to attempt a
        lookup (e.g. has an API key), without making a network call.
        Used by GUI consumers to decide whether to offer live
        lookups at all -- see `app/gui/pages/threat_intel_page.py`.
        """

        return any(provider.is_configured() for provider in self._providers)

    def lookup_indicator(self, ioc_type: str, value: str) -> dict[str, Any]:
        """
        Look up a single indicator and return it in the same
        VT-shaped, verdict-annotated dict that `enrich_results`
        produces per item -- e.g. `{"sha256": ..., "found": ...,
        "malicious": ..., ..., "verdict": ..., "detection_ratio":
        ...}`.

        Unlike `enrich_results`, this does not catch and count
        errors -- it is meant for interactive, single-indicator
        callers (the Threat Intelligence page's ad-hoc lookup) that
        want to handle a single failure directly, exactly as calling
        `VirusTotalClient.lookup_*` directly did before Stage 2.
        Every exception `VirusTotalProvider.lookup_raw()` raises
        propagates unchanged.

        Args:
            ioc_type:
                One of `"sha256"`, `"ipv4"`, `"domain"`, `"url"` --
                the same four categories `enrich_results` enriches.
            value:
                The indicator value to look up.

        Raises:
            ValueError:
                If `ioc_type` is not one of the four supported
                categories.
        """

        mapped_type = _QUERY_TYPE_TO_IOC_TYPE.get(ioc_type)
        if mapped_type is None:
            raise ValueError(
                f"Unsupported indicator type {ioc_type!r}. "
                f"Expected one of {sorted(_QUERY_TYPE_TO_IOC_TYPE)}."
            )

        raw = self._lookup_raw(mapped_type, value)
        return self._format_verdict(raw)

    def enrich_results(
        self,
        results: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Enrich extracted IOCs with threat intelligence.

        Args:
            results:
                Dictionary returned by the IOC extractor.

        Returns:
            Dictionary containing enrichment results.
        """

        hashes = results.get(
            "SHA256",
            results.get(
                "sha256",
                [],
            ),
        ) or []
        ips = results.get(
            "ipv4",
            results.get(
                "IPV4",
                results.get(
                    "ips",
                    [],
                ),
            ),
        ) or []
        domains = results.get(
            "domains",
            results.get(
                "DOMAINS",
                results.get(
                    "domain",
                    [],
                ),
            ),
        ) or []
        urls = results.get(
            "urls",
            results.get(
                "URLS",
                results.get(
                    "url",
                    [],
                ),
            ),
        ) or []

        enriched_hashes: list[dict[str, Any]] = []
        enriched_ips: list[dict[str, Any]] = []
        enriched_domains: list[dict[str, Any]] = []
        enriched_urls: list[dict[str, Any]] = []

        total_requested = len(hashes) + len(ips) + len(domains) + len(urls)
        succeeded = 0
        failed = 0
        skipped_invalid = 0
        rate_limited = False
        invalid_api_key = False

        # 1. SHA256 Hashes
        for idx, sha256 in enumerate(hashes):
            try:
                result = self._lookup_raw(
                    IOCType.SHA256,
                    sha256,
                )
                result = self._format_verdict(result)
                enriched_hashes.append(result)
                succeeded += 1
            except InvalidHashError:
                logger.warning(
                    "Skipping invalid SHA256: %s",
                    sha256,
                )
                skipped_invalid += 1
            except (
                ThreatIntelTimeoutError,
                ThreatIntelConnectionError,
                UnexpectedAPIResponseError,
            ) as error:
                logger.error(
                    "Threat intelligence lookup failed for SHA256 %s: %s",
                    sha256,
                    error,
                )
                failed += 1
            except RateLimitExceededError:
                logger.warning(
                    "VirusTotal rate limit exceeded during SHA256 lookups. Stopping further lookups."
                )
                rate_limited = True
                remaining_hashes = len(hashes) - (idx + 1)
                failed += 1 + remaining_hashes + len(ips) + len(domains) + len(urls)
                break
            except InvalidAPIKeyError:
                logger.error(
                    "VirusTotal API key rejected during SHA256 lookups. Stopping further lookups."
                )
                invalid_api_key = True
                remaining_hashes = len(hashes) - (idx + 1)
                failed += 1 + remaining_hashes + len(ips) + len(domains) + len(urls)
                break

        # 2. IPv4 Addresses
        if not (rate_limited or invalid_api_key):
            for idx, ip in enumerate(ips):
                try:
                    result = self._lookup_raw(
                        IOCType.IPV4,
                        ip,
                    )
                    result = self._format_verdict(result)
                    enriched_ips.append(result)
                    succeeded += 1
                except InvalidIPError:
                    logger.warning(
                        "Skipping invalid IPv4: %s",
                        ip,
                    )
                    skipped_invalid += 1
                except (
                    ThreatIntelTimeoutError,
                    ThreatIntelConnectionError,
                    UnexpectedAPIResponseError,
                ) as error:
                    logger.error(
                        "Threat intelligence lookup failed for IPv4 %s: %s",
                        ip,
                        error,
                    )
                    failed += 1
                except RateLimitExceededError:
                    logger.warning(
                        "VirusTotal rate limit exceeded during IPv4 lookups. Stopping further lookups."
                    )
                    rate_limited = True
                    remaining_ips = len(ips) - (idx + 1)
                    failed += 1 + remaining_ips + len(domains) + len(urls)
                    break
                except InvalidAPIKeyError:
                    logger.error(
                        "VirusTotal API key rejected during IPv4 lookups. Stopping further lookups."
                    )
                    invalid_api_key = True
                    remaining_ips = len(ips) - (idx + 1)
                    failed += 1 + remaining_ips + len(domains) + len(urls)
                    break

        # 3. Domains
        if not (rate_limited or invalid_api_key):
            for idx, domain in enumerate(domains):
                try:
                    result = self._lookup_raw(
                        IOCType.DOMAIN,
                        domain,
                    )
                    result = self._format_verdict(result)
                    enriched_domains.append(result)
                    succeeded += 1
                except InvalidDomainError:
                    logger.warning(
                        "Skipping invalid domain: %s",
                        domain,
                    )
                    skipped_invalid += 1
                except (
                    ThreatIntelTimeoutError,
                    ThreatIntelConnectionError,
                    UnexpectedAPIResponseError,
                ) as error:
                    logger.error(
                        "Threat intelligence lookup failed for domain %s: %s",
                        domain,
                        error,
                    )
                    failed += 1
                except RateLimitExceededError:
                    logger.warning(
                        "VirusTotal rate limit exceeded during domain lookups. Stopping further lookups."
                    )
                    rate_limited = True
                    remaining_domains = len(domains) - (idx + 1)
                    failed += 1 + remaining_domains
                    break
                except InvalidAPIKeyError:
                    logger.error(
                        "VirusTotal API key rejected during domain lookups. Stopping further lookups."
                    )
                    invalid_api_key = True
                    remaining_domains = len(domains) - (idx + 1)
                    failed += 1 + remaining_domains + len(urls)
                    break

        # 4. URLs
        if not (rate_limited or invalid_api_key):
            for idx, url in enumerate(urls):
                try:
                    result = self._lookup_raw(
                        IOCType.URL,
                        url,
                    )
                    result = self._format_verdict(result)
                    enriched_urls.append(result)
                    succeeded += 1
                except InvalidURLError:
                    logger.warning(
                        "Skipping invalid URL: %s",
                        url,
                    )
                    skipped_invalid += 1
                except (
                    ThreatIntelTimeoutError,
                    ThreatIntelConnectionError,
                    UnexpectedAPIResponseError,
                ) as error:
                    logger.error(
                        "Threat intelligence lookup failed for URL %s: %s",
                        url,
                        error,
                    )
                    failed += 1
                except RateLimitExceededError:
                    logger.warning(
                        "VirusTotal rate limit exceeded during URL lookups. Stopping further lookups."
                    )
                    rate_limited = True
                    remaining_urls = len(urls) - (idx + 1)
                    failed += 1 + remaining_urls
                    break
                except InvalidAPIKeyError:
                    logger.error(
                        "VirusTotal API key rejected during URL lookups. Stopping further lookups."
                    )
                    invalid_api_key = True
                    remaining_urls = len(urls) - (idx + 1)
                    failed += 1 + remaining_urls
                    break

        if total_requested == 0:
            status = "no_indicators"
        elif rate_limited or invalid_api_key or failed > 0:
            status = "partial"
        else:
            status = "ok"

        coverage = {
            "status": status,
            "requested": total_requested,
            "succeeded": succeeded,
            "failed": failed,
            "skipped_invalid": skipped_invalid,
            "rate_limited": rate_limited,
            "invalid_api_key": invalid_api_key,
        }

        logger.info(
            "Enriched %d/%d indicator(s) (status=%s).",
            coverage["succeeded"],
            coverage["requested"],
            coverage["status"],
        )

        return {
            "hashes": enriched_hashes,
            "ips": enriched_ips,
            "domains": enriched_domains,
            "urls": enriched_urls,
            "status": coverage["status"],
            "coverage": coverage,
        }

    def _enrich_sha256_hashes(
        self,
        hashes: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Enrich SHA256 hashes using VirusTotal.

        Args:
            hashes:
                List of SHA256 hashes.

        Returns:
            A tuple of `(enriched_results, coverage)`.
        """
        results = self.enrich_results({"SHA256": hashes})
        return results["hashes"], results["coverage"]

    def _enrich_ips(
        self,
        ips: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Enrich IPv4 addresses using VirusTotal.

        Args:
            ips:
                List of IPv4 addresses.

        Returns:
            A tuple of `(enriched_results, coverage)`.
        """
        results = self.enrich_results({"ipv4": ips})
        return results["ips"], results["coverage"]

    def _enrich_domains(
        self,
        domains: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Enrich domains using VirusTotal.

        Args:
            domains:
                List of domain names.

        Returns:
            A tuple of `(enriched_results, coverage)`.
        """
        results = self.enrich_results({"domains": domains})
        return results["domains"], results["coverage"]

    def _enrich_urls(
        self,
        urls: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Enrich URLs using VirusTotal.

        Args:
            urls:
                List of URLs.

        Returns:
            A tuple of `(enriched_results, coverage)`.
        """
        results = self.enrich_results({"urls": urls})
        return results["urls"], results["coverage"]

    def close(
        self,
    ) -> None:
        """
        Close underlying threat intelligence provider(s).
        """

        for provider in self._providers:
            close = getattr(provider, "close", None)
            if callable(close):
                close()

        logger.debug(
            "Threat intelligence service closed."
        )

    def __enter__(
        self,
    ) -> "ThreatIntelService":
        """
        Context manager entry.
        """

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ) -> None:
        """
        Context manager exit.
        """

        self.close()
