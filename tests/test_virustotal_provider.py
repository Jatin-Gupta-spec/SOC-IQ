"""
Tests for app.threat_intel.virustotal_provider.VirusTotalProvider
(Phase 4C, Stage 1).

All lookups go through a FakeVirusTotalClient injected via the
`client=` constructor argument -- no real network calls, and
`app.threat_intel.virustotal.VirusTotalClient` itself is never
touched by these tests (it is exercised separately, unchanged, by
tests/test_virustotal.py).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidHashError,
    InvalidIPError,
    MissingAPIKeyError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)
from app.threat_intel.models import IOC, IOCType, Verdict
from app.threat_intel.virustotal_provider import VirusTotalProvider

VALID_SHA256 = "a" * 64
VALID_IP = "192.0.2.1"
VALID_DOMAIN = "malware.example.com"
VALID_URL = "http://malware.example.com/payload.exe"


class ScriptedVirusTotalClient:
    """
    Fake VirusTotalClient whose lookup_* methods return a scripted
    result or raise a scripted exception, one per IOC type.
    """

    def __init__(self) -> None:
        self.sha256_result: dict[str, Any] | Exception | None = None
        self.ip_result: dict[str, Any] | Exception | None = None
        self.domain_result: dict[str, Any] | Exception | None = None
        self.url_result: dict[str, Any] | Exception | None = None
        self.calls: list[tuple[str, str]] = []
        self.closed = False

    def _resolve(self, category: str, value: str, scripted):
        self.calls.append((category, value))
        if isinstance(scripted, Exception):
            raise scripted
        return scripted

    def lookup_sha256(self, sha256: str) -> dict[str, Any]:
        return self._resolve("sha256", sha256, self.sha256_result)

    def lookup_ip(self, ip: str) -> dict[str, Any]:
        return self._resolve("ip", ip, self.ip_result)

    def lookup_domain(self, domain: str) -> dict[str, Any]:
        return self._resolve("domain", domain, self.domain_result)

    def lookup_url(self, url: str) -> dict[str, Any]:
        return self._resolve("url", url, self.url_result)

    def close(self) -> None:
        self.closed = True


def run(coro):
    return asyncio.run(coro)


def found_payload(
    malicious=0,
    suspicious=0,
    harmless=60,
    undetected=10,
    reputation=0,
    permalink="https://www.virustotal.com/gui/file/aaaa",
) -> dict[str, Any]:
    return {
        "found": True,
        "malicious": malicious,
        "suspicious": suspicious,
        "harmless": harmless,
        "undetected": undetected,
        "reputation": reputation,
        "permalink": permalink,
    }


def not_found_payload(
    permalink="https://www.virustotal.com/gui/file/aaaa",
) -> dict[str, Any]:
    return {
        "found": False,
        "malicious": 0,
        "suspicious": 0,
        "harmless": 0,
        "undetected": 0,
        "reputation": None,
        "permalink": permalink,
    }


class TestVerdictTranslation:
    """The central requirement of Phase 4C (design doc SS12): NOT_FOUND
    must never collapse into CLEAN."""

    def test_not_found_maps_to_not_found_not_clean(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = not_found_payload()
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.NOT_FOUND
        assert result.verdict is not Verdict.CLEAN

    def test_found_and_clean(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload(malicious=0, suspicious=0, harmless=80, undetected=5)
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.CLEAN
        assert result.raw_detection_ratio == "0/85"

    def test_found_and_malicious(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload(malicious=10, suspicious=1, harmless=60, undetected=0)
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.MALICIOUS
        assert result.raw_detection_ratio == "10/71"

    def test_found_and_suspicious_when_no_malicious(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload(malicious=0, suspicious=3, harmless=60, undetected=0)
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.SUSPICIOUS

    def test_malicious_precedence_over_suspicious(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload(malicious=1, suspicious=5, harmless=60, undetected=0)
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.MALICIOUS

    def test_detection_ratio_is_n_a_when_total_zero(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload(malicious=0, suspicious=0, harmless=0, undetected=0)
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.CLEAN
        assert result.raw_detection_ratio == "N/A"

    def test_source_url_carries_over_permalink(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload(permalink="https://www.virustotal.com/gui/file/abc123")
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.source_url == "https://www.virustotal.com/gui/file/abc123"

    def test_provider_name_and_ioc_echoed(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = found_payload()
        provider = VirusTotalProvider(client=client)
        ioc = IOC(IOCType.SHA256, VALID_SHA256)

        result = run(provider.lookup(ioc))

        assert result.provider == "virustotal"
        assert result.ioc == ioc


class TestIOCTypeRouting:
    def test_ipv4_routes_to_lookup_ip(self) -> None:
        client = ScriptedVirusTotalClient()
        client.ip_result = found_payload()
        provider = VirusTotalProvider(client=client)

        run(provider.lookup(IOC(IOCType.IPV4, VALID_IP)))

        assert client.calls == [("ip", VALID_IP)]

    def test_domain_routes_to_lookup_domain(self) -> None:
        client = ScriptedVirusTotalClient()
        client.domain_result = found_payload()
        provider = VirusTotalProvider(client=client)

        run(provider.lookup(IOC(IOCType.DOMAIN, VALID_DOMAIN)))

        assert client.calls == [("domain", VALID_DOMAIN)]

    def test_url_routes_to_lookup_url(self) -> None:
        client = ScriptedVirusTotalClient()
        client.url_result = found_payload()
        provider = VirusTotalProvider(client=client)

        run(provider.lookup(IOC(IOCType.URL, VALID_URL)))

        assert client.calls == [("url", VALID_URL)]

    def test_unsupported_type_short_circuits_without_calling_client(self) -> None:
        client = ScriptedVirusTotalClient()
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.CVE, "CVE-2024-0001")))

        assert result.verdict is Verdict.UNSUPPORTED
        assert client.calls == []


class TestErrorTranslation:
    """Design doc SS10: transport-level failures become error-shaped
    ProviderResults with error_detail populated, rather than raising."""

    def test_rate_limit_exceeded_maps_to_rate_limited_verdict(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = RateLimitExceededError("rate limited")
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.RATE_LIMITED
        assert result.error_detail == "rate limited"

    def test_invalid_api_key_maps_to_no_api_key_verdict(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = InvalidAPIKeyError("key rejected")
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.NO_API_KEY
        assert result.error_detail == "key rejected"

    def test_timeout_maps_to_unavailable_verdict(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = ThreatIntelTimeoutError("timed out")
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.UNAVAILABLE

    def test_connection_error_maps_to_unavailable_verdict(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = ThreatIntelConnectionError("no connection")
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.UNAVAILABLE

    def test_unexpected_response_maps_to_error_verdict(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = UnexpectedAPIResponseError("malformed")
        provider = VirusTotalProvider(client=client)

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.ERROR

    def test_missing_api_key_at_construction_maps_to_no_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No injected client and no explicit api_key: provider must
        # lazily construct a real VirusTotalClient on first lookup
        # and translate its MissingAPIKeyError into a NO_API_KEY
        # ProviderResult rather than letting it propagate.
        # SettingsService is patched (rather than relying on this
        # machine's real settings file) so the "no key configured"
        # case is deterministic.
        from app.settings.models import ApplicationSettings
        from app.settings.service import SettingsService

        monkeypatch.setattr(
            SettingsService,
            "load_settings",
            lambda self: ApplicationSettings(virustotal_api_key=""),
        )

        provider = VirusTotalProvider()

        result = run(provider.lookup(IOC(IOCType.SHA256, VALID_SHA256)))

        assert result.verdict is Verdict.NO_API_KEY


class TestValidationErrorsPropagate:
    """Design doc SS10: malformed-IOC validation errors are call-site
    bugs and must keep propagating as exceptions, not become a
    ProviderResult verdict."""

    def test_invalid_sha256_raises(self) -> None:
        client = ScriptedVirusTotalClient()
        client.sha256_result = InvalidHashError("bad hash")
        provider = VirusTotalProvider(client=client)

        with pytest.raises(InvalidHashError):
            run(provider.lookup(IOC(IOCType.SHA256, "not-a-hash")))

    def test_invalid_ip_raises(self) -> None:
        client = ScriptedVirusTotalClient()
        client.ip_result = InvalidIPError("bad ip")
        provider = VirusTotalProvider(client=client)

        with pytest.raises(InvalidIPError):
            run(provider.lookup(IOC(IOCType.IPV4, "not-an-ip")))


class TestIsConfigured:
    def test_injected_client_is_always_configured(self) -> None:
        client = ScriptedVirusTotalClient()
        provider = VirusTotalProvider(client=client)
        assert provider.is_configured() is True

    def test_explicit_api_key_is_configured(self) -> None:
        provider = VirusTotalProvider(api_key="some-key")
        assert provider.is_configured() is True

    def test_no_key_no_client_falls_back_to_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.settings.models import ApplicationSettings
        from app.settings.service import SettingsService

        monkeypatch.setattr(
            SettingsService,
            "load_settings",
            lambda self: ApplicationSettings(virustotal_api_key="from-settings"),
        )

        provider = VirusTotalProvider()
        assert provider.is_configured() is True

    def test_is_configured_never_raises_even_if_settings_broken(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.settings.service import SettingsService

        def broken_load(self):
            raise RuntimeError("disk is on fire")

        monkeypatch.setattr(SettingsService, "load_settings", broken_load)

        provider = VirusTotalProvider()
        assert provider.is_configured() is False


class TestNameAndSupportedTypes:
    def test_name_is_virustotal(self) -> None:
        provider = VirusTotalProvider(client=ScriptedVirusTotalClient())
        assert provider.name == "virustotal"

    def test_supported_types_match_current_four_lookup_methods(self) -> None:
        # Design doc SS7 "Current (CONFIRMED)": exactly SHA256, IPv4,
        # Domain, URL -- matching the four VirusTotalClient.lookup_*
        # methods that exist today. Widening this is explicitly out
        # of scope for Stage 1.
        provider = VirusTotalProvider(client=ScriptedVirusTotalClient())
        assert provider.supported_ioc_types == {
            IOCType.SHA256,
            IOCType.IPV4,
            IOCType.DOMAIN,
            IOCType.URL,
        }


class TestCloseAndContextManager:
    def test_close_closes_injected_client(self) -> None:
        client = ScriptedVirusTotalClient()
        provider = VirusTotalProvider(client=client)

        provider.close()

        assert client.closed is True

    def test_close_is_safe_before_any_lookup_with_no_client(self) -> None:
        provider = VirusTotalProvider(api_key="unused")
        # No lookup has happened, so no client was ever lazily
        # constructed -- close() must not raise.
        provider.close()

    def test_async_context_manager_closes_on_exit(self) -> None:
        client = ScriptedVirusTotalClient()

        async def scenario() -> None:
            async with VirusTotalProvider(client=client) as provider:
                assert provider is not None

        run(scenario())

        assert client.closed is True
