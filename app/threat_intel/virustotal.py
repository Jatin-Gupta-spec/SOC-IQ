"""
VirusTotal Threat Intelligence Client.

This module provides a production-ready client responsible for
communicating with the VirusTotal v3 API.

The client currently supports configuration, authentication,
session management, and API key validation. Hash lookup
operations will be added in the next sprint step.
"""

from __future__ import annotations

import requests

from app.settings import (
    VIRUSTOTAL_API_KEY,
    VIRUSTOTAL_TIMEOUT,
)

from app.threat_intel.exceptions import (
    MissingAPIKeyError,
)


class VirusTotalClient:
    """
    Client for interacting with the VirusTotal v3 API.
    """

    BASE_URL = "https://www.virustotal.com/api/v3"

    def __init__(
        self,
        api_key: str | None = None,
        timeout: int | float | None = None,
    ) -> None:
        """
        Initialize the VirusTotal client.

        Args:
            api_key:
                Optional API key. If omitted, the key from
                settings.py is used.

            timeout:
                Optional request timeout in seconds.
        """

        self.api_key = api_key or VIRUSTOTAL_API_KEY
        self.timeout = timeout or VIRUSTOTAL_TIMEOUT

        if not self.api_key:
            raise MissingAPIKeyError(
                "VirusTotal API key is not configured."
            )

        self.session = requests.Session()

        self.session.headers.update(
            {
                "x-apikey": self.api_key,
                "Accept": "application/json",
            }
        )