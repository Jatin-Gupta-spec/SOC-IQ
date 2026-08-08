"""
Threat intelligence service.

This module coordinates threat intelligence enrichment for
Indicators of Compromise (IOCs) extracted by SOC-IQ.
"""

from __future__ import annotations

import logging
from typing import Any

from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidHashError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)
from app.threat_intel.virustotal import VirusTotalClient

logger = logging.getLogger(__name__)


class ThreatIntelService:
    """
    Service responsible for enriching extracted
    Indicators of Compromise (IOCs) using
    external threat intelligence providers.
    """

    def __init__(
        self,
        virustotal: VirusTotalClient | None = None,
    ) -> None:
        """
        Initialize the threat intelligence service.

        Args:
            virustotal:
                Optional VirusTotal client for dependency
                injection during testing.
        """

        self._virustotal = (
            virustotal
            if virustotal is not None
            else VirusTotalClient()
        )

        logger.debug(
            "ThreatIntelService initialized."
        )

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
        )

        (
            enriched_hashes,
            coverage,
        ) = self._enrich_sha256_hashes(
            hashes,
        )

        logger.info(
            "Enriched %d/%d SHA256 hash(es) (status=%s).",
            coverage["succeeded"],
            coverage["requested"],
            coverage["status"],
        )

        return {
            "hashes": enriched_hashes,
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
            `coverage["status"]` is one of:
              - "no_indicators": nothing was submitted for enrichment.
              - "ok": every requested hash was successfully looked up
                (found or not found in VirusTotal -- both are a
                completed check).
              - "partial": at least one requested hash was NOT
                successfully checked (a per-hash failure, a rate
                limit, or a rejected API key that stopped remaining
                lookups -- see `coverage["rate_limited"]` /
                `coverage["invalid_api_key"]`). `enriched` may still
                be non-empty and any "Clean" verdicts in it remain
                trustworthy -- but the *absence* of malicious
                findings across the whole set can no longer be read
                as "nothing malicious was found", only as "not
                everything was checked."
            This lets callers (and the persisted `Investigation`)
            distinguish a genuinely clean result from an incomplete
            one instead of both collapsing to the same empty/short
            `hashes` list.
        """

        enriched: list[
            dict[str, Any]
        ] = []

        requested = len(hashes)
        succeeded = 0
        failed = 0
        skipped_invalid = 0
        rate_limited = False
        invalid_api_key = False

        for sha256 in hashes:

            try:

                result = (
                    self._virustotal.lookup_sha256(
                        sha256,
                    )
                )

                malicious = result.get(
                    "malicious",
                    0,
                )

                suspicious = result.get(
                    "suspicious",
                    0,
                )

                harmless = result.get(
                    "harmless",
                    0,
                )

                undetected = result.get(
                    "undetected",
                    0,
                )

                total = (
                    malicious
                    + suspicious
                    + harmless
                    + undetected
                )

                if malicious > 0:

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

                enriched.append(
                    result,
                )

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
                    "Threat intelligence lookup failed "
                    "for %s: %s",
                    sha256,
                    error,
                )

                failed += 1

            except RateLimitExceededError:

                logger.warning(
                    "VirusTotal rate limit exceeded. "
                    "Stopping further lookups."
                )

                # Every hash that never got a chance to run counts
                # against coverage, not just this one -- otherwise
                # a rate limit hit early in a long IOC list would
                # under-report how much of the investigation was
                # left unchecked.
                remaining_unattempted = (
                    requested
                    - succeeded
                    - failed
                    - skipped_invalid
                )

                failed += remaining_unattempted

                rate_limited = True

                break

            except InvalidAPIKeyError:

                # Unlike `InvalidHashError` (a per-hash problem),
                # a rejected API key is a systemic failure: every
                # remaining hash would fail the same way. Previously
                # this exception type was not caught here at all, so
                # it escaped `_enrich_sha256_hashes` mid-batch --
                # any hashes not yet attempted were silently dropped
                # from `coverage` instead of being counted, and the
                # specific reason was lost by the time a generic
                # `except Exception` higher up in the analyzer
                # caught it. Treat it the same way as a rate limit:
                # stop further lookups and account for every
                # unattempted hash as failed.
                logger.error(
                    "VirusTotal API key rejected. "
                    "Stopping further lookups."
                )

                remaining_unattempted = (
                    requested
                    - succeeded
                    - failed
                    - skipped_invalid
                )

                failed += remaining_unattempted

                invalid_api_key = True

                break

        if requested == 0:
            status = "no_indicators"
        elif rate_limited or invalid_api_key or failed > 0:
            status = "partial"
        else:
            status = "ok"

        coverage = {
            "status": status,
            "requested": requested,
            "succeeded": succeeded,
            "failed": failed,
            "skipped_invalid": skipped_invalid,
            "rate_limited": rate_limited,
            "invalid_api_key": invalid_api_key,
        }

        return enriched, coverage

    def close(
        self,
    ) -> None:
        """
        Close underlying threat intelligence client.
        """

        self._virustotal.close()

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