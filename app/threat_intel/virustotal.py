"""
VirusTotal API client for SOC-IQ threat intelligence enrichment.
"""

from __future__ import annotations

import base64
import ipaddress
import logging
import re
from datetime import UTC, datetime
from types import TracebackType
from typing import Any, Self
from urllib.parse import urlparse

import requests

from app.config import (
    VIRUSTOTAL_BASE_URL,
    VIRUSTOTAL_TIMEOUT,
)

from app.settings.service import SettingsService

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

logger = logging.getLogger(__name__)

_SHA256_PATTERN = re.compile(
    r"^[A-Fa-f0-9]{64}$"
)

_DOMAIN_LABEL_PATTERN = re.compile(
    r"^(?!-)[a-zA-Z0-9-]{1,63}(?<!-)$"
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

        settings = SettingsService().load_settings()

        self._api_key = api_key or settings.virustotal_api_key

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

            self._session: requests.Session | None = (
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

    def _validate_ip(
        self,
        ip: str,
    ) -> None:
        """
        Validate IPv4 address format.
        """

        if not isinstance(ip, str) or not ip.strip():
            logger.error(
                "Invalid IPv4 address: %s",
                ip,
            )
            raise InvalidIPError(
                f"{ip!r} is not a valid IPv4 address."
            )

        trimmed = ip.strip()
        parts = trimmed.split(".")
        if len(parts) != 4:
            logger.error(
                "Invalid IPv4 address: %s",
                ip,
            )
            raise InvalidIPError(
                f"{ip!r} is not a valid IPv4 address."
            )

        try:
            addr = ipaddress.IPv4Address(trimmed)
            if str(addr) != trimmed:
                raise ValueError(
                    "Leading zeros or non-standard IPv4 representation."
                )
        except ValueError as error:
            logger.error(
                "Invalid IPv4 address: %s",
                ip,
            )
            raise InvalidIPError(
                f"{ip!r} is not a valid IPv4 address."
            ) from error

    def _validate_domain(
        self,
        domain: str,
    ) -> None:
        """
        Validate domain name format.
        """

        if not isinstance(domain, str) or not domain.strip():
            logger.error(
                "Invalid domain name: %s",
                domain,
            )
            raise InvalidDomainError(
                f"{domain!r} is not a valid domain name."
            )

        domain_str = domain.strip().rstrip(".")
        if not domain_str or len(domain_str) > 253:
            logger.error(
                "Invalid domain length: %s",
                domain,
            )
            raise InvalidDomainError(
                f"{domain!r} is not a valid domain name."
            )

        labels = domain_str.split(".")
        if len(labels) < 2:
            logger.error(
                "Domain missing TLD: %s",
                domain,
            )
            raise InvalidDomainError(
                f"{domain!r} is not a valid domain name."
            )

        for label in labels:
            if not label or not _DOMAIN_LABEL_PATTERN.match(label):
                logger.error(
                    "Invalid label in domain: %s (%s)",
                    label,
                    domain,
                )
                raise InvalidDomainError(
                    f"{domain!r} contains an invalid label: {label!r}."
                )

        if labels[-1].isdigit():
            logger.error(
                "Domain has all-numeric TLD: %s",
                domain,
            )
            raise InvalidDomainError(
                f"{domain!r} has an invalid numeric TLD."
            )

    def _validate_url(
        self,
        url: str,
    ) -> None:
        """
        Validate that the input is a well-formed HTTP or HTTPS URL.
        """

        if not isinstance(url, str) or not url.strip():
            logger.error(
                "Invalid URL (empty or non-string): %s",
                url,
            )
            raise InvalidURLError(
                f"{url!r} is not a valid URL."
            )

        trimmed = url.strip()

        try:
            parsed = urlparse(trimmed)
        except Exception as error:
            logger.error(
                "URL parsing failed: %s",
                url,
            )
            raise InvalidURLError(
                f"{url!r} is not a valid URL."
            ) from error

        if parsed.scheme not in ("http", "https"):
            logger.error(
                "Invalid URL scheme: %s",
                parsed.scheme,
            )
            raise InvalidURLError(
                f"{url!r} does not have a valid "
                f"HTTP/HTTPS scheme."
            )

        if not parsed.netloc:
            logger.error(
                "URL has no network location: %s",
                url,
            )
            raise InvalidURLError(
                f"{url!r} is missing a valid "
                f"network location."
            )

    @staticmethod
    def _generate_url_identifier(
        url: str,
    ) -> str:
        """
        Generate the VirusTotal URL identifier.

        VirusTotal v3 requires URL lookups to use a
        URL-safe Base64-encoded identifier with trailing
        ``=`` characters removed.
        """

        url_id = (
            base64.urlsafe_b64encode(
                url.encode("utf-8")
            )
            .decode("ascii")
            .rstrip("=")
        )

        return url_id

    def _ensure_open(self) -> requests.Session:
        """
        Guard against use of the client after it has
        been closed.

        A closed VirusTotalClient previously left
        `_session` set to `None`, so any subsequent
        request raised an opaque `AttributeError`
        deep inside `requests`. This surfaces a clear,
        actionable error instead.
        """

        if self._session is None:

            raise ThreatIntelConnectionError(
                "VirusTotalClient has already been "
                "closed and cannot be reused. Create "
                "a new client instance for further "
                "lookups."
            )

        return self._session

    def _request(
        self,
        endpoint: str,
    ) -> requests.Response:
        """
        Execute a GET request.
        """

        session = self._ensure_open()

        url = (
            f"{self._base_url}/"
            f"{endpoint.lstrip('/')}"
        )

        logger.debug(
            "GET %s",
            url,
        )

        try:

            return session.get(
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

    def lookup_ip(
        self,
        ip: str,
    ) -> dict[str, Any]:
        """
        Query VirusTotal using an IPv4 address.
        """

        self._validate_ip(
            ip,
        )

        trimmed_ip = ip.strip()

        response = self._request(
            f"ip_addresses/{trimmed_ip}"
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

            return self._parse_success_ip_response(
                trimmed_ip,
                payload,
            )

        if status_code == 404:

            logger.info(
                "IP not found in VirusTotal: %s",
                trimmed_ip,
            )

            return self._build_not_found_ip_response(
                trimmed_ip,
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

    def lookup_domain(
        self,
        domain: str,
    ) -> dict[str, Any]:
        """
        Query VirusTotal using a domain name.
        """

        self._validate_domain(
            domain,
        )

        cleaned_domain = domain.strip().rstrip(".")

        response = self._request(
            f"domains/{cleaned_domain}"
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

            return self._parse_success_domain_response(
                cleaned_domain,
                payload,
            )

        if status_code == 404:

            logger.info(
                "Domain not found in VirusTotal: %s",
                cleaned_domain,
            )

            return self._build_not_found_domain_response(
                cleaned_domain,
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

    def lookup_url(
        self,
        url: str,
    ) -> dict[str, Any]:
        """
        Query VirusTotal using a URL.

        The URL is identified via URL-safe Base64 encoding
        with trailing ``=`` stripped, as required by the
        VirusTotal v3 ``/urls/{id}`` endpoint.
        """

        self._validate_url(
            url,
        )

        trimmed_url = url.strip()
        url_id = self._generate_url_identifier(
            trimmed_url,
        )

        response = self._request(
            f"urls/{url_id}"
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

            return self._parse_success_url_response(
                trimmed_url,
                url_id,
                payload,
            )

        if status_code == 404:

            logger.info(
                "URL not found in VirusTotal: %s",
                trimmed_url,
            )

            return self._build_not_found_url_response(
                trimmed_url,
                url_id,
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
                f"https://www.virustotal.com/gui/file/{sha256}"
            ),
        }

    def _build_not_found_ip_response(
        self,
        ip: str,
    ) -> dict[str, Any]:
        """
        Build a normalized response for IPv4 addresses
        that are not present in VirusTotal.
        """

        return {
            "ip": ip,
            "found": False,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "reputation": None,
            "last_analysis_date": None,
            "permalink": (
                f"https://www.virustotal.com/gui/ip-address/{ip}"
            ),
        }

    def _build_not_found_domain_response(
        self,
        domain: str,
    ) -> dict[str, Any]:
        """
        Build a normalized response for domains
        that are not present in VirusTotal.
        """

        return {
            "domain": domain,
            "found": False,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "reputation": None,
            "last_analysis_date": None,
            "permalink": (
                f"https://www.virustotal.com/gui/domain/{domain}"
            ),
        }

    def _build_not_found_url_response(
        self,
        url: str,
        url_id: str,
    ) -> dict[str, Any]:
        """
        Build a normalized response for URLs
        that are not present in VirusTotal.
        """

        return {
            "url": url,
            "url_id": url_id,
            "found": False,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "reputation": None,
            "last_analysis_date": None,
            "permalink": (
                f"https://www.virustotal.com/gui/url/{url_id}"
            ),
        }

    def _extract_attributes_and_stats(
        self,
        payload: dict[str, Any],
    ) -> tuple[dict[str, int], int | None, str | None]:
        """
        Validate and extract common VirusTotal stats and attributes.
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

        try:

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

            parsed_stats = {
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
            }

            reputation = (
                int(attributes["reputation"])
                if attributes.get(
                    "reputation"
                ) is not None
                else None
            )

            return parsed_stats, reputation, last_analysis_date

        except (
            TypeError,
            ValueError,
            OSError,
        ) as error:

            logger.exception(
                "VirusTotal response contained a malformed field."
            )

            raise UnexpectedAPIResponseError(
                "VirusTotal returned a malformed field value."
            ) from error

    def _parse_success_response(
        self,
        sha256: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and normalize a successful VirusTotal SHA256 response.
        """

        stats, reputation, last_analysis_date = (
            self._extract_attributes_and_stats(payload)
        )

        return {
            "sha256": sha256,
            "found": True,
            "malicious": stats["malicious"],
            "suspicious": stats["suspicious"],
            "harmless": stats["harmless"],
            "undetected": stats["undetected"],
            "reputation": reputation,
            "last_analysis_date": last_analysis_date,
            "permalink": (
                f"https://www.virustotal.com/gui/file/{sha256}"
            ),
        }

    def _parse_success_ip_response(
        self,
        ip: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and normalize a successful VirusTotal IPv4 response.
        """

        stats, reputation, last_analysis_date = (
            self._extract_attributes_and_stats(payload)
        )

        return {
            "ip": ip,
            "found": True,
            "malicious": stats["malicious"],
            "suspicious": stats["suspicious"],
            "harmless": stats["harmless"],
            "undetected": stats["undetected"],
            "reputation": reputation,
            "last_analysis_date": last_analysis_date,
            "permalink": (
                f"https://www.virustotal.com/gui/ip-address/{ip}"
            ),
        }

    def _parse_success_domain_response(
        self,
        domain: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and normalize a successful VirusTotal domain response.
        """

        stats, reputation, last_analysis_date = (
            self._extract_attributes_and_stats(payload)
        )

        return {
            "domain": domain,
            "found": True,
            "malicious": stats["malicious"],
            "suspicious": stats["suspicious"],
            "harmless": stats["harmless"],
            "undetected": stats["undetected"],
            "reputation": reputation,
            "last_analysis_date": last_analysis_date,
            "permalink": (
                f"https://www.virustotal.com/gui/domain/{domain}"
            ),
        }

    def _parse_success_url_response(
        self,
        url: str,
        url_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate and normalize a successful VirusTotal URL response.
        """

        stats, reputation, last_analysis_date = (
            self._extract_attributes_and_stats(payload)
        )

        return {
            "url": url,
            "url_id": url_id,
            "found": True,
            "malicious": stats["malicious"],
            "suspicious": stats["suspicious"],
            "harmless": stats["harmless"],
            "undetected": stats["undetected"],
            "reputation": reputation,
            "last_analysis_date": last_analysis_date,
            "permalink": (
                f"https://www.virustotal.com/gui/url/{url_id}"
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

    def __del__(self) -> None:
        """
        Safety net for callers that construct a
        VirusTotalClient without using it as a
        context manager and never call `close()`
        explicitly. Never raises during
        interpreter teardown.
        """

        try:

            if (
                getattr(self, "_owns_session", False)
                and getattr(self, "_session", None) is not None
            ):

                logger.warning(
                    "VirusTotalClient was garbage-collected "
                    "without close() being called explicitly. "
                    "Use 'with VirusTotalClient(...) as client:' "
                    "to guarantee the HTTP session is released."
                )

                self.close()

        except Exception:

            # __del__ must never raise.
            pass