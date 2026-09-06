"""
Unit tests for `app.services.ioc_detail_context` and
`app.services.ioc_significance`.

These are plain-Python tests (no Qt/PySide6 dependency) covering
the logic that decides what threat-intelligence state to show for
a given IOC -- enriched, not enriched, missing API key, provider
error, incomplete check, or an unsupported indicator type -- and
the risk-significance banding derived from the existing scoring
weights.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.services.ioc_detail_context import (
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    TI_STATE_UNSUPPORTED_TYPE,
    build_ioc_detail_context,
)
from app.services.ioc_significance import (
    ioc_type_significance,
    ioc_type_title,
    ioc_type_weight,
)
from app.scoring.engine import RiskScoringEngine


def _make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="sample_report.txt",
        iocs={
            "sha256": ["aaa111", "bbb222"],
            "ipv4": ["1.2.3.4"],
        },
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "aaa111",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                    "reputation": -20,
                    "last_analysis_date": "2026-01-01T00:00:00+00:00",
                },
            ],
            "status": "ok",
            "coverage": {
                "status": "ok",
                "requested": 2,
                "succeeded": 2,
                "failed": 0,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": False,
            },
        },
        risk_score=42,
        severity="HIGH",
        confidence=0.8,
        ioc_score=10,
        threat_intel_score=25,
        cve_score=0,
        analyzed_at=datetime(2026, 1, 1, tzinfo=UTC),
        investigation_id=7,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


# ==========================================================
# ioc_significance
# ==========================================================


def test_significance_weights_come_from_scoring_engine():
    for ioc_type, weight in RiskScoringEngine.IOC_WEIGHTS.items():
        assert ioc_type_weight(ioc_type) == weight


def test_significance_banding_high_for_sha256_and_cves():
    assert ioc_type_significance("sha256") == "High"
    assert ioc_type_significance("cves") == "High"


def test_significance_banding_low_for_ipv4():
    assert ioc_type_significance("ipv4") == "Low"


def test_significance_banding_unknown_type_is_informational():
    assert ioc_type_significance("something_new") == "Informational"


def test_ioc_type_title_known_and_unknown():
    assert ioc_type_title("sha256") == "SHA256 Hash"
    assert ioc_type_title("mystery_type") == "mystery_type"


# ==========================================================
# build_ioc_detail_context -- investigation/significance context
# ==========================================================


def test_context_includes_investigation_details():
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {"aaa111": investigation.threat_intelligence["hashes"][0]},
        api_key_configured=True,
    )

    assert context["value"] == "aaa111"
    assert context["ioc_type"] == "sha256"
    assert context["investigation"]["investigation_id"] == 7
    assert context["investigation"]["report_name"] == "sample_report.txt"
    assert context["significance"] == "High"


# ==========================================================
# build_ioc_detail_context -- threat-intelligence states
# ==========================================================


def test_enriched_hash_reports_enriched_state_with_record():
    investigation = _make_investigation()
    record = investigation.threat_intelligence["hashes"][0]

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {"aaa111": record},
        api_key_configured=True,
    )

    threat_intel = context["threat_intel"]

    assert threat_intel["state"] == TI_STATE_ENRICHED
    assert threat_intel["record"] == record


def test_unsupported_ioc_type_reports_unsupported_state():
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "emails",
        "user@example.com",
        {},
        api_key_configured=True,
    )

    threat_intel = context["threat_intel"]

    assert threat_intel["state"] == TI_STATE_UNSUPPORTED_TYPE
    assert threat_intel["record"] is None
    assert "not yet implemented" in threat_intel["message"]


def test_missing_api_key_reports_no_api_key_state_even_for_sha256():
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {},
        api_key_configured=False,
    )

    threat_intel = context["threat_intel"]

    assert threat_intel["state"] == TI_STATE_NO_API_KEY
    assert threat_intel["record"] is None


def test_hash_with_no_record_and_ok_status_reports_not_enriched():
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "ccc333",
        {},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_NOT_ENRICHED


def test_partial_status_without_a_record_reports_incomplete_check():
    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 1,
                "succeeded": 0,
                "failed": 1,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": False,
            },
        },
    )

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_INCOMPLETE_CHECK


def test_rate_limited_coverage_reports_provider_error():
    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 1,
                "succeeded": 0,
                "failed": 1,
                "skipped_invalid": 0,
                "rate_limited": True,
                "invalid_api_key": False,
            },
        },
    )

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_PROVIDER_ERROR
    assert "rate limit" in context["threat_intel"]["message"].lower()


def test_invalid_api_key_coverage_reports_provider_error():
    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 1,
                "succeeded": 0,
                "failed": 1,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": True,
            },
        },
    )

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_PROVIDER_ERROR
    assert "rejected" in context["threat_intel"]["message"].lower()


def test_empty_threat_intelligence_dict_does_not_raise():
    investigation = _make_investigation(threat_intelligence={})

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_NOT_ENRICHED
