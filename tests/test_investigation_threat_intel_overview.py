"""
Unit tests for
`app.services.ioc_detail_context.build_investigation_threat_intel_overview`.

This is the investigation-level ("what is the overall
threat-intelligence state of this investigation") counterpart to
`build_ioc_detail_context`'s per-IOC threat-intel state, added in
Phase 2 Part 2B-1. Plain-Python tests, no Qt/PySide6 dependency.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import Investigation
from app.services.ioc_detail_context import (
    TI_STATE_ENRICHED,
    TI_STATE_INCOMPLETE_CHECK,
    TI_STATE_NO_API_KEY,
    TI_STATE_NOT_ENRICHED,
    TI_STATE_PROVIDER_ERROR,
    build_investigation_threat_intel_overview,
)


def _make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="sample_report.txt",
        iocs={"sha256": ["aaa111", "bbb222"], "ipv4": ["1.2.3.4"]},
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "aaa111",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                },
                {
                    "sha256": "bbb222",
                    "verdict": "Clean",
                    "detection_ratio": "0/70",
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


def test_fully_enriched_reports_enriched_with_counts():
    investigation = _make_investigation()

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    assert overview["state"] == TI_STATE_ENRICHED
    assert overview["requested"] == 2
    assert overview["succeeded"] == 2
    assert "2/2" in overview["short_label"]


def test_empty_threat_intelligence_dict_reports_not_enriched():
    investigation = _make_investigation(threat_intelligence={})

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    assert overview["state"] == TI_STATE_NOT_ENRICHED
    assert "no threat-intelligence check" in overview["message"].lower()


def test_no_indicators_reports_not_enriched_with_reason():
    investigation = _make_investigation(
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={
            "hashes": [],
            "status": "no_indicators",
            "coverage": {
                "status": "no_indicators",
                "requested": 0,
                "succeeded": 0,
                "failed": 0,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": False,
            },
        },
    )

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    assert overview["state"] == TI_STATE_NOT_ENRICHED
    assert overview["short_label"] == "No Enrichable Indicators"
    assert "no enrichable indicators" in overview["message"].lower()


def test_missing_api_key_reported_before_provider_error():
    """
    When hashes exist but no API key is configured, the overview
    must report the specific, more useful "no API key" state --
    not a generic provider error -- even though the underlying
    coverage would also show `invalid_api_key=True` (the client
    fails fast on the very first lookup attempt).
    """

    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 2,
                "succeeded": 0,
                "failed": 2,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": True,
            },
        },
    )

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=False,
    )

    assert overview["state"] == TI_STATE_NO_API_KEY
    assert "api key" in overview["message"].lower()


def test_invalid_api_key_with_key_configured_reports_provider_error():
    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 2,
                "succeeded": 0,
                "failed": 2,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": True,
            },
        },
    )

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    assert overview["state"] == TI_STATE_PROVIDER_ERROR
    assert "rejected" in overview["message"].lower()


def test_rate_limited_reports_provider_error():
    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [
                {"sha256": "aaa111", "verdict": "Clean", "detection_ratio": "0/70"},
            ],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 2,
                "succeeded": 1,
                "failed": 1,
                "skipped_invalid": 0,
                "rate_limited": True,
                "invalid_api_key": False,
            },
        },
    )

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    assert overview["state"] == TI_STATE_PROVIDER_ERROR
    assert "rate limit" in overview["message"].lower()


def test_partial_without_provider_error_reports_incomplete_check():
    investigation = _make_investigation(
        threat_intelligence={
            "hashes": [
                {"sha256": "aaa111", "verdict": "Clean", "detection_ratio": "0/70"},
            ],
            "status": "partial",
            "coverage": {
                "status": "partial",
                "requested": 2,
                "succeeded": 1,
                "failed": 1,
                "skipped_invalid": 0,
                "rate_limited": False,
                "invalid_api_key": False,
            },
        },
    )

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    assert overview["state"] == TI_STATE_INCOMPLETE_CHECK
    assert overview["requested"] == 2
    assert overview["succeeded"] == 1


def test_short_label_always_present_and_non_empty():
    """
    Every state the function can return must produce a non-empty
    `short_label`, since the header card's compact KeyValueRow has
    no fallback text of its own.
    """

    cases = [
        _make_investigation(),
        _make_investigation(threat_intelligence={}),
        _make_investigation(
            iocs={"ipv4": ["1.2.3.4"]},
            threat_intelligence={
                "hashes": [],
                "status": "no_indicators",
                "coverage": {
                    "status": "no_indicators",
                    "requested": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "skipped_invalid": 0,
                    "rate_limited": False,
                    "invalid_api_key": False,
                },
            },
        ),
    ]

    for investigation in cases:
        for api_key_configured in (True, False):
            overview = build_investigation_threat_intel_overview(
                investigation,
                api_key_configured=api_key_configured,
            )

            assert overview["short_label"]
            assert overview["message"]
