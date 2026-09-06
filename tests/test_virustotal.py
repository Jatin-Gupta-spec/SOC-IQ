"""
Regression tests for the SOC-IQ VirusTotal client
(app.threat_intel.virustotal.VirusTotalClient).

Verifies structured error handling for missing/invalid API keys,
rate limiting, connection failures, timeouts, and malformed
responses. All HTTP interaction is mocked -- no real network calls
are made, and no alternate API-key source is introduced (the
existing api_key= constructor argument is used directly, the same
path SettingsService already provides).
"""

from __future__ import annotations

import requests

import pytest

from app.threat_intel.exceptions import (
    InvalidAPIKeyError,
    InvalidDomainError,
    InvalidHashError,
    InvalidIPError,
    InvalidURLError,
    MissingAPIKeyError,
    RateLimitExceededError,
    ThreatIntelConnectionError,
    ThreatIntelTimeoutError,
    UnexpectedAPIResponseError,
)
from app.threat_intel.virustotal import VirusTotalClient

VALID_SHA256 = "a" * 64
VALID_IP = "192.0.2.1"
VALID_DOMAIN = "malware.example.com"
VALID_URL = "http://malware.example.com/payload.exe"


class FakeResponse:
    """Minimal stand-in for requests.Response."""

    def __init__(self, status_code, json_data=None, json_error=False):
        self.status_code = status_code
        self._json_data = json_data
        self._json_error = json_error

    def json(self):
        if self._json_error:
            raise ValueError("No JSON could be decoded")
        return self._json_data


class FakeSession:
    """Fake requests.Session whose .get() is scripted per test."""

    def __init__(self, responder):
        self.headers = {}
        self._responder = responder

    def get(self, url, timeout=None):
        return self._responder(url, timeout)

    def close(self):
        pass


def make_client(responder, **kwargs):
    session = FakeSession(responder)
    kwargs.setdefault("api_key", "test-api-key")
    kwargs.setdefault("session", session)
    return VirusTotalClient(**kwargs)


def success_payload(malicious=0, suspicious=0, harmless=60, undetected=10, reputation=0):
    return {
        "data": {
            "attributes": {
                "last_analysis_stats": {
                    "malicious": malicious,
                    "suspicious": suspicious,
                    "harmless": harmless,
                    "undetected": undetected,
                },
                "reputation": reputation,
                "last_analysis_date": 1700000000,
            }
        }
    }


# ==========================================================
# Missing API key
# ==========================================================


def test_missing_api_key_raises(monkeypatch):
    class NoKeySettingsService:
        def load_settings(self):
            class Settings:
                virustotal_api_key = ""

            return Settings()

    monkeypatch.setattr(
        "app.threat_intel.virustotal.SettingsService",
        NoKeySettingsService,
    )

    with pytest.raises(MissingAPIKeyError):
        VirusTotalClient(api_key=None, session=FakeSession(lambda *a: None))


def test_empty_string_api_key_argument_raises(monkeypatch):
    class NoKeySettingsService:
        def load_settings(self):
            class Settings:
                virustotal_api_key = ""

            return Settings()

    monkeypatch.setattr(
        "app.threat_intel.virustotal.SettingsService",
        NoKeySettingsService,
    )

    with pytest.raises(MissingAPIKeyError):
        VirusTotalClient(api_key="", session=FakeSession(lambda *a: None))


# ==========================================================
# Invalid API key (401 / 403)
# ==========================================================


@pytest.mark.parametrize("status_code", [401, 403])
def test_invalid_api_key_raises(status_code):
    def responder(url, timeout):
        return FakeResponse(status_code)

    client = make_client(responder)

    with pytest.raises(InvalidAPIKeyError):
        client.lookup_sha256(VALID_SHA256)


# ==========================================================
# Rate limit (429)
# ==========================================================


def test_rate_limit_raises():
    def responder(url, timeout):
        return FakeResponse(429)

    client = make_client(responder)

    with pytest.raises(RateLimitExceededError):
        client.lookup_sha256(VALID_SHA256)


# ==========================================================
# Connection failure
# ==========================================================


def test_connection_error_raises():
    def responder(url, timeout):
        raise requests.exceptions.ConnectionError("no route to host")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_sha256(VALID_SHA256)


def test_generic_request_exception_raises_connection_error():
    def responder(url, timeout):
        raise requests.exceptions.RequestException("weird failure")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_sha256(VALID_SHA256)


# ==========================================================
# Timeout
# ==========================================================


def test_timeout_raises():
    def responder(url, timeout):
        raise requests.exceptions.Timeout("timed out")

    client = make_client(responder)

    with pytest.raises(ThreatIntelTimeoutError):
        client.lookup_sha256(VALID_SHA256)


# ==========================================================
# Malformed response
# ==========================================================


def test_invalid_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_error=True)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_non_dict_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data=["not", "a", "dict"])

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_missing_data_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"no_data_key": True})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_missing_attributes_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"data": {"no_attributes": True}})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_missing_analysis_stats_fields_raises():
    def responder(url, timeout):
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "attributes": {
                        "last_analysis_stats": {
                            "malicious": 1,
                            # suspicious/harmless/undetected missing
                        }
                    }
                }
            },
        )

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_non_numeric_stat_value_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_stats"]["malicious"] = "oops"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_malformed_last_analysis_date_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_date"] = "not-a-timestamp"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


# ==========================================================
# Server errors / unexpected status codes
# ==========================================================


def test_server_error_5xx_raises():
    def responder(url, timeout):
        return FakeResponse(503)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


def test_unexpected_status_code_raises():
    def responder(url, timeout):
        return FakeResponse(418)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_sha256(VALID_SHA256)


# ==========================================================
# Success and not-found paths (sanity checks around the errors)
# ==========================================================


def test_successful_lookup_returns_normalized_result():
    def responder(url, timeout):
        return FakeResponse(200, json_data=success_payload(malicious=3))

    client = make_client(responder)

    result = client.lookup_sha256(VALID_SHA256)

    assert result["found"] is True
    assert result["malicious"] == 3
    assert result["sha256"] == VALID_SHA256


def test_not_found_returns_normalized_zeroed_result():
    def responder(url, timeout):
        return FakeResponse(404)

    client = make_client(responder)

    result = client.lookup_sha256(VALID_SHA256)

    assert result["found"] is False
    assert result["malicious"] == 0


# ==========================================================
# Hash validation
# ==========================================================


def test_invalid_hash_format_raises_before_any_request():
    calls = []

    def responder(url, timeout):
        calls.append(url)
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)

    with pytest.raises(InvalidHashError):
        client.lookup_sha256("not-a-valid-hash")

    assert calls == []


# ==========================================================
# Client lifecycle
# ==========================================================


def test_closed_client_raises_on_reuse():
    def responder(url, timeout):
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)
    client.close()

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_sha256(VALID_SHA256)


def test_zero_timeout_rejected():
    with pytest.raises(ValueError):
        make_client(lambda *a: None, timeout=0)


def test_negative_timeout_rejected():
    with pytest.raises(ValueError):
        make_client(lambda *a: None, timeout=-5)


def test_close_does_not_close_externally_owned_session():
    """
    A caller-supplied session (session=...) should not be closed by
    the client -- only sessions the client itself created should be.
    """

    closed = {"value": False}

    class TrackedSession(FakeSession):
        def close(self):
            closed["value"] = True

    session = TrackedSession(lambda *a: FakeResponse(200, json_data=success_payload()))
    client = VirusTotalClient(api_key="key", session=session)

    client.close()

    assert closed["value"] is False


# ==========================================================
# IPv4 Lookups (lookup_ip)
# ==========================================================


@pytest.mark.parametrize("status_code", [401, 403])
def test_ip_invalid_api_key_raises(status_code):
    def responder(url, timeout):
        return FakeResponse(status_code)

    client = make_client(responder)

    with pytest.raises(InvalidAPIKeyError):
        client.lookup_ip(VALID_IP)


def test_ip_rate_limit_raises():
    def responder(url, timeout):
        return FakeResponse(429)

    client = make_client(responder)

    with pytest.raises(RateLimitExceededError):
        client.lookup_ip(VALID_IP)


def test_ip_connection_error_raises():
    def responder(url, timeout):
        raise requests.exceptions.ConnectionError("no route to host")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_ip(VALID_IP)


def test_ip_generic_request_exception_raises_connection_error():
    def responder(url, timeout):
        raise requests.exceptions.RequestException("connection dropped")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_ip(VALID_IP)


def test_ip_timeout_raises():
    def responder(url, timeout):
        raise requests.exceptions.Timeout("timed out")

    client = make_client(responder)

    with pytest.raises(ThreatIntelTimeoutError):
        client.lookup_ip(VALID_IP)


def test_ip_invalid_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_error=True)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_non_dict_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data=["not", "a", "dict"])

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_missing_data_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"no_data_key": True})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_missing_attributes_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"data": {"no_attributes": True}})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_missing_analysis_stats_fields_raises():
    def responder(url, timeout):
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "attributes": {
                        "last_analysis_stats": {
                            "malicious": 1,
                        }
                    }
                }
            },
        )

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_non_numeric_stat_value_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_stats"]["malicious"] = "oops"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_malformed_last_analysis_date_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_date"] = "not-a-timestamp"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_server_error_5xx_raises():
    def responder(url, timeout):
        return FakeResponse(500)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_unexpected_status_code_raises():
    def responder(url, timeout):
        return FakeResponse(418)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_ip(VALID_IP)


def test_ip_successful_lookup_returns_normalized_result():
    def responder(url, timeout):
        assert "ip_addresses/192.0.2.1" in url
        return FakeResponse(200, json_data=success_payload(malicious=5, suspicious=1, harmless=50, undetected=14, reputation=10))

    client = make_client(responder)

    result = client.lookup_ip(VALID_IP)

    assert result["found"] is True
    assert result["ip"] == VALID_IP
    assert result["malicious"] == 5
    assert result["suspicious"] == 1
    assert result["harmless"] == 50
    assert result["undetected"] == 14
    assert result["reputation"] == 10
    assert result["last_analysis_date"] is not None
    assert result["permalink"] == f"https://www.virustotal.com/gui/ip-address/{VALID_IP}"


def test_ip_not_found_returns_normalized_zeroed_result():
    def responder(url, timeout):
        return FakeResponse(404)

    client = make_client(responder)

    result = client.lookup_ip(VALID_IP)

    assert result["found"] is False
    assert result["ip"] == VALID_IP
    assert result["malicious"] == 0
    assert result["suspicious"] == 0
    assert result["harmless"] == 0
    assert result["undetected"] == 0
    assert result["reputation"] is None
    assert result["last_analysis_date"] is None
    assert result["permalink"] == f"https://www.virustotal.com/gui/ip-address/{VALID_IP}"


def test_ip_closed_client_raises_on_reuse():
    def responder(url, timeout):
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)
    client.close()

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_ip(VALID_IP)


@pytest.mark.parametrize(
    "bad_ip",
    [
        "not-an-ip",
        "256.0.0.1",
        "1.2.3",
        "1.2.3.4.5",
        "2001:db8::1",
        "",
        "   ",
        "01.02.03.04",
        "192.168.1.1.com",
    ],
)
def test_invalid_ip_format_raises_before_any_request(bad_ip):
    calls = []

    def responder(url, timeout):
        calls.append(url)
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)

    with pytest.raises(InvalidIPError):
        client.lookup_ip(bad_ip)

    assert calls == []


# ==========================================================
# Domain Lookups (lookup_domain)
# ==========================================================


@pytest.mark.parametrize("status_code", [401, 403])
def test_domain_invalid_api_key_raises(status_code):
    def responder(url, timeout):
        return FakeResponse(status_code)

    client = make_client(responder)

    with pytest.raises(InvalidAPIKeyError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_rate_limit_raises():
    def responder(url, timeout):
        return FakeResponse(429)

    client = make_client(responder)

    with pytest.raises(RateLimitExceededError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_connection_error_raises():
    def responder(url, timeout):
        raise requests.exceptions.ConnectionError("no route to host")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_generic_request_exception_raises_connection_error():
    def responder(url, timeout):
        raise requests.exceptions.RequestException("connection dropped")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_timeout_raises():
    def responder(url, timeout):
        raise requests.exceptions.Timeout("timed out")

    client = make_client(responder)

    with pytest.raises(ThreatIntelTimeoutError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_invalid_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_error=True)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_non_dict_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data=["not", "a", "dict"])

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_missing_data_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"no_data_key": True})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_missing_attributes_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"data": {"no_attributes": True}})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_missing_analysis_stats_fields_raises():
    def responder(url, timeout):
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "attributes": {
                        "last_analysis_stats": {
                            "malicious": 1,
                        }
                    }
                }
            },
        )

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_non_numeric_stat_value_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_stats"]["malicious"] = "oops"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_malformed_last_analysis_date_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_date"] = "not-a-timestamp"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_server_error_5xx_raises():
    def responder(url, timeout):
        return FakeResponse(502)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_unexpected_status_code_raises():
    def responder(url, timeout):
        return FakeResponse(418)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_domain(VALID_DOMAIN)


def test_domain_successful_lookup_returns_normalized_result():
    def responder(url, timeout):
        assert "domains/malware.example.com" in url
        return FakeResponse(200, json_data=success_payload(malicious=12, suspicious=2, harmless=40, undetected=16, reputation=-5))

    client = make_client(responder)

    result = client.lookup_domain(VALID_DOMAIN)

    assert result["found"] is True
    assert result["domain"] == VALID_DOMAIN
    assert result["malicious"] == 12
    assert result["suspicious"] == 2
    assert result["harmless"] == 40
    assert result["undetected"] == 16
    assert result["reputation"] == -5
    assert result["last_analysis_date"] is not None
    assert result["permalink"] == f"https://www.virustotal.com/gui/domain/{VALID_DOMAIN}"


def test_domain_not_found_returns_normalized_zeroed_result():
    def responder(url, timeout):
        return FakeResponse(404)

    client = make_client(responder)

    result = client.lookup_domain(VALID_DOMAIN)

    assert result["found"] is False
    assert result["domain"] == VALID_DOMAIN
    assert result["malicious"] == 0
    assert result["suspicious"] == 0
    assert result["harmless"] == 0
    assert result["undetected"] == 0
    assert result["reputation"] is None
    assert result["last_analysis_date"] is None
    assert result["permalink"] == f"https://www.virustotal.com/gui/domain/{VALID_DOMAIN}"


def test_domain_closed_client_raises_on_reuse():
    def responder(url, timeout):
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)
    client.close()

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_domain(VALID_DOMAIN)


@pytest.mark.parametrize(
    "bad_domain",
    [
        "nodot",
        "-invalid.com",
        "invalid-.com",
        "inv..alid.com",
        "",
        "   ",
        "192.168.1.1",
        "a" * 255 + ".com",
    ],
)
def test_invalid_domain_format_raises_before_any_request(bad_domain):
    calls = []

    def responder(url, timeout):
        calls.append(url)
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)

    with pytest.raises(InvalidDomainError):
        client.lookup_domain(bad_domain)

    assert calls == []


# ==========================================================
# URL Lookups (lookup_url)
# ==========================================================


@pytest.mark.parametrize("status_code", [401, 403])
def test_url_invalid_api_key_raises(status_code):
    def responder(url, timeout):
        return FakeResponse(status_code)

    client = make_client(responder)

    with pytest.raises(InvalidAPIKeyError):
        client.lookup_url(VALID_URL)


def test_url_rate_limit_raises():
    def responder(url, timeout):
        return FakeResponse(429)

    client = make_client(responder)

    with pytest.raises(RateLimitExceededError):
        client.lookup_url(VALID_URL)


def test_url_connection_error_raises():
    def responder(url, timeout):
        raise requests.exceptions.ConnectionError("no route to host")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_url(VALID_URL)


def test_url_generic_request_exception_raises_connection_error():
    def responder(url, timeout):
        raise requests.exceptions.RequestException("connection dropped")

    client = make_client(responder)

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_url(VALID_URL)


def test_url_timeout_raises():
    def responder(url, timeout):
        raise requests.exceptions.Timeout("timed out")

    client = make_client(responder)

    with pytest.raises(ThreatIntelTimeoutError):
        client.lookup_url(VALID_URL)


def test_url_invalid_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_error=True)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_non_dict_json_response_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data=["not", "a", "dict"])

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_missing_data_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"no_data_key": True})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_missing_attributes_key_raises():
    def responder(url, timeout):
        return FakeResponse(200, json_data={"data": {"no_attributes": True}})

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_missing_analysis_stats_fields_raises():
    def responder(url, timeout):
        return FakeResponse(
            200,
            json_data={
                "data": {
                    "attributes": {
                        "last_analysis_stats": {
                            "malicious": 1,
                        }
                    }
                }
            },
        )

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_non_numeric_stat_value_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_stats"]["malicious"] = "oops"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_malformed_last_analysis_date_raises():
    def responder(url, timeout):
        payload = success_payload()
        payload["data"]["attributes"]["last_analysis_date"] = "not-a-timestamp"
        return FakeResponse(200, json_data=payload)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_server_error_5xx_raises():
    def responder(url, timeout):
        return FakeResponse(502)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_unexpected_status_code_raises():
    def responder(url, timeout):
        return FakeResponse(418)

    client = make_client(responder)

    with pytest.raises(UnexpectedAPIResponseError):
        client.lookup_url(VALID_URL)


def test_url_successful_lookup_returns_normalized_result():
    def responder(url, timeout):
        import base64
        # Validate that the url ID generation is correct
        expected_id = base64.urlsafe_b64encode(VALID_URL.encode("utf-8")).decode("ascii").rstrip("=")
        assert f"urls/{expected_id}" in url
        return FakeResponse(200, json_data=success_payload(malicious=12, suspicious=2, harmless=40, undetected=16, reputation=-5))

    client = make_client(responder)

    result = client.lookup_url(VALID_URL)

    import base64
    expected_id = base64.urlsafe_b64encode(VALID_URL.encode("utf-8")).decode("ascii").rstrip("=")

    assert result["found"] is True
    assert result["url"] == VALID_URL
    assert result["url_id"] == expected_id
    assert result["malicious"] == 12
    assert result["suspicious"] == 2
    assert result["harmless"] == 40
    assert result["undetected"] == 16
    assert result["reputation"] == -5
    assert result["last_analysis_date"] is not None
    assert result["permalink"] == f"https://www.virustotal.com/gui/url/{expected_id}"


def test_url_not_found_returns_normalized_zeroed_result():
    def responder(url, timeout):
        return FakeResponse(404)

    client = make_client(responder)

    result = client.lookup_url(VALID_URL)

    import base64
    expected_id = base64.urlsafe_b64encode(VALID_URL.encode("utf-8")).decode("ascii").rstrip("=")

    assert result["found"] is False
    assert result["url"] == VALID_URL
    assert result["url_id"] == expected_id
    assert result["malicious"] == 0
    assert result["suspicious"] == 0
    assert result["harmless"] == 0
    assert result["undetected"] == 0
    assert result["reputation"] is None
    assert result["last_analysis_date"] is None
    assert result["permalink"] == f"https://www.virustotal.com/gui/url/{expected_id}"


def test_url_closed_client_raises_on_reuse():
    def responder(url, timeout):
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)
    client.close()

    with pytest.raises(ThreatIntelConnectionError):
        client.lookup_url(VALID_URL)


@pytest.mark.parametrize(
    "bad_url",
    [
        "not-a-url",
        "ftp://example.com/file",
        "http://",
        "",
        "   ",
    ],
)
def test_invalid_url_format_raises_before_any_request(bad_url):
    calls = []

    def responder(url, timeout):
        calls.append(url)
        return FakeResponse(200, json_data=success_payload())

    client = make_client(responder)

    with pytest.raises(InvalidURLError):
        client.lookup_url(bad_url)

    assert calls == []
