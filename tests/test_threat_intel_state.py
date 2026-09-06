"""
Unit tests for `app.services.threat_intel_state` (Phase 4J-1).

Covers:
  - the six canonical TI_STATE_* values are unchanged from their
    pre-move definitions in `app.services.ioc_detail_context`.
  - `build_investigation_threat_intel_overview()`'s classification
    behavior is unchanged (mirrors the state-by-state coverage in
    `tests/test_investigation_threat_intel_overview.py`, imported
    from the new canonical location instead of the GUI module).
  - the module is importable with no `app.gui` / PySide6 dependency
    anywhere in its own import graph.
  - `app.services.ioc_detail_context` re-exports the exact same
    objects (not a duplicate definition) -- the "exactly one
    canonical definition" requirement.
"""

from __future__ import annotations

import subprocess
import sys

from app.database.models import Investigation
from app.services.threat_intel_state import (
    ENRICHABLE_IOC_TYPES,
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    TI_STATE_UNSUPPORTED_TYPE,
    build_investigation_indicator_states,
    build_investigation_threat_intel_overview,
    build_threat_intel_by_value,
    classify_indicator_ti_state,
)


def _make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="sample_report.txt",
        iocs={"sha256": ["aaa111", "bbb222"], "ipv4": ["1.2.3.4"]},
        threat_intelligence={
            "status": "complete",
            "coverage": {"requested": 2, "succeeded": 2},
        },
        risk_score=10,
        severity="low",
        confidence=0.5,
        ioc_score=5,
        threat_intel_score=5,
        cve_score=0,
        status="open",
    )
    defaults.update(overrides)
    return Investigation(**defaults)


class TestCanonicalStateValues:
    def test_six_states_have_expected_string_values(self) -> None:
        assert TI_STATE_ENRICHED == "enriched"
        assert TI_STATE_NOT_ENRICHED == "not_enriched"
        assert TI_STATE_NO_API_KEY == "no_api_key"
        assert TI_STATE_PROVIDER_ERROR == "provider_error"
        assert TI_STATE_INCOMPLETE_CHECK == "incomplete_check"
        assert TI_STATE_UNSUPPORTED_TYPE == "unsupported_type"


class TestOverviewClassification:
    def test_no_threat_intelligence_recorded_is_not_enriched(self) -> None:
        investigation = _make_investigation(threat_intelligence={})
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=True
        )
        assert result["state"] == TI_STATE_NOT_ENRICHED

    def test_no_indicators_is_not_enriched(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={"status": "no_indicators", "coverage": {}}
        )
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=True
        )
        assert result["state"] == TI_STATE_NOT_ENRICHED
        assert result["short_label"] == "No Enrichable Indicators"

    def test_missing_api_key_is_no_api_key(self) -> None:
        investigation = _make_investigation()
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=False
        )
        assert result["state"] == TI_STATE_NO_API_KEY

    def test_invalid_api_key_is_provider_error(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "partial",
                "coverage": {
                    "requested": 2,
                    "succeeded": 0,
                    "invalid_api_key": True,
                },
            }
        )
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=True
        )
        assert result["state"] == TI_STATE_PROVIDER_ERROR
        assert "Invalid Key" in result["short_label"]

    def test_rate_limited_is_provider_error(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "partial",
                "coverage": {
                    "requested": 2,
                    "succeeded": 1,
                    "rate_limited": True,
                },
            }
        )
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=True
        )
        assert result["state"] == TI_STATE_PROVIDER_ERROR
        assert "Rate Limited" in result["short_label"]

    def test_partial_status_is_incomplete_check(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "partial",
                "coverage": {"requested": 2, "succeeded": 1},
            }
        )
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=True
        )
        assert result["state"] == TI_STATE_INCOMPLETE_CHECK
        assert result["short_label"] == "Partial (1/2)"

    def test_full_coverage_is_enriched(self) -> None:
        investigation = _make_investigation()
        result = build_investigation_threat_intel_overview(
            investigation, api_key_configured=True
        )
        assert result["state"] == TI_STATE_ENRICHED
        assert result["short_label"] == "Enriched (2/2)"


class TestBuildThreatIntelByValue:
    def test_maps_each_category_by_its_own_record_key(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "ok",
                "coverage": {"requested": 4, "succeeded": 4},
                "hashes": [{"sha256": "aaa111", "verdict": "Clean"}],
                "ips": [{"ip": "1.2.3.4", "verdict": "Malicious"}],
                "domains": [{"domain": "evil.example", "verdict": "Clean"}],
                "urls": [{"url": "http://evil.example/x", "verdict": "Clean"}],
            }
        )
        by_value = build_threat_intel_by_value(investigation)
        assert by_value["aaa111"]["verdict"] == "Clean"
        assert by_value["1.2.3.4"]["verdict"] == "Malicious"
        assert by_value["evil.example"]["verdict"] == "Clean"
        assert by_value["http://evil.example/x"]["verdict"] == "Clean"

    def test_empty_threat_intelligence_yields_empty_map(self) -> None:
        investigation = _make_investigation(threat_intelligence={})
        assert build_threat_intel_by_value(investigation) == {}

    def test_records_missing_their_value_key_are_skipped(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={"hashes": [{"verdict": "Clean"}]}
        )
        assert build_threat_intel_by_value(investigation) == {}


class TestClassifyIndicatorTiState:
    def test_unsupported_type_wins_regardless_of_other_signals(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "ok",
                "coverage": {"requested": 1, "succeeded": 1},
            }
        )
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="emails",
            value="a@example.com",
            threat_intel_by_value={},
            api_key_configured=True,
        )
        assert state == TI_STATE_UNSUPPORTED_TYPE

    def test_no_api_key_for_enrichable_type(self) -> None:
        investigation = _make_investigation()
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="sha256",
            value="aaa111",
            threat_intel_by_value={},
            api_key_configured=False,
        )
        assert state == TI_STATE_NO_API_KEY

    def test_record_present_is_enriched(self) -> None:
        investigation = _make_investigation()
        record = {"sha256": "aaa111", "verdict": "Clean"}
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="sha256",
            value="aaa111",
            threat_intel_by_value={"aaa111": record},
            api_key_configured=True,
        )
        assert state == TI_STATE_ENRICHED

    def test_invalid_api_key_coverage_is_provider_error(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "partial",
                "coverage": {
                    "requested": 2,
                    "succeeded": 0,
                    "invalid_api_key": True,
                },
            }
        )
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="sha256",
            value="aaa111",
            threat_intel_by_value={},
            api_key_configured=True,
        )
        assert state == TI_STATE_PROVIDER_ERROR

    def test_rate_limited_coverage_is_provider_error(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "partial",
                "coverage": {
                    "requested": 2,
                    "succeeded": 1,
                    "rate_limited": True,
                },
            }
        )
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="sha256",
            value="bbb222",
            threat_intel_by_value={},
            api_key_configured=True,
        )
        assert state == TI_STATE_PROVIDER_ERROR

    def test_partial_status_without_record_is_incomplete_check(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "partial",
                "coverage": {"requested": 2, "succeeded": 1},
            }
        )
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="sha256",
            value="bbb222",
            threat_intel_by_value={},
            api_key_configured=True,
        )
        assert state == TI_STATE_INCOMPLETE_CHECK

    def test_no_record_and_no_partial_status_is_not_enriched(self) -> None:
        investigation = _make_investigation(
            threat_intelligence={
                "status": "ok",
                "coverage": {"requested": 1, "succeeded": 1},
            }
        )
        state = classify_indicator_ti_state(
            investigation,
            ioc_type="sha256",
            value="ccc333",
            threat_intel_by_value={},
            api_key_configured=True,
        )
        assert state == TI_STATE_NOT_ENRICHED


class TestBuildInvestigationIndicatorStates:
    def test_covers_multiple_ioc_types_grouped_by_type(self) -> None:
        investigation = _make_investigation(
            iocs={
                "sha256": ["aaa111", "bbb222"],
                "ipv4": ["1.2.3.4"],
                "emails": ["a@example.com"],
            },
            threat_intelligence={
                "status": "partial",
                "coverage": {"requested": 3, "succeeded": 1},
                "hashes": [{"sha256": "aaa111", "verdict": "Clean"}],
                "ips": [],
                "domains": [],
                "urls": [],
            },
        )
        states = build_investigation_indicator_states(
            investigation, api_key_configured=True
        )
        assert states == {
            "sha256": {
                "aaa111": TI_STATE_ENRICHED,
                "bbb222": TI_STATE_INCOMPLETE_CHECK,
            },
            "ipv4": {"1.2.3.4": TI_STATE_INCOMPLETE_CHECK},
            "emails": {"a@example.com": TI_STATE_UNSUPPORTED_TYPE},
        }

    def test_no_iocs_yields_empty_states(self) -> None:
        investigation = _make_investigation(iocs={})
        states = build_investigation_indicator_states(
            investigation, api_key_configured=True
        )
        assert states == {}

    def test_does_not_mutate_raw_threat_intelligence(self) -> None:
        ti_payload = {
            "status": "ok",
            "coverage": {"requested": 1, "succeeded": 1},
            "hashes": [{"sha256": "aaa111", "verdict": "Clean"}],
        }
        investigation = _make_investigation(
            iocs={"sha256": ["aaa111"]},
            threat_intelligence=ti_payload,
        )
        build_investigation_indicator_states(investigation, api_key_configured=True)
        assert investigation.threat_intelligence == ti_payload


class TestEnrichableIocTypesConstant:
    def test_matches_the_four_enriched_categories(self) -> None:
        assert ENRICHABLE_IOC_TYPES == frozenset(
            {"sha256", "ipv4", "domains", "urls"}
        )


class TestFrameworkIndependence:
    def test_module_has_no_app_gui_or_qt_import(self) -> None:
        """
        Import the module in a fresh subprocess with `app.gui` and
        every PySide6 submodule poisoned to raise on import -- if
        `app.services.threat_intel_state` (or anything it imports)
        reaches into either, this fails loudly instead of relying on
        `sys.modules` merely happening to already be populated by an
        earlier test.
        """

        probe = (
            "import sys\n"
            "class _Blocker:\n"
            "    def find_module(self, name, path=None):\n"
            "        if name == 'app.gui' or name.startswith('app.gui.'):\n"
            "            raise ImportError(f'blocked: {name}')\n"
            "        if name == 'PySide6' or name.startswith('PySide6.'):\n"
            "            raise ImportError(f'blocked: {name}')\n"
            "        return None\n"
            "sys.meta_path.insert(0, _Blocker())\n"
            "import app.services.threat_intel_state\n"
            "print('OK')\n"
        )
        completed = subprocess.run(
            [sys.executable, "-c", probe],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert completed.returncode == 0, completed.stderr
        assert "OK" in completed.stdout


class TestGuiCompatibilityReExport:
    def test_gui_module_re_exports_the_same_objects(self) -> None:
        """
        `app.services.ioc_detail_context` must expose the exact
        same constants/function objects as
        `app.services.threat_intel_state`, not a second, independent
        definition -- this is the "exactly one canonical definition"
        requirement.
        """

        from app.gui.services import ioc_detail_context

        assert ioc_detail_context.TI_STATE_ENRICHED is TI_STATE_ENRICHED
        assert ioc_detail_context.TI_STATE_NOT_ENRICHED is TI_STATE_NOT_ENRICHED
        assert ioc_detail_context.TI_STATE_NO_API_KEY is TI_STATE_NO_API_KEY
        assert (
            ioc_detail_context.TI_STATE_PROVIDER_ERROR is TI_STATE_PROVIDER_ERROR
        )
        assert (
            ioc_detail_context.TI_STATE_INCOMPLETE_CHECK
            is TI_STATE_INCOMPLETE_CHECK
        )
        assert (
            ioc_detail_context.TI_STATE_UNSUPPORTED_TYPE
            is TI_STATE_UNSUPPORTED_TYPE
        )
        assert (
            ioc_detail_context.build_investigation_threat_intel_overview
            is build_investigation_threat_intel_overview
        )
