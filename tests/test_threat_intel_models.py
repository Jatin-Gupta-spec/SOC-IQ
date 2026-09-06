"""
Tests for app.threat_intel.models (Phase 4C, Stage 1).

Covers the Verdict/ProviderResult/IOC data models and the
`aggregate()` policy function, independent of any real or fake
provider -- per design doc SS15.2's "aggregation-policy unit tests"
requirement.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.threat_intel.models import (
    IOC,
    LEGACY_VERDICT_STRINGS,
    IOCType,
    ProviderResult,
    Verdict,
    aggregate,
)


def make_result(verdict: Verdict, provider: str = "virustotal") -> ProviderResult:
    return ProviderResult(
        provider=provider,
        ioc=IOC(type=IOCType.SHA256, value="a" * 64),
        verdict=verdict,
        confidence=None,
        raw_detection_ratio=None,
        source_url=None,
        queried_at=datetime.now(UTC),
    )


class TestIOCAndIOCType:
    def test_ioc_is_frozen(self) -> None:
        ioc = IOC(type=IOCType.IPV4, value="192.0.2.1")
        assert ioc.type is IOCType.IPV4
        assert ioc.value == "192.0.2.1"

    def test_all_ten_extractor_categories_represented(self) -> None:
        # Mirrors app/extractor.py::IOC_PATTERNS's ten categories
        # (design doc SS2.5/SS7) -- not every one is enrichable by
        # every provider, but every one must be representable.
        assert {member.value for member in IOCType} == {
            "sha256",
            "ipv4",
            "domain",
            "url",
            "email",
            "md5",
            "sha1",
            "cve",
            "windows_file_path",
            "windows_registry_key",
        }


class TestLegacyVerdictStrings:
    def test_legacy_strings_preserved_exactly(self) -> None:
        # Byte-for-byte match with today's
        # ThreatIntelService._format_verdict output (design doc SS5).
        assert LEGACY_VERDICT_STRINGS[Verdict.MALICIOUS] == "Malicious"
        assert LEGACY_VERDICT_STRINGS[Verdict.SUSPICIOUS] == "Suspicious"
        assert LEGACY_VERDICT_STRINGS[Verdict.CLEAN] == "Clean"

    def test_not_found_string_is_new_and_distinct(self) -> None:
        not_found_string = LEGACY_VERDICT_STRINGS[Verdict.NOT_FOUND]
        assert not_found_string == "Not Found"
        assert not_found_string not in (
            "Malicious",
            "Suspicious",
            "Clean",
        )


class TestAggregateSingleProvider:
    """The degenerate case Phase 4C actually ships (design doc SS9)."""

    def test_single_malicious(self) -> None:
        assert aggregate([make_result(Verdict.MALICIOUS)]) is Verdict.MALICIOUS

    def test_single_suspicious(self) -> None:
        assert aggregate([make_result(Verdict.SUSPICIOUS)]) is Verdict.SUSPICIOUS

    def test_single_clean(self) -> None:
        assert aggregate([make_result(Verdict.CLEAN)]) is Verdict.CLEAN

    def test_single_not_found(self) -> None:
        assert aggregate([make_result(Verdict.NOT_FOUND)]) is Verdict.NOT_FOUND

    def test_single_rate_limited(self) -> None:
        assert aggregate([make_result(Verdict.RATE_LIMITED)]) is Verdict.RATE_LIMITED

    def test_single_no_api_key(self) -> None:
        assert aggregate([make_result(Verdict.NO_API_KEY)]) is Verdict.NO_API_KEY

    def test_single_unavailable(self) -> None:
        assert aggregate([make_result(Verdict.UNAVAILABLE)]) is Verdict.UNAVAILABLE

    def test_single_error(self) -> None:
        assert aggregate([make_result(Verdict.ERROR)]) is Verdict.ERROR

    def test_single_unsupported(self) -> None:
        assert aggregate([make_result(Verdict.UNSUPPORTED)]) is Verdict.UNSUPPORTED


class TestAggregateEmptyInput:
    def test_no_providers_is_unsupported(self) -> None:
        assert aggregate([]) is Verdict.UNSUPPORTED


class TestAggregateContentPrecedence:
    """Malicious > Suspicious > Clean > (all) Not Found, never CLEAN
    from a not-found result (design doc SS9/SS12 -- the central
    correctness requirement of this phase)."""

    def test_malicious_beats_everything(self) -> None:
        results = [
            make_result(Verdict.CLEAN),
            make_result(Verdict.SUSPICIOUS),
            make_result(Verdict.MALICIOUS),
            make_result(Verdict.NOT_FOUND),
        ]
        assert aggregate(results) is Verdict.MALICIOUS

    def test_suspicious_beats_clean_and_not_found(self) -> None:
        results = [
            make_result(Verdict.CLEAN),
            make_result(Verdict.NOT_FOUND),
            make_result(Verdict.SUSPICIOUS),
        ]
        assert aggregate(results) is Verdict.SUSPICIOUS

    def test_clean_beats_not_found(self) -> None:
        results = [make_result(Verdict.NOT_FOUND), make_result(Verdict.CLEAN)]
        assert aggregate(results) is Verdict.CLEAN

    def test_all_not_found_is_not_found_not_clean(self) -> None:
        # This is the precise scenario SS9's pseudocode calls out:
        # "do NOT default to CLEAN here."
        results = [make_result(Verdict.NOT_FOUND), make_result(Verdict.NOT_FOUND)]
        assert aggregate(results) is Verdict.NOT_FOUND
        assert aggregate(results) is not Verdict.CLEAN


class TestAggregateAbsencePrecedence:
    """Mixed error/absence states with no content verdict present."""

    def test_rate_limited_beats_no_api_key(self) -> None:
        results = [make_result(Verdict.NO_API_KEY), make_result(Verdict.RATE_LIMITED)]
        assert aggregate(results) is Verdict.RATE_LIMITED

    def test_no_api_key_beats_unavailable(self) -> None:
        results = [make_result(Verdict.UNAVAILABLE), make_result(Verdict.NO_API_KEY)]
        assert aggregate(results) is Verdict.NO_API_KEY

    def test_unavailable_beats_error(self) -> None:
        results = [make_result(Verdict.ERROR), make_result(Verdict.UNAVAILABLE)]
        assert aggregate(results) is Verdict.UNAVAILABLE

    def test_error_beats_not_found(self) -> None:
        results = [make_result(Verdict.NOT_FOUND), make_result(Verdict.ERROR)]
        assert aggregate(results) is Verdict.ERROR

    def test_not_found_beats_unsupported_when_mixed(self) -> None:
        results = [make_result(Verdict.UNSUPPORTED), make_result(Verdict.NOT_FOUND)]
        assert aggregate(results) is Verdict.NOT_FOUND

    def test_unsupported_is_last_resort(self) -> None:
        results = [make_result(Verdict.UNSUPPORTED)]
        assert aggregate(results) is Verdict.UNSUPPORTED
