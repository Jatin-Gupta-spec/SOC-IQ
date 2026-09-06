"""
Unit tests for URL, IPv4, and domain support in IOC detail context.

Covers:
  * URL found / not found / no API key / error / record lookup
  * SHA256, IPv4, and domain regression
  * Genuinely unsupported types remain unsupported
  * Incomplete check and provider error states for URLs

These are plain-Python tests (no Qt/PySide6 dependency) covering
the multi-type enrichment support added in Phase 3D.
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
    TI_STATE_UNSUPPORTED_TYPE,
    build_ioc_detail_context,
)


def _make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="sample_report.txt",
        iocs={
            "urls": ["http://malicious.com"],
            "sha256": ["aaa111"],
            "ipv4": ["1.1.1.1"],
            "domains": ["evil.com"],
        },
        threat_intelligence={
            "urls": [
                {
                    "url": "http://malicious.com",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                    "reputation": -20,
                    "last_analysis_date": "2026-01-01T00:00:00+00:00",
                },
            ],
            "hashes": [
                {
                    "sha256": "aaa111",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
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


# ----------------------------------------------------------------
# URL states
# ----------------------------------------------------------------


def test_url_found_state():
    investigation = _make_investigation()
    threat_intel_by_value = {
        "http://malicious.com": investigation.threat_intelligence["urls"][0],
    }

    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="urls",
        value="http://malicious.com",
        threat_intel_by_value=threat_intel_by_value,
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_ENRICHED
    assert context["threat_intel"]["record"]["verdict"] == "Malicious"


def test_url_not_found_state():
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="urls",
        value="http://unknown.com",
        threat_intel_by_value={},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_NOT_ENRICHED


def test_url_no_api_key_state():
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="urls",
        value="http://malicious.com",
        threat_intel_by_value={},
        api_key_configured=False,
    )

    assert context["threat_intel"]["state"] == TI_STATE_NO_API_KEY


def test_url_invalid_api_key_reports_provider_error():
    investigation = _make_investigation(
        threat_intelligence={
            "urls": [],
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
        investigation=investigation,
        ioc_type="urls",
        value="http://malicious.com",
        threat_intel_by_value={},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_PROVIDER_ERROR
    assert "rejected" in context["threat_intel"]["message"].lower()


def test_url_rate_limited_reports_provider_error():
    investigation = _make_investigation(
        threat_intelligence={
            "urls": [],
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
        investigation=investigation,
        ioc_type="urls",
        value="http://malicious.com",
        threat_intel_by_value={},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_PROVIDER_ERROR
    assert "rate limit" in context["threat_intel"]["message"].lower()


def test_url_partial_status_reports_incomplete_check():
    investigation = _make_investigation(
        threat_intelligence={
            "urls": [],
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
        investigation=investigation,
        ioc_type="urls",
        value="http://malicious.com",
        threat_intel_by_value={},
        api_key_configured=True,
    )

    assert context["threat_intel"]["state"] == TI_STATE_INCOMPLETE_CHECK


def test_url_record_lookup():
    """Verify that the record is correctly looked up by URL value."""
    investigation = _make_investigation()
    url_record = investigation.threat_intelligence["urls"][0]

    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="urls",
        value="http://malicious.com",
        threat_intel_by_value={"http://malicious.com": url_record},
        api_key_configured=True,
    )

    assert context["threat_intel"]["record"] is url_record
    assert context["threat_intel"]["record"]["url"] == "http://malicious.com"


# ----------------------------------------------------------------
# Regression: SHA256, IPv4, domain
# ----------------------------------------------------------------


def test_sha256_regression():
    investigation = _make_investigation()
    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="sha256",
        value="aaa111",
        threat_intel_by_value={"aaa111": {"sha256": "aaa111", "verdict": "Clean"}},
        api_key_configured=True,
    )
    assert context["threat_intel"]["state"] == TI_STATE_ENRICHED


def test_ipv4_regression():
    investigation = _make_investigation()
    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="ipv4",
        value="1.1.1.1",
        threat_intel_by_value={"1.1.1.1": {"ip": "1.1.1.1", "verdict": "Clean"}},
        api_key_configured=True,
    )
    assert context["threat_intel"]["state"] == TI_STATE_ENRICHED


def test_domain_regression():
    investigation = _make_investigation()
    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="domains",
        value="evil.com",
        threat_intel_by_value={"evil.com": {"domain": "evil.com", "verdict": "Clean"}},
        api_key_configured=True,
    )
    assert context["threat_intel"]["state"] == TI_STATE_ENRICHED


# ----------------------------------------------------------------
# Genuinely unsupported types
# ----------------------------------------------------------------


def test_emails_remain_unsupported():
    investigation = _make_investigation()
    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="emails",
        value="user@example.com",
        threat_intel_by_value={},
        api_key_configured=True,
    )
    assert context["threat_intel"]["state"] == TI_STATE_UNSUPPORTED_TYPE
    assert context["threat_intel"]["record"] is None


def test_cves_remain_unsupported():
    investigation = _make_investigation()
    context = build_ioc_detail_context(
        investigation=investigation,
        ioc_type="cves",
        value="CVE-2024-1234",
        threat_intel_by_value={},
        api_key_configured=True,
    )
    assert context["threat_intel"]["state"] == TI_STATE_UNSUPPORTED_TYPE
