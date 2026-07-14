"""
Threat intelligence service.

This module coordinates threat intelligence enrichment for
Indicators of Compromise (IOCs) extracted by SOC-IQ.
"""

from __future__ import annotations

import logging
from typing import Any

from app.threat_intel.exceptions import (
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

        return {
            "hashes": self._enrich_sha256_hashes(
                hashes
            )
        }

    def _enrich_sha256_hashes(
        self,
        hashes: list[str],
    ) -> list[dict[str, Any]]:
        """
        Enrich SHA256 hashes using VirusTotal.

        Args:
            hashes:
                List of SHA256 hashes.

        Returns:
            List of VirusTotal enrichment results.
        """

        enriched: list[dict[str, Any]] = []

        for sha256 in hashes:

            try:

                result = self._virustotal.lookup_sha256(
                    sha256
                )

                enriched.append(
                    result
                )

            except InvalidHashError:

                logger.warning(
                    "Skipping invalid SHA256: %s",
                    sha256,
                )

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

            except RateLimitExceededError:

                logger.warning(
                    "VirusTotal rate limit exceeded. "
                    "Stopping further lookups."
                )

                break

        return enriched

    def close(self) -> None:
        """
        Close underlying threat intelligence clients.
        """

        self._virustotal.close()

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