"""
VirusTotal API client for SOC-IQ threat intelligence enrichment.
 
Provides a thin, fail-fast wrapper around the VirusTotal v3 REST API
for looking up file hash reputation data via SHA256.
"""
 
import re
from types import TracebackType
from typing import Any, Self
 
import requests
 
from app.logger import logger
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
 
_SHA256_PATTERN = re.compile(
    r"^[A-Fa-f0-9]{64}$"
)
 
 
class VirusTotalClient:
    """
    Client for querying the VirusTotal v3 API for file hash reputation.
 
    Each instance owns a single requests.Session configured with the
    VirusTotal authentication header. Call close() when the client is
    no longer needed, or use it as a context manager.
    """
 
    def __init__(
        self,
        api_key: str | None = None,
        timeout: float | None = None,
    ) -> None:
        """
        Initialize the VirusTotal client.
 
        Args:
            api_key: Explicit API key, overriding VIRUSTOTAL_API_KEY.
                Primarily useful for dependency injection in tests.
            timeout: Explicit request timeout in seconds, overriding
                VIRUSTOTAL_TIMEOUT. Primarily useful for tests.
 
        Raises:
            MissingAPIKeyError: If no API key is available from either
                the constructor argument or app.settings.
        """
        self._api_key: str = api_key or VIRUSTOTAL_API_KEY
 
        if not self._api_key:
            raise MissingAPIKeyError(
                "VirusTotal API key is not configured. Set "
                "VIRUSTOTAL_API_KEY in app/settings.py, or pass "
                "api_key explicitly."
            )
 
        self._timeout = (
              timeout
        if timeout is not None
        else VIRUSTOTAL_TIMEOUT
             )
        
        self._base_url: str = VIRUSTOTAL_BASE_URL.rstrip("/")
 
        self._session: requests.Session = requests.Session()
        self._session.headers.update(
            {
                "x-apikey": self._api_key,
                "Accept": "application/json",
                "User-Agent": "SOC-IQ/1.0",
            }
        )
 
    def _validate_sha256(self, hash_value: str) -> None:
        """
        Validate that a value is a well-formed SHA256 hash.
 
        Args:
            hash_value: The candidate hash string.
 
        Raises:
            InvalidHashError: If hash_value is not exactly 64 hexadecimal
                characters.
        """
        if not isinstance(hash_value, str) or not _SHA256_PATTERN.fullmatch(
            hash_value
        ):
            raise InvalidHashError(
                f"Invalid SHA256 hash: {hash_value!r}. "
                "Expected exactly 64 hexadecimal characters."
            )
 
    def _request(self, endpoint: str) -> requests.Response:
        """
        Perform an authenticated GET request against the VirusTotal API.
 
        Args:
            endpoint: API path relative to the base URL, e.g.
                "/files/{sha256}".
 
        Returns:
            The raw requests.Response.
 
        Raises:
            ThreatIntelTimeoutError: If the request exceeds the configured
                timeout.
            ThreatIntelConnectionError: If the connection to VirusTotal
                fails, or another transport-level error occurs.
        """
        url = f"{self._base_url}/{endpoint.lstrip('/')}"
 
        try:
            return self._session.get(url, timeout=self._timeout)
        except requests.exceptions.Timeout as error:
            logger.error("VirusTotal request timed out: %s", url)
            raise ThreatIntelTimeoutError(
                f"VirusTotal request timed out after {self._timeout}s: {url}"
            ) from error
        except requests.exceptions.ConnectionError as error:
            logger.error("Connection to VirusTotal failed: %s", url)
            raise ThreatIntelConnectionError(
                f"Failed to connect to VirusTotal: {url}"
            ) from error
        except requests.exceptions.RequestException as error:
            logger.error("VirusTotal request failed: %s", url)
            raise ThreatIntelConnectionError(
                f"VirusTotal request failed: {url}"
            ) from error
 
    def lookup_sha256(self, hash_value: str) -> dict[str, Any]:
        """
        Look up a file's reputation on VirusTotal by SHA256 hash.
 
        Args:
            hash_value: A 64-character hexadecimal SHA256 hash.
 
        Returns:
            A normalized reputation dictionary with the keys: sha256,
            found, malicious, suspicious, harmless, undetected,
            reputation, last_analysis_date, permalink. If VirusTotal has
            no record of the hash, 'found' is False and the numeric
            fields carry their default (zero/None) values.
 
        Raises:
            InvalidHashError: If hash_value is not a valid SHA256 hash.
            InvalidAPIKeyError: If the configured API key is rejected.
            RateLimitExceededError: If the VirusTotal rate limit is hit.
            UnexpectedAPIResponseError: For server errors or a malformed
                200 response body.
            ThreatIntelTimeoutError: If the request times out.
            ThreatIntelConnectionError: If a connection error occurs.
        """
        self._validate_sha256(hash_value)
 
        logger.debug("Looking up SHA256: %s", hash_value)
 
        response = self._request(f"/files/{hash_value}")
 
        if response.status_code == 200:
            return self._parse_success_response(hash_value, response)
 
        if response.status_code == 404:
            logger.debug("No VirusTotal record found for %s", hash_value)
            return self._build_not_found_response(hash_value)
 
        if response.status_code in (401, 403):
            logger.error(
                "VirusTotal rejected the configured API key (HTTP %s).",
                response.status_code,
            )
            raise InvalidAPIKeyError(
                f"VirusTotal rejected the configured API key "
                f"(HTTP {response.status_code})."
            )
 
        if response.status_code == 429:
            logger.warning("VirusTotal rate limit exceeded.")
            raise RateLimitExceededError(
                "VirusTotal API rate limit exceeded."
            )
 
        if response.status_code >= 500:
            logger.error(
                "VirusTotal returned a server error (HTTP %s).",
                response.status_code,
            )
            raise UnexpectedAPIResponseError(
                f"VirusTotal returned a server error "
                f"(HTTP {response.status_code})."
            )
 
        logger.error(
            "Unexpected VirusTotal response (HTTP %s).",
            response.status_code,
        )
        raise UnexpectedAPIResponseError(
            f"Unexpected VirusTotal response (HTTP {response.status_code})."
        )
 
    def _build_not_found_response(self, hash_value: str) -> dict[str, Any]:
        """
        Build the normalized response for a hash with no VirusTotal record.
 
        Args:
            hash_value: The SHA256 hash that was looked up.
 
        Returns:
            A normalized reputation dictionary with found=False and
            default values.
        """
        return {
            "sha256": hash_value,
            "found": False,
            "malicious": 0,
            "suspicious": 0,
            "harmless": 0,
            "undetected": 0,
            "reputation": None,
            "last_analysis_date": None,
            "permalink": "",
        }
 
    def _parse_success_response(
        self,
        hash_value: str,
        response: requests.Response,
    ) -> dict[str, Any]:
        """
        Parse and normalize a successful (HTTP 200) VirusTotal response.
 
        Args:
            hash_value: The SHA256 hash that was looked up.
            response: The raw HTTP 200 response from VirusTotal.
 
        Returns:
            A normalized reputation dictionary. The raw VirusTotal JSON
            body is never returned to the caller.
 
        Raises:
            UnexpectedAPIResponseError: If the response body is not
                valid JSON or is missing the expected structure.
        """
        try:
            payload = response.json()
        except ValueError as error:
            logger.error("VirusTotal returned a non-JSON response body.")
            raise UnexpectedAPIResponseError(
                "VirusTotal returned a non-JSON response body."
            ) from error
 
        try:
            attributes = payload["data"]["attributes"]
            stats = attributes["last_analysis_stats"]
 
            return {
                "sha256": hash_value,
                "found": True,
                "malicious": int(stats.get("malicious", 0)),
                "suspicious": int(stats.get("suspicious", 0)),
                "harmless": int(stats.get("harmless", 0)),
                "undetected": int(stats.get("undetected", 0)),
                "reputation": attributes.get("reputation"),
                "last_analysis_date": attributes.get("last_analysis_date"),
                "permalink": (
                    f"https://www.virustotal.com/gui/file/{hash_value}"
                ),
            }
        except (KeyError, TypeError, ValueError, AttributeError) as error:
            logger.error("VirusTotal response was missing expected fields.")
            raise UnexpectedAPIResponseError(
                "VirusTotal response was missing expected fields."
            ) from error
 
    def close(self) -> None:
        """
        Close the underlying HTTP session and release its connections.
        """
        logger.debug("Closing VirusTotal session.")
        self._session.close()
 
    def __enter__(self) -> Self:
        return self
 
    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
 