"""
VirusTotal API client for SOC-IQ threat intelligence enrichment.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self

import requests

from app.settings import (
    VIRUSTOTAL_API_KEY,
    VIRUSTOTAL_BASE_URL,
    VIRUSTOTAL_TIMEOUT,
)

from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidHashError,
    MissingAPIKeyError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)

logger = logging.getLogger(__name__)

_SHA256_PATTERN = re.compile(
    r"^[A-Fa-f0-9]{64}$"
)


class VirusTotalClient:
    """
    Production-grade VirusTotal v3 API client.
    """

    def __init__(
        self,
        api_key: str | None = None,
        timeout: float | None = None,
        base_url: str | None = None,
        session: requests.Session | None = None,
    ) -> None:
        """
        Initialize the VirusTotal client.
        """

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

        self._owns_session = (
            session is None
        )

        if self._owns_session:

            self._session = (
                requests.Session()
            )

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
            "VirusTotal client initialized."
        )

    def _validate_sha256(
        self,
        sha256: str,
    ) -> None:
        """
        Validate SHA256 hash format.
        """

        if (
            not isinstance(sha256, str)
            or not _SHA256_PATTERN.fullmatch(
                sha256
            )
        ):
            logger.error(
                "Invalid SHA256 hash: %s",
                sha256,
            )

            raise InvalidHashError(
                f"{sha256!r} "
                "is not a valid SHA256 hash."
            )

    def _request(
        self,
        endpoint: str,
    ) -> requests.Response:
        """
        Execute a GET request.
        """

        url = (
            f"{self._base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        logger.debug(
            "GET %s",
            url,
        )

        try:

            return self._session.get(
                url,
                timeout=self._timeout,
            )

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
                "Unable to connect to VirusTotal."
            ) from error

        except requests.exceptions.RequestException as error:

            logger.exception(
                "Unexpected HTTP error."
            )

            raise ThreatIntelConnectionError(
                str(error)
            ) from error

    def lookup_sha256(
        self,
        sha256: str,
    ) -> dict[str, Any]:
        """
        Query VirusTotal using a SHA256 hash.
        """

        self._validate_sha256(
            sha256,
        )

        response = self._request(
            f"files/{sha256}"
        )

        status_code = response.status_code
        if status_code == 200:

            try:

                payload = response.json()

            except ValueError as error:

                logger.exception(
                    "VirusTotal returned invalid JSON."
                )

                raise UnexpectedAPIResponseError(
                    "VirusTotal returned an invalid JSON response."
                ) from error

            return self._parse_success_response(
                sha256,
                payload,
            )

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
                "VirusTotal API key rejected."
            )

            raise InvalidAPIKeyError(
                "Configured VirusTotal API key is invalid."
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
                "VirusTotal server error (%d).",
                status_code,
            )

            raise UnexpectedAPIResponseError(
                f"VirusTotal server returned HTTP "
                f"{status_code}."
            )

        logger.error(
            "Unexpected VirusTotal response (%d).",
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
        Build a normalized response for hashes
        that are not present in VirusTotal.
        """

        return {
            "sha256": sha256,
            "found": False,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "reputation": None,
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
        Validate and normalize a successful
        VirusTotal response.
        """

        if not isinstance(
            payload,
            dict,
        ):
            raise UnexpectedAPIResponseError(
                "VirusTotal response is not a JSON object."
            )

        try:

            data = payload["data"]

            if not isinstance(
                data,
                dict,
            ):
                raise TypeError(
                    "Invalid data section."
                )

            attributes = data["attributes"]

            if not isinstance(
                attributes,
                dict,
            ):
                raise TypeError(
                    "Invalid attributes section."
                )

            stats = attributes[
                "last_analysis_stats"
            ]

            if not isinstance(
                stats,
                dict,
            ):
                raise TypeError(
                    "Invalid analysis statistics."
                )

            required_keys = (
                "malicious",
                "suspicious",
                "harmless",
                "undetected",
            )

            missing_keys = [
                key
                for key in required_keys
                if key not in stats
            ]

            if missing_keys:

                raise KeyError(
                    f"Missing analysis fields: "
                    f"{', '.join(missing_keys)}"
                )

        except (
            KeyError,
            TypeError,
        ) as error:

            logger.exception(
                "VirusTotal response schema validation failed."
            )

            raise UnexpectedAPIResponseError(
                "VirusTotal returned an unexpected response format."
            ) from error

        last_analysis_timestamp = attributes.get(
            "last_analysis_date"
        )

        if (
            last_analysis_timestamp
            is not None
        ):

            last_analysis_date = (
                datetime.fromtimestamp(
                    last_analysis_timestamp,
                    UTC,
                ).isoformat()
            )

        else:

            last_analysis_date = None
        return {
            "sha256": sha256,
            "found": True,
            "malicious": int(
                stats["malicious"]
            ),
            "suspicious": int(
                stats["suspicious"]
            ),
            "harmless": int(
                stats["harmless"]
            ),
            "undetected": int(
                stats["undetected"]
            ),
            "reputation": (
                int(attributes["reputation"])
                if attributes.get(
                    "reputation"
                ) is not None
                else None
            ),
            "last_analysis_date": (
                last_analysis_date
            ),
            "permalink": (
                f"https://www.virustotal.com/"
                f"gui/file/{sha256}"
            ),
        }

    def close(self) -> None:
        """
        Close the HTTP session if this client
        created it.
        """

        if (
            self._owns_session
            and self._session is not None
        ):

            logger.debug(
                "Closing VirusTotal HTTP session."
            )

            self._session.close()

            self._session = None

    def __enter__(
        self,
    ) -> Self:
        """
        Enter the runtime context.
        """

        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Exit the runtime context.
        """

        self.close()