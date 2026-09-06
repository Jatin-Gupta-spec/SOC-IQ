"""
Focused tests for Phase 4K-1: deriving typed `Verdict` values from
already-persisted raw provider responses
(`app.threat_intel.verdict_from_persisted`).

Covers the acceptance conditions the phase's contract note lists:
  1. real CLEAN raw response -> CLEAN
  2. real NOT_FOUND raw response -> NOT_FOUND
  3. explicit NOT_FOUND != CLEAN
  4. MALICIOUS remains MALICIOUS
  5. SUSPICIOUS remains SUSPICIOUS
  6. provider failure/unavailable/no-key/unsupported information is
     not silently converted to CLEAN (there is no such information in
     the persisted shape at all -- covered here by confirming a
     record with no `found` key never becomes CLEAN)
  7. old persisted data without sufficient verdict information does
     not crash and is not fabricated into CLEAN or NOT_FOUND
  8. existing response fields remain unchanged (covered in
     tests/test_application_layer.py's GetThreatIntelligenceCommandHandlerTests)
  9. get_threat_intelligence performs no provider/network lookup
     (also covered in tests/test_application_layer.py; this module's
     own import graph is checked here for absence of any provider
     network-call surface)
 10. the extracted helper (`translate_verdict`) preserves existing
     provider translation behavior (see
     tests/test_virustotal_provider.py's TestVerdictTranslation,
     unmodified and still passing against the refactored code)
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import Investigation
from app.threat_intel.models import Verdict
from app.threat_intel.verdict_from_persisted import (
    build_investigation_typed_verdicts,
    derive_typed_verdict,
)


def _make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="phase4k1_test_report.txt",
        iocs={},
        threat_intelligence={},
        risk_score=0,
        severity="LOW",
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    return Investigation(**defaults)


def _real_found_record(malicious=0, suspicious=0, harmless=60, undetected=10) -> dict:
    return {
        "sha256": "a" * 64,
        "found": True,
        "malicious": malicious,
        "suspicious": suspicious,
        "harmless": harmless,
        "undetected": undetected,
        "reputation": 0,
        "permalink": "https://www.virustotal.com/gui/file/aaaa",
        "verdict": "Clean",  # legacy string -- must be ignored, not parsed
        "detection_ratio": "0/70",
    }


def _real_not_found_record() -> dict:
    return {
        "ip": "1.2.3.4",
        "found": False,
        "malicious": 0,
        "suspicious": 0,
        "harmless": 0,
        "undetected": 0,
        "reputation": None,
        "permalink": "https://www.virustotal.com/gui/ip-address/1.2.3.4",
        "verdict": "Not Found",
        "detection_ratio": "N/A",
    }


class TestDeriveTypedVerdict:
    """`derive_typed_verdict` acceptance conditions 1-7."""

    def test_real_clean_response_yields_clean(self) -> None:
        record = _real_found_record(malicious=0, suspicious=0)
        assert derive_typed_verdict(record) == Verdict.CLEAN.value

    def test_real_not_found_response_yields_not_found(self) -> None:
        record = _real_not_found_record()
        assert derive_typed_verdict(record) == Verdict.NOT_FOUND.value

    def test_not_found_is_never_clean(self) -> None:
        record = _real_not_found_record()
        result = derive_typed_verdict(record)
        assert result == Verdict.NOT_FOUND.value
        assert result != Verdict.CLEAN.value

    def test_malicious_remains_malicious(self) -> None:
        record = _real_found_record(malicious=5, suspicious=1)
        assert derive_typed_verdict(record) == Verdict.MALICIOUS.value

    def test_suspicious_remains_suspicious_when_no_malicious(self) -> None:
        record = _real_found_record(malicious=0, suspicious=3)
        assert derive_typed_verdict(record) == Verdict.SUSPICIOUS.value

    def test_record_missing_found_key_is_not_fabricated_as_clean(self) -> None:
        # A legacy persisted record with only the display verdict
        # string and no raw counts at all -- pre-Stage-3 shape.
        legacy_record = {"ip": "1.2.3.4", "verdict": "Malicious"}
        assert derive_typed_verdict(legacy_record) is None

    def test_record_missing_found_key_is_not_fabricated_as_not_found(self) -> None:
        legacy_record = {"sha256": "a" * 64, "verdict": "Clean"}
        result = derive_typed_verdict(legacy_record)
        assert result is None
        assert result != Verdict.NOT_FOUND.value

    def test_no_record_at_all_yields_none_without_crashing(self) -> None:
        assert derive_typed_verdict(None) is None
        assert derive_typed_verdict({}) is None

    def test_legacy_verdict_string_is_never_read(self) -> None:
        """
        A record whose legacy `verdict` string says one thing but
        whose raw counts say another must be classified from the raw
        counts, proving the legacy string is never parsed to produce
        the typed value.
        """
        contradictory_record = _real_found_record(malicious=1, suspicious=0)
        contradictory_record["verdict"] = "Clean"  # deliberately wrong

        assert derive_typed_verdict(contradictory_record) == Verdict.MALICIOUS.value


class TestBuildInvestigationTypedVerdicts:
    def test_grouped_by_ioc_type_matching_iocs_shape(self) -> None:
        investigation = _make_investigation(
            iocs={"sha256": ["aaa111"], "ipv4": ["1.2.3.4"]},
            threat_intelligence={
                "status": "ok",
                "coverage": {"requested": 2, "succeeded": 2},
                "hashes": [
                    {
                        "sha256": "aaa111",
                        "found": True,
                        "malicious": 3,
                        "suspicious": 0,
                        "harmless": 10,
                        "undetected": 0,
                        "verdict": "Malicious",
                    }
                ],
                "ips": [
                    {
                        "ip": "1.2.3.4",
                        "found": False,
                        "malicious": 0,
                        "suspicious": 0,
                        "harmless": 0,
                        "undetected": 0,
                        "verdict": "Not Found",
                    }
                ],
            },
        )

        result = build_investigation_typed_verdicts(investigation)

        assert result == {
            "sha256": {"aaa111": Verdict.MALICIOUS.value},
            "ipv4": {"1.2.3.4": Verdict.NOT_FOUND.value},
        }

    def test_indicator_with_no_persisted_record_is_none(self) -> None:
        investigation = _make_investigation(
            iocs={"sha256": ["aaa111", "bbb222"]},
            threat_intelligence={
                "status": "partial",
                "coverage": {"requested": 2, "succeeded": 1},
                "hashes": [
                    {
                        "sha256": "aaa111",
                        "found": True,
                        "malicious": 0,
                        "suspicious": 0,
                        "harmless": 5,
                        "undetected": 0,
                        "verdict": "Clean",
                    }
                ],
            },
        )

        result = build_investigation_typed_verdicts(investigation)

        assert result == {
            "sha256": {"aaa111": Verdict.CLEAN.value, "bbb222": None}
        }

    def test_old_persisted_investigation_without_raw_fields_does_not_crash(self) -> None:
        # Mirrors tests/test_application_layer.py's pre-Stage-3-shaped
        # ti_payload fixtures: a record with only the legacy display
        # string, no raw counts.
        investigation = _make_investigation(
            iocs={"ipv4": ["1.2.3.4"]},
            threat_intelligence={
                "status": "ok",
                "coverage": {"requested": 1, "succeeded": 1},
                "ips": [{"ip": "1.2.3.4", "verdict": "Malicious"}],
            },
        )

        result = build_investigation_typed_verdicts(investigation)

        assert result == {"ipv4": {"1.2.3.4": None}}

    def test_no_iocs_yields_empty_dict(self) -> None:
        investigation = _make_investigation(iocs={})

        assert build_investigation_typed_verdicts(investigation) == {}

    def test_unsupported_ioc_type_yields_none_not_a_crash(self) -> None:
        investigation = _make_investigation(
            iocs={"emails": ["a@example.com"]},
            threat_intelligence={},
        )

        result = build_investigation_typed_verdicts(investigation)

        assert result == {"emails": {"a@example.com": None}}


class TestNoNetworkOrProviderSurfaceImported:
    """
    Acceptance condition 9 (no provider/network lookup): this
    module's import graph must not reach any provider network-call
    surface -- `ThreatIntelProvider.lookup`, `ThreatIntelService.
    enrich_results` / `.lookup_indicator` / `._format_verdict`, or
    `VirusTotalProvider.lookup_raw` -- confirming the module only
    imports the pure translation helper and the pure persisted-data
    reader, not anything that can make a request.
    """

    def test_module_does_not_import_threat_intel_service(self) -> None:
        import app.threat_intel.verdict_from_persisted as module

        assert not hasattr(module, "ThreatIntelService")

    def test_module_does_not_call_provider_lookup_methods(self) -> None:
        import ast
        import inspect

        import app.threat_intel.verdict_from_persisted as module

        source = inspect.getsource(module)
        tree = ast.parse(source)

        called_attribute_names = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }

        forbidden = {"lookup", "lookup_raw", "_format_verdict", "enrich_results"}
        assert called_attribute_names.isdisjoint(forbidden)
