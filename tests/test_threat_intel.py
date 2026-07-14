from typing import Any

from app.threat_intel.exceptions import (
    InvalidHashError,
    RateLimitExceededError,
)

from app.threat_intel.service import (
    ThreatIntelService,
)


class FakeVirusTotalClient:
    """
    Fake VirusTotal client for testing.
    """

    def __init__(self) -> None:

        self.lookups: list[str] = []


    def lookup_sha256(
        self,
        sha256: str,
    ) -> dict[str, Any]:

        self.lookups.append(
            sha256
        )

        return {
            "sha256": sha256,
            "malicious": 10,
            "suspicious": 1,
            "harmless": 60,
        }


    def close(self) -> None:
        """
        Fake close method.
        """

        pass



def test_threat_intel_service_enriches_sha256():

    fake_client = FakeVirusTotalClient()

    service = ThreatIntelService(
        virustotal=fake_client
    )

    results = service.enrich_results(
        {
            "SHA256": [
                "abc123"
            ]
        }
    )

    assert len(
        results["hashes"]
    ) == 1


    assert (
        results["hashes"][0]["sha256"]
        == "abc123"
    )


def test_threat_intel_service_handles_invalid_hash():

    class InvalidHashClient(
        FakeVirusTotalClient
    ):

        def lookup_sha256(
            self,
            sha256: str,
        ) -> dict[str, Any]:

            raise InvalidHashError(
                "Invalid hash"
            )


    service = ThreatIntelService(
        virustotal=InvalidHashClient()
    )


    results = service.enrich_results(
        {
            "SHA256": [
                "bad_hash"
            ]
        }
    )


    assert results["hashes"] == []


def test_threat_intel_service_handles_rate_limit():

    class RateLimitClient(
        FakeVirusTotalClient
    ):

        def lookup_sha256(
            self,
            sha256: str,
        ) -> dict[str, Any]:

            raise RateLimitExceededError(
                "Rate limit exceeded"
            )


    service = ThreatIntelService(
        virustotal=RateLimitClient()
    )


    results = service.enrich_results(
        {
            "SHA256": [
                "abc123"
            ]
        }
    )


    assert results["hashes"] == []