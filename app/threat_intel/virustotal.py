"""
VirusTotal API client for SOC-IQ threat intelligence enrichment.
"""

from __future__ import annotations

import logging
import re
from types import TracebackType
from typing import Any, Self

import requests

from app.settings import (
    VIRUSTOTAL_API_KEY,
    VIRUSTOTAL_TIMEOUT,
    VIRUSTOTAL_BASE_URL,
)

from app.threat_intel.exceptions import (
    MissingAPIKeyError,
    InvalidHashError,
    InvalidAPIKeyError,
    RateLimitExceededError,
    ThreatIntelTimeoutError,
    ThreatIntelConnectionError,
    UnexpectedAPIResponseError,
)

logger = logging.getLogger(__name__)

_SHA256_PATTERN = re.compile(
    r"^[A-Fa-f0-9]{64}$"
)


class VirusTotalClient:
    """
    Production-grade client for the VirusTotal v3 API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:

        self._api_key = api_key or VIRUSTOTAL_API_KEY

        if not self._api_key:
            raise MissingAPIKeyError(
                "A valid VirusTotal API key is required."
            )

        self._timeout = (
            timeout
            if timeout is not None
            else VIRUSTOTAL_TIMEOUT
        )

        if self._timeout <= 0:
            raise ValueError(
                "Timeout must be greater than zero."
            )

        self._base_url = (
            base_url
            or VIRUSTOTAL_BASE_URL
        ).rstrip("/")
        self._owns_session = session is None

        if self._owns_session:
            self._session = requests.Session()
        else:
            assert session is not None
            self._session = session

        self._session.headers.update(
            {
                "x-apikey": self._api_key,
                "Accept": "application/json",
                "User-Agent": "SOC-IQ/1.0",
            }
        )

        logger.debug(
            "VirusTotalClient initialized successfully."
        )

    def _validate_sha256(
        self,
        sha256: str,
    ) -> None:
        """
        Validate a SHA256 hash.
        """

        if (
            not isinstance(sha256, str)
            or not _SHA256_PATTERN.fullmatch(sha256)
        ):
            logger.error(
                "Hash validation failed: %s",
                sha256,
            )

            raise InvalidHashError(
                f"The provided string "
                f"{sha256!r} "
                "is not a valid SHA256 hash."
            )

    def _request(
        self,
        endpoint: str,
    ) -> requests.Response:
        """
        Send a GET request to VirusTotal.
        """

        url = (
            f"{self._base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        logger.debug(
            "Dispatching GET request to %s",
            url,
        )

        try:
            response = self._session.get(
                url,
                timeout=self._timeout,
            )

            return response

        except requests.exceptions.Timeout as error:
            logger.exception(
                "VirusTotal request timed out."
            )

            raise ThreatIntelTimeoutError(
                f"Lookup timed out after "
                f"{self._timeout} seconds."
            ) from error

        except requests.exceptions.ConnectionError as error:
            logger.exception(
                "Unable to connect to VirusTotal."
            )

            raise ThreatIntelConnectionError(
                "Unable to connect to "
                "VirusTotal."
            ) from error

        except requests.exceptions.RequestException as error:
            logger.exception(
                "Unexpected HTTP error."
            )

            raise ThreatIntelConnectionError(
                f"Unexpected request error: {error}"
            ) from error

    def lookup_sha256(
        self,
        sha256: str,
    ) -> dict[str, Any]:
        """
        Query VirusTotal using a SHA256 hash.
        """

        self._validate_sha256(sha256)

        response = self._request(
            f"files/{sha256}"
        )

        status_code = response.status_code
        if status_code == 200:
            try:
                payload = response.json()
                return self._parse_success_response(
                    sha256,
                    payload,
                )

            except (
                ValueError,
                KeyError,
                TypeError,
            ) as error:
                logger.exception(
                    "Malformed JSON payload received."
                )

                raise UnexpectedAPIResponseError(
                    "Threat intelligence response body "
                    "processing failed."
                ) from error

        if status_code == 404:
            logger.info(
                "SHA256 not found in VirusTotal: %s",
                sha256,
            )

            return self._build_not_found_response(
                sha256,
            )

        if status_code in (401, 403):
            logger.error(
                "VirusTotal rejected API key."
            )

            raise InvalidAPIKeyError(
                "Configured VirusTotal API key "
                "is invalid or unauthorized."
            )

        if status_code == 429:
            logger.warning(
                "VirusTotal API rate limit exceeded."
            )

            raise RateLimitExceededError(
                "VirusTotal API rate limit exceeded."
            )

        if status_code >= 500:
            logger.error(
                "VirusTotal server error: %s",
                status_code,
            )

            raise UnexpectedAPIResponseError(
                f"VirusTotal server returned "
                f"HTTP {status_code}."
            )

        logger.error(
            "Unexpected VirusTotal response: %s",
            status_code,
        )

        raise UnexpectedAPIResponseError(
            f"Unexpected VirusTotal response "
            f"(HTTP {status_code})."
        )

    def _build_not_found_response(
        self,
        sha256: str,
    ) -> dict[str, Any]:
        """
        Build a normalized response for hashes that
        are not present in VirusTotal.
        """

        return {
            "sha256": sha256,
            "found": False,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "reputation": 0,
            "last_analysis_date": None,
            "permalink": (
                f"https://www.virustotal.com/"
                f"gui/file/{sha256}"
            ),
        }

    def _parse_success_response(
        self,
        sha256: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Normalize a successful VirusTotal response.
        """

        attributes = (
            payload.get("data", {})
            .get("attributes", {})
        )

        stats = attributes.get(
            "last_analysis_stats",
            {},
        )

        return {
            "sha256": sha256,
            "found": True,
            "malicious": int(
                stats.get("malicious", 0)
            ),
            "suspicious": int(
                stats.get("suspicious", 0)
            ),
            "harmless": int(
                stats.get("harmless", 0)
            ),
            "undetected": int(
                stats.get("undetected", 0)
            ),
            "reputation": int(
                attributes.get("reputation") or 0
            ),
            "last_analysis_date": attributes.get(
                "last_analysis_date"
            ),
            "permalink": (
                f"https://www.virustotal.com/"
                f"gui/file/{sha256}"
            ),
        }

    def close(self) -> None:
        """
        Close the underlying HTTP session.
        """

        if self._owns_session:
            self._session.close()

            logger.debug(
                "VirusTotal session closed."
            )

    def __enter__(self) -> Self:
        """
        Context manager entry.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Context manager exit.
        """

        self.close()