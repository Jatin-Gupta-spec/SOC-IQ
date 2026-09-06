from typing import Any

import pytest

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

from app.threat_intel.service import (
    ThreatIntelService,
)


class FakeVirusTotalClient:
    """
    Fake VirusTotal client for testing.
    """

    def __init__(self) -> None:
        self.lookups: list[str] = []
        self.ip_lookups: list[str] = []
        self.domain_lookups: list[str] = []
        self.url_lookups: list[str] = []
        self.closed = False

    def lookup_sha256(
        self,
        sha256: str,
    ) -> dict[str, Any]:
        self.lookups.append(sha256)
        return {
            "sha256": sha256,
            "malicious": 10,
            "suspicious": 1,
            "harmless": 60,
            "undetected": 0,
        }

    def lookup_ip(
        self,
        ip: str,
    ) -> dict[str, Any]:
        self.ip_lookups.append(ip)
        return {
            "ip": ip,
            "malicious": 4,
            "suspicious": 0,
            "harmless": 70,
            "undetected": 2,
        }

    def lookup_domain(
        self,
        domain: str,
    ) -> dict[str, Any]:
        self.domain_lookups.append(domain)
        return {
            "domain": domain,
            "malicious": 0,
            "suspicious": 2,
            "harmless": 65,
            "undetected": 3,
        }

    def lookup_url(
        self,
        url: str,
    ) -> dict[str, Any]:
        self.url_lookups.append(url)
        return {
            "url": url,
            "malicious": 3,
            "suspicious": 1,
            "harmless": 80,
            "undetected": 5,
        }

    def close(self) -> None:
        self.closed = True


def test_threat_intel_service_enriches_sha256():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    results = service.enrich_results({"SHA256": ["abc123"]})

    assert len(results["hashes"]) == 1
    assert results["hashes"][0]["sha256"] == "abc123"
    assert results["hashes"][0]["verdict"] == "Malicious"
    assert results["hashes"][0]["detection_ratio"] == "10/71"
    assert results["status"] == "ok"
    assert results["coverage"]["succeeded"] == 1


def test_threat_intel_service_handles_invalid_hash():
    class InvalidHashClient(FakeVirusTotalClient):
        def lookup_sha256(self, sha256: str) -> dict[str, Any]:
            raise InvalidHashError("Invalid hash")

    service = ThreatIntelService(virustotal=InvalidHashClient())
    results = service.enrich_results({"SHA256": ["bad_hash"]})

    assert results["hashes"] == []
    assert results["coverage"]["skipped_invalid"] == 1


def test_threat_intel_service_handles_rate_limit():
    class RateLimitClient(FakeVirusTotalClient):
        def lookup_sha256(self, sha256: str) -> dict[str, Any]:
            raise RateLimitExceededError("Rate limit exceeded")

    service = ThreatIntelService(virustotal=RateLimitClient())
    results = service.enrich_results({"SHA256": ["abc123"]})

    assert results["hashes"] == []
    assert results["coverage"]["rate_limited"] is True
    assert results["coverage"]["failed"] == 1
    assert results["status"] == "partial"


def test_threat_intel_service_enriches_ipv4():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    results = service.enrich_results({"ipv4": ["198.51.100.1"]})

    assert len(results["ips"]) == 1
    assert results["ips"][0]["ip"] == "198.51.100.1"
    assert results["ips"][0]["verdict"] == "Malicious"
    assert results["ips"][0]["detection_ratio"] == "4/76"
    assert results["status"] == "ok"
    assert results["coverage"]["succeeded"] == 1
    assert results["coverage"]["requested"] == 1


def test_threat_intel_service_enriches_domains():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    results = service.enrich_results({"domains": ["example.com"]})

    assert len(results["domains"]) == 1
    assert results["domains"][0]["domain"] == "example.com"
    assert results["domains"][0]["verdict"] == "Suspicious"
    assert results["domains"][0]["detection_ratio"] == "0/70"
    assert results["status"] == "ok"
    assert results["coverage"]["succeeded"] == 1
    assert results["coverage"]["requested"] == 1


def test_threat_intel_service_enriches_urls():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    results = service.enrich_results({"urls": ["https://example.com/bad"]})

    assert len(results["urls"]) == 1
    assert results["urls"][0]["url"] == "https://example.com/bad"
    assert results["urls"][0]["verdict"] == "Malicious"
    assert results["urls"][0]["detection_ratio"] == "3/89"
    assert results["status"] == "ok"
    assert results["coverage"]["succeeded"] == 1
    assert results["coverage"]["requested"] == 1


def test_threat_intel_service_enriches_all_four_categories():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    results = service.enrich_results(
        {
            "sha256": ["aaa" * 21 + "a"],
            "ipv4": ["203.0.113.195"],
            "domains": ["c2-server.net"],
            "urls": ["http://malware.com/payload"],
        }
    )

    assert len(results["hashes"]) == 1
    assert len(results["ips"]) == 1
    assert len(results["domains"]) == 1
    assert len(results["urls"]) == 1
    assert results["status"] == "ok"
    assert results["coverage"]["requested"] == 4
    assert results["coverage"]["succeeded"] == 4
    assert results["coverage"]["failed"] == 0


def test_threat_intel_service_handles_invalid_ip():
    class InvalidIPClient(FakeVirusTotalClient):
        def lookup_ip(self, ip: str) -> dict[str, Any]:
            raise InvalidIPError("Invalid IP")

    service = ThreatIntelService(virustotal=InvalidIPClient())
    results = service.enrich_results({"ipv4": ["999.999.999.999"]})

    assert results["ips"] == []
    assert results["coverage"]["skipped_invalid"] == 1


def test_threat_intel_service_handles_invalid_domain():
    class InvalidDomainClient(FakeVirusTotalClient):
        def lookup_domain(self, domain: str) -> dict[str, Any]:
            raise InvalidDomainError("Invalid domain")

    service = ThreatIntelService(virustotal=InvalidDomainClient())
    results = service.enrich_results({"domains": ["-invalid-.com"]})

    assert results["domains"] == []
    assert results["coverage"]["skipped_invalid"] == 1


def test_threat_intel_service_handles_invalid_url():
    class InvalidURLClient(FakeVirusTotalClient):
        def lookup_url(self, url: str) -> dict[str, Any]:
            raise InvalidURLError("Invalid URL")

    service = ThreatIntelService(virustotal=InvalidURLClient())
    results = service.enrich_results({"urls": ["not-a-url"]})

    assert results["urls"] == []
    assert results["coverage"]["skipped_invalid"] == 1


def test_threat_intel_service_handles_ip_rate_limit():
    class IPRateLimitClient(FakeVirusTotalClient):
        def lookup_ip(self, ip: str) -> dict[str, Any]:
            raise RateLimitExceededError("Rate limit")

    service = ThreatIntelService(virustotal=IPRateLimitClient())
    results = service.enrich_results(
        {
            "ipv4": ["1.2.3.4", "5.6.7.8"],
            "domains": ["example.org"],
        }
    )

    assert results["ips"] == []
    assert results["domains"] == []
    assert results["coverage"]["rate_limited"] is True
    assert results["coverage"]["failed"] == 3
    assert results["status"] == "partial"


def test_threat_intel_service_handles_domain_rate_limit():
    class DomainRateLimitClient(FakeVirusTotalClient):
        def lookup_domain(self, domain: str) -> dict[str, Any]:
            raise RateLimitExceededError("Rate limit")

    service = ThreatIntelService(virustotal=DomainRateLimitClient())
    results = service.enrich_results({"domains": ["bad.org"]})

    assert results["domains"] == []
    assert results["coverage"]["rate_limited"] is True
    assert results["coverage"]["failed"] == 1
    assert results["status"] == "partial"


def test_threat_intel_service_handles_url_rate_limit():
    class URLRateLimitClient(FakeVirusTotalClient):
        def lookup_url(self, url: str) -> dict[str, Any]:
            raise RateLimitExceededError("Rate limit")

    service = ThreatIntelService(virustotal=URLRateLimitClient())
    results = service.enrich_results({"urls": ["http://bad.com/1", "http://bad.com/2"]})

    assert results["urls"] == []
    assert results["coverage"]["rate_limited"] is True
    assert results["coverage"]["failed"] == 2
    assert results["status"] == "partial"


def test_threat_intel_service_handles_ip_invalid_api_key():
    class IPInvalidKeyClient(FakeVirusTotalClient):
        def lookup_ip(self, ip: str) -> dict[str, Any]:
            raise InvalidAPIKeyError("Invalid API key")

    service = ThreatIntelService(virustotal=IPInvalidKeyClient())
    results = service.enrich_results(
        {
            "ipv4": ["1.2.3.4"],
            "domains": ["example.com"],
        }
    )

    assert results["ips"] == []
    assert results["domains"] == []
    assert results["coverage"]["invalid_api_key"] is True
    assert results["coverage"]["failed"] == 2
    assert results["status"] == "partial"


def test_threat_intel_service_handles_domain_invalid_api_key():
    class DomainInvalidKeyClient(FakeVirusTotalClient):
        def lookup_domain(self, domain: str) -> dict[str, Any]:
            raise InvalidAPIKeyError("Invalid API key")

    service = ThreatIntelService(virustotal=DomainInvalidKeyClient())
    results = service.enrich_results({"domains": ["example.com"]})

    assert results["domains"] == []
    assert results["coverage"]["invalid_api_key"] is True
    assert results["coverage"]["failed"] == 1
    assert results["status"] == "partial"


def test_threat_intel_service_handles_url_invalid_api_key():
    class URLInvalidKeyClient(FakeVirusTotalClient):
        def lookup_url(self, url: str) -> dict[str, Any]:
            raise InvalidAPIKeyError("Invalid API key")

    service = ThreatIntelService(virustotal=URLInvalidKeyClient())
    results = service.enrich_results({"urls": ["http://example.com"]})

    assert results["urls"] == []
    assert results["coverage"]["invalid_api_key"] is True
    assert results["coverage"]["failed"] == 1
    assert results["status"] == "partial"


def test_threat_intel_service_handles_network_errors_on_ip_and_domain():
    class NetworkErrorClient(FakeVirusTotalClient):
        def lookup_ip(self, ip: str) -> dict[str, Any]:
            raise ThreatIntelTimeoutError("Timeout")

        def lookup_domain(self, domain: str) -> dict[str, Any]:
            raise ThreatIntelConnectionError("Connection dropped")

    service = ThreatIntelService(virustotal=NetworkErrorClient())
    results = service.enrich_results(
        {
            "ipv4": ["1.2.3.4"],
            "domains": ["example.com"],
        }
    )

    assert results["ips"] == []
    assert results["domains"] == []
    assert results["coverage"]["failed"] == 2
    assert results["status"] == "partial"


def test_threat_intel_service_clean_verdict():
    class CleanClient(FakeVirusTotalClient):
        def lookup_ip(self, ip: str) -> dict[str, Any]:
            return {
                "ip": ip,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 80,
                "undetected": 5,
            }

    service = ThreatIntelService(virustotal=CleanClient())
    results = service.enrich_results({"ipv4": ["8.8.8.8"]})

    assert results["ips"][0]["verdict"] == "Clean"
    assert results["ips"][0]["detection_ratio"] == "0/85"


def test_threat_intel_service_no_indicators():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    results = service.enrich_results({})

    assert results["hashes"] == []
    assert results["ips"] == []
    assert results["domains"] == []
    assert results["urls"] == []
    assert results["status"] == "no_indicators"
    assert results["coverage"]["requested"] == 0
    assert results["coverage"]["succeeded"] == 0


# ----------------------------------------------------------------
# Phase 4C, Stage 3: NOT_FOUND vs CLEAN regression coverage.
#
# Design doc SS12 calls this "the central requirement of this
# phase" -- a not-found result must never collapse into "Clean".
# Stage 2 preserved `_format_verdict` byte-for-byte (to keep the
# legacy raw-dict shape intact) but did not carry the `found`-first
# structural fix into it, so `enrich_results`/`lookup_indicator`
# still exhibited the original bug until Stage 3. These tests pin
# the fix down at the `ThreatIntelService` boundary -- the layer
# every real consumer (`analyzer.py`, the GUI page) actually calls
# -- not just at `VirusTotalProvider.lookup()`/`ProviderResult`,
# which `test_virustotal_provider.py` already covers separately and
# which nothing in production reads for these two entry points.
# ----------------------------------------------------------------


def test_threat_intel_service_not_found_is_not_clean():
    class NotFoundClient(FakeVirusTotalClient):
        def lookup_sha256(self, sha256: str) -> dict[str, Any]:
            return {
                "sha256": sha256,
                "found": False,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 0,
                "undetected": 0,
            }

    service = ThreatIntelService(virustotal=NotFoundClient())
    results = service.enrich_results({"SHA256": ["deadbeef"]})

    assert results["hashes"][0]["verdict"] == "Not Found"
    assert results["hashes"][0]["verdict"] != "Clean"
    assert results["hashes"][0]["detection_ratio"] == "N/A"


def test_threat_intel_service_found_and_zero_counts_is_still_clean():
    """
    A genuinely found-and-clean result (VT scanned it, nothing
    flagged) must keep saying "Clean" -- the fix must distinguish
    not-found from clean, not just relabel every zero-count result.
    """

    class FoundCleanClient(FakeVirusTotalClient):
        def lookup_sha256(self, sha256: str) -> dict[str, Any]:
            return {
                "sha256": sha256,
                "found": True,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 70,
                "undetected": 5,
            }

    service = ThreatIntelService(virustotal=FoundCleanClient())
    results = service.enrich_results({"SHA256": ["cafebabe"]})

    assert results["hashes"][0]["verdict"] == "Clean"
    assert results["hashes"][0]["detection_ratio"] == "0/75"


# ----------------------------------------------------------------
# lookup_indicator (Stage 2's GUI-facing single-lookup method).
#
# Previously only ever exercised through a `MagicMock()` in
# tests/gui/test_threat_intel_page_url.py -- which asserts the GUI
# worker calls it correctly, but never runs the real method against
# a real (fake) provider. These tests close that gap by driving the
# actual implementation through `virustotal=` dependency injection,
# the same pattern `enrich_results`'s tests already use.
# ----------------------------------------------------------------


def test_lookup_indicator_returns_legacy_shape_for_each_type():
    fake_client = FakeVirusTotalClient()
    service = ThreatIntelService(virustotal=fake_client)

    sha_result = service.lookup_indicator("sha256", "abc123")
    assert sha_result["sha256"] == "abc123"
    assert sha_result["verdict"] == "Malicious"
    assert fake_client.lookups == ["abc123"]

    ip_result = service.lookup_indicator("ipv4", "198.51.100.1")
    assert ip_result["ip"] == "198.51.100.1"
    assert ip_result["verdict"] == "Malicious"
    assert fake_client.ip_lookups == ["198.51.100.1"]

    domain_result = service.lookup_indicator("domain", "example.com")
    assert domain_result["domain"] == "example.com"
    assert domain_result["verdict"] == "Suspicious"
    assert fake_client.domain_lookups == ["example.com"]

    url_result = service.lookup_indicator("url", "https://example.com/bad")
    assert url_result["url"] == "https://example.com/bad"
    assert url_result["verdict"] == "Malicious"
    assert fake_client.url_lookups == ["https://example.com/bad"]


def test_lookup_indicator_not_found_is_not_clean():
    class NotFoundClient(FakeVirusTotalClient):
        def lookup_url(self, url: str) -> dict[str, Any]:
            return {
                "url": url,
                "found": False,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 0,
                "undetected": 0,
            }

    service = ThreatIntelService(virustotal=NotFoundClient())
    result = service.lookup_indicator("url", "http://never-seen.example")

    assert result["verdict"] == "Not Found"


def test_lookup_indicator_invalid_type_raises_value_error():
    service = ThreatIntelService(virustotal=FakeVirusTotalClient())

    with pytest.raises(ValueError):
        service.lookup_indicator("email", "test@example.com")


def test_lookup_indicator_propagates_errors_unlike_enrich_results():
    """
    Unlike `enrich_results` (which catches and counts errors),
    `lookup_indicator` is for the interactive single-lookup caller
    (the GUI page) and must let the caller handle a single failure
    directly -- exactly as calling `VirusTotalClient.lookup_*`
    directly did before Stage 2.
    """

    class RateLimitClient(FakeVirusTotalClient):
        def lookup_sha256(self, sha256: str) -> dict[str, Any]:
            raise RateLimitExceededError("Rate limit exceeded")

    service = ThreatIntelService(virustotal=RateLimitClient())

    with pytest.raises(RateLimitExceededError):
        service.lookup_indicator("sha256", "a" * 64)


def test_threat_intel_service_context_manager():
    fake_client = FakeVirusTotalClient()
    with ThreatIntelService(virustotal=fake_client) as service:
        # Stage 2: the service's internal dependency is a
        # ThreatIntelProvider wrapping the injected client, not the
        # client itself -- see app/threat_intel/service.py's module
        # docstring. `fake_client.closed` (below) is what actually
        # matters: the injected client is still the one that ends up
        # network-facing and torn down.
        assert service._providers[0]._injected_client is fake_client
    assert fake_client.closed is True