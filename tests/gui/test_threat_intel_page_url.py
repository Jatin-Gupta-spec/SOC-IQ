"""
Unit tests for URL support in the Threat Intelligence Page.

Covers:
  * URL detection (http://, https://)
  * IP detection (dotted-quad IPv4)
  * Domain detection
  * SHA256 detection
  * Unsupported indicator types are rejected
  * Successful URL result rendering (does not crash)
  * URL not-found rendering
  * No-API-key state
  * API/network error rendering
  * SHA256 result rendering regression
  * IP result rendering regression
  * Domain result rendering regression

Tests exercise the indicator detection logic, worker construction,
and result rendering callbacks directly -- without starting real
QThreads or making network calls.

Phase 4C, Stage 2: the page now dispatches through
`ThreatIntelService.lookup_indicator(ioc_type, value)` instead of
calling a `VirusTotalClient` method directly (see
`app/gui/pages/threat_intel_page.py`'s module docstring), so the
worker-dispatch tests below assert against a mocked
`ThreatIntelService.lookup_indicator` call instead of per-type
`client.lookup_*` calls. This is an intentional, planned test update
for Stage 2's consumer migration, not a coverage reduction -- every
dispatch type, the no-key state, and error/rendering behavior remain
covered.
"""

from __future__ import annotations

import re
from unittest.mock import MagicMock, patch

from app.gui.pages.threat_intel_page import (
    ThreatIntelPage,
    _SHA256_PATTERN,
    _IPV4_PATTERN,
    _DOMAIN_PATTERN,
    _URL_PATTERN,
    _VirusTotalLookupWorker,
)


# ----------------------------------------------------------------
# Pattern detection (unit-level, no Qt needed)
# ----------------------------------------------------------------


def test_sha256_pattern_matches_valid_hash():
    assert _SHA256_PATTERN.fullmatch("a" * 64) is not None
    assert _SHA256_PATTERN.fullmatch("A" * 64) is not None
    assert _SHA256_PATTERN.fullmatch("0123456789abcdef" * 4) is not None


def test_sha256_pattern_rejects_non_hash():
    assert _SHA256_PATTERN.fullmatch("a" * 63) is None
    assert _SHA256_PATTERN.fullmatch("a" * 65) is None
    assert _SHA256_PATTERN.fullmatch("not-a-hash") is None


def test_ipv4_pattern_matches_valid_ips():
    assert _IPV4_PATTERN.fullmatch("8.8.8.8") is not None
    assert _IPV4_PATTERN.fullmatch("192.168.1.1") is not None
    assert _IPV4_PATTERN.fullmatch("255.255.255.255") is not None


def test_ipv4_pattern_rejects_invalid():
    assert _IPV4_PATTERN.fullmatch("256.1.1.1") is None
    assert _IPV4_PATTERN.fullmatch("not-an-ip") is None


def test_domain_pattern_matches_valid_domains():
    assert _DOMAIN_PATTERN.fullmatch("example.com") is not None
    assert _DOMAIN_PATTERN.fullmatch("sub.example.com") is not None


def test_domain_pattern_rejects_invalid():
    assert _DOMAIN_PATTERN.fullmatch("not a domain") is None


def test_url_pattern_matches_http_and_https():
    assert _URL_PATTERN.match("http://malicious.com") is not None
    assert _URL_PATTERN.match("https://secure.example.com/path?q=1") is not None


def test_url_pattern_rejects_non_url():
    assert _URL_PATTERN.match("ftp://server.com") is None
    assert _URL_PATTERN.match("just-text") is None


# ----------------------------------------------------------------
# Indicator type detection in _run_query
# ----------------------------------------------------------------


def test_threat_intel_page_detects_url(qapp):
    page = ThreatIntelPage()
    page._vt_client = MagicMock()
    page._search_input.setText("http://malicious.com")

    with patch("PySide6.QtCore.QThread.start"):
        page._run_query()

    assert page._worker is not None
    assert page._worker._query_type == "url"


def test_threat_intel_page_detects_ip(qapp):
    page = ThreatIntelPage()
    page._vt_client = MagicMock()
    page._search_input.setText("8.8.8.8")

    with patch("PySide6.QtCore.QThread.start"):
        page._run_query()

    assert page._worker is not None
    assert page._worker._query_type == "ipv4"


def test_threat_intel_page_detects_domain(qapp):
    page = ThreatIntelPage()
    page._vt_client = MagicMock()
    page._search_input.setText("example.com")

    with patch("PySide6.QtCore.QThread.start"):
        page._run_query()

    assert page._worker is not None
    assert page._worker._query_type == "domain"


def test_threat_intel_page_detects_sha256(qapp):
    page = ThreatIntelPage()
    page._vt_client = MagicMock()
    page._search_input.setText("a" * 64)

    with patch("PySide6.QtCore.QThread.start"):
        page._run_query()

    assert page._worker is not None
    assert page._worker._query_type == "sha256"


def test_threat_intel_page_rejects_unsupported(qapp):
    page = ThreatIntelPage()
    page._vt_client = MagicMock()
    page._search_input.setText("test@example.com")
    page._run_query()

    # No worker should be created for unsupported types
    assert page._worker is None
    assert "Unsupported" in page._res_title.text()


def test_threat_intel_page_no_api_key(qapp):
    page = ThreatIntelPage()
    page._vt_client = None
    page._search_input.setText("http://test.com")
    page._run_query()

    assert page._worker is None
    assert "Not Configured" in page._res_title.text()


# ----------------------------------------------------------------
# Result rendering
# ----------------------------------------------------------------


def test_threat_intel_page_renders_url_success(qapp):
    page = ThreatIntelPage()
    result = {
        "url": "http://test.com",
        "found": True,
        "malicious": 1,
        "suspicious": 2,
        "harmless": 3,
        "undetected": 4,
        "reputation": 0,
        "last_analysis_date": "2026-01-01",
        "permalink": "http://vt/url/123",
    }
    page._on_lookup_finished(result)
    assert "http://test.com" in page._res_detail.text()
    assert "Malicious: 1" in page._res_detail.text()


def test_threat_intel_page_renders_url_not_found(qapp):
    page = ThreatIntelPage()
    result = {"url": "http://test.com", "found": False}
    page._on_lookup_finished(result)
    assert "http://test.com" in page._res_detail.text()
    assert "Not found" in page._res_detail.text()


def test_threat_intel_page_renders_sha256_success(qapp):
    """SHA256 result rendering regression."""
    page = ThreatIntelPage()
    result = {
        "sha256": "a" * 64,
        "found": True,
        "malicious": 10,
        "suspicious": 0,
        "harmless": 60,
        "undetected": 0,
        "reputation": -50,
        "last_analysis_date": "2026-01-01",
        "permalink": "http://vt/file/abc",
    }
    page._on_lookup_finished(result)
    assert ("a" * 64) in page._res_detail.text()
    assert "Malicious: 10" in page._res_detail.text()


def test_threat_intel_page_renders_ip_success(qapp):
    """IPv4 result rendering regression."""
    page = ThreatIntelPage()
    result = {
        "ip": "8.8.8.8",
        "found": True,
        "malicious": 0,
        "suspicious": 0,
        "harmless": 70,
        "undetected": 0,
        "reputation": 10,
        "last_analysis_date": "2026-01-01",
        "permalink": "http://vt/ip/8.8.8.8",
    }
    page._on_lookup_finished(result)
    assert "8.8.8.8" in page._res_detail.text()


def test_threat_intel_page_renders_domain_success(qapp):
    """Domain result rendering regression."""
    page = ThreatIntelPage()
    result = {
        "domain": "example.com",
        "found": True,
        "malicious": 0,
        "suspicious": 1,
        "harmless": 69,
        "undetected": 0,
        "reputation": 5,
        "last_analysis_date": "2026-01-01",
        "permalink": "http://vt/domain/example.com",
    }
    page._on_lookup_finished(result)
    assert "example.com" in page._res_detail.text()


def test_threat_intel_page_renders_api_error(qapp):
    """API/network errors are shown to the analyst, not as raw exceptions."""
    page = ThreatIntelPage()
    page._on_lookup_failed("Connection timed out after 30 seconds")
    assert "Query Failed" in page._res_title.text()
    assert "Connection timed out" in page._res_detail.text()


def test_threat_intel_page_invalid_input_rejected(qapp):
    """Various invalid inputs should be rejected gracefully."""
    page = ThreatIntelPage()
    page._vt_client = MagicMock()

    for invalid_input in ["", "   ", "CVE-2024-1234", "random text"]:
        page._search_input.setText(invalid_input)
        page._worker = None
        page._thread = None
        page._run_query()
        assert page._worker is None


# ----------------------------------------------------------------
# Worker dispatch
# ----------------------------------------------------------------


def test_worker_dispatches_url_to_lookup_indicator():
    """The worker correctly calls service.lookup_indicator for URL queries."""
    service = MagicMock()
    service.lookup_indicator.return_value = {"url": "http://test.com", "found": True}

    worker = _VirusTotalLookupWorker(service, "http://test.com", "url")

    received = []
    worker.finished.connect(received.append)
    worker.run()

    service.lookup_indicator.assert_called_once_with("url", "http://test.com")
    assert len(received) == 1
    assert received[0]["url"] == "http://test.com"


def test_worker_dispatches_sha256_to_lookup_indicator():
    """SHA256 dispatch regression."""
    service = MagicMock()
    service.lookup_indicator.return_value = {"sha256": "a" * 64, "found": True}

    worker = _VirusTotalLookupWorker(service, "a" * 64, "sha256")

    received = []
    worker.finished.connect(received.append)
    worker.run()

    service.lookup_indicator.assert_called_once_with("sha256", "a" * 64)
    assert len(received) == 1


def test_worker_dispatches_ip_to_lookup_indicator():
    """IPv4 dispatch regression."""
    service = MagicMock()
    service.lookup_indicator.return_value = {"ip": "8.8.8.8", "found": True}

    worker = _VirusTotalLookupWorker(service, "8.8.8.8", "ipv4")

    received = []
    worker.finished.connect(received.append)
    worker.run()

    service.lookup_indicator.assert_called_once_with("ipv4", "8.8.8.8")


def test_worker_dispatches_domain_to_lookup_indicator():
    """Domain dispatch regression."""
    service = MagicMock()
    service.lookup_indicator.return_value = {"domain": "example.com", "found": True}

    worker = _VirusTotalLookupWorker(service, "example.com", "domain")

    received = []
    worker.finished.connect(received.append)
    worker.run()

    service.lookup_indicator.assert_called_once_with("domain", "example.com")


def test_worker_emits_failed_on_exception():
    """Worker errors are signaled, not raised."""
    service = MagicMock()
    service.lookup_indicator.side_effect = ConnectionError("Network unreachable")

    worker = _VirusTotalLookupWorker(service, "http://test.com", "url")

    failures = []
    worker.failed.connect(failures.append)
    worker.run()

    assert len(failures) == 1
    assert "Network unreachable" in failures[0]
