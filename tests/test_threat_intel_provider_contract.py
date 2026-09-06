"""
Provider-contract compliance test (Phase 4C, Stage 1, design doc
SS15.4).

Runs a structural + behavioral compliance checklist against any
`ThreatIntelProvider` implementation, so a future second provider's
onboarding (SS18) gets this coverage for free instead of needing
bespoke tests reinvented per provider. `VirusTotalProvider` is the
only implementation exercised in Stage 1.
"""

from __future__ import annotations

import asyncio

import pytest

from app.threat_intel.models import IOC, IOCType, ProviderResult, Verdict
from app.threat_intel.provider import ThreatIntelProvider
from app.threat_intel.virustotal_provider import VirusTotalProvider


class FakeVirusTotalClient:
    """
    Minimal stand-in for VirusTotalClient used only to exercise
    VirusTotalProvider's contract compliance -- not a substitute for
    tests/test_virustotal_provider.py's behavioral coverage.
    """

    def __init__(self, result: dict) -> None:
        self._result = result
        self.closed = False

    def lookup_sha256(self, sha256: str) -> dict:
        return dict(self._result, sha256=sha256)

    def lookup_ip(self, ip: str) -> dict:
        return dict(self._result, ip=ip)

    def lookup_domain(self, domain: str) -> dict:
        return dict(self._result, domain=domain)

    def lookup_url(self, url: str) -> dict:
        return dict(self._result, url=url)

    def close(self) -> None:
        self.closed = True


def run_contract_checks(provider: ThreatIntelProvider) -> None:
    """
    Shared checklist any ThreatIntelProvider implementation must
    satisfy. Call this from a provider-specific test module with a
    provider instance already configured to succeed on at least one
    supported IOC type.
    """

    # Structural compliance with the Protocol.
    assert isinstance(provider, ThreatIntelProvider)
    assert isinstance(provider.name, str) and provider.name
    assert isinstance(provider.supported_ioc_types, set)
    assert provider.supported_ioc_types, "must declare at least one supported IOC type"
    assert all(isinstance(t, IOCType) for t in provider.supported_ioc_types)

    # is_configured() must be synchronous (no coroutine) and boolean.
    configured = provider.is_configured()
    assert isinstance(configured, bool)
    assert configured is True

    # lookup() on a supported type must return a ProviderResult, not
    # raise, for a normal successful call.
    supported_type = next(iter(provider.supported_ioc_types))
    ioc = IOC(type=supported_type, value="contract-test-value")
    result = asyncio.run(provider.lookup(ioc))
    assert isinstance(result, ProviderResult)
    assert result.provider == provider.name
    assert result.ioc == ioc
    assert isinstance(result.verdict, Verdict)

    # lookup() on an unsupported type must not raise -- it must
    # return an UNSUPPORTED-verdict ProviderResult (design doc SS7).
    all_types = set(IOCType)
    unsupported_types = all_types - provider.supported_ioc_types
    if unsupported_types:
        unsupported_ioc = IOC(
            type=next(iter(unsupported_types)),
            value="contract-test-unsupported",
        )
        unsupported_result = asyncio.run(provider.lookup(unsupported_ioc))
        assert isinstance(unsupported_result, ProviderResult)
        assert unsupported_result.verdict is Verdict.UNSUPPORTED


class TestVirusTotalProviderContractCompliance:
    def test_virustotal_provider_satisfies_contract(self) -> None:
        fake_client = FakeVirusTotalClient(
            {
                "found": True,
                "malicious": 0,
                "suspicious": 0,
                "harmless": 70,
                "undetected": 5,
                "reputation": 0,
                "permalink": "https://www.virustotal.com/gui/file/aaaa",
            }
        )
        provider = VirusTotalProvider(client=fake_client)
        run_contract_checks(provider)

    def test_unconfigured_provider_is_not_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.settings.models import ApplicationSettings
        from app.settings.service import SettingsService

        monkeypatch.setattr(
            SettingsService,
            "load_settings",
            lambda self: ApplicationSettings(virustotal_api_key=""),
        )

        provider = VirusTotalProvider()
        assert provider.is_configured() is False
