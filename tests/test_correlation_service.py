"""
Tests for the Phase 3B evidence correlation service
(app.services.correlation_service.CorrelationService).

Covers exact/normalized duplicate matches, cross-category
domain/URL association, threat-intelligence linkage, empty and
invalid input, determinism, and ordering.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.services.correlation_models import (
    RELATIONSHIP_DOMAIN_URL_HOST,
    RELATIONSHIP_DUPLICATE_IOC,
    RELATIONSHIP_THREAT_INTEL_LINK,
)
from app.services.correlation_service import (
    CorrelationService,
    normalize_ioc_value,
)


def make_investigation(
    iocs: dict[str, list[str]] | None = None,
    threat_intelligence: dict | None = None,
) -> Investigation:
    return Investigation(
        report_name="test_report.txt",
        iocs=iocs or {},
        threat_intelligence=threat_intelligence or {},
        risk_score=0,
        severity="LOW",
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime.now(UTC),
    )


@pytest.fixture()
def service():
    return CorrelationService()


# ==========================================================
# Normalization
# ==========================================================


@pytest.mark.parametrize(
    "ioc_type,raw,expected",
    [
        ("domains", "Example.COM", "example.com"),
        ("domains", "example.com.", "example.com"),
        ("sha256", "AABBCC", "aabbcc"),
        ("ipv4", "1.2.3.4", "1.2.3.4"),
        ("urls", "HTTPS://Example.com/Path", "https://example.com/Path"),
    ],
)
def test_normalize_ioc_value(ioc_type, raw, expected):
    assert normalize_ioc_value(ioc_type, raw) == expected


def test_normalize_url_preserves_path_case():
    # The path is case-sensitive on many servers -- only scheme and
    # host are normalized for comparison.
    normalized = normalize_ioc_value("urls", "HTTP://Host.com/CaseSensitive")
    assert normalized == "http://host.com/CaseSensitive"


def test_normalize_malformed_url_falls_back_to_lowercase():
    # Not a parseable absolute URL -- must not raise.
    normalized = normalize_ioc_value("urls", "not-a-url")
    assert normalized == "not-a-url"


# ==========================================================
# Exact / normalized duplicate matches
# ==========================================================


def test_duplicate_normalized_domain_detected(service):
    investigation = make_investigation(
        iocs={"domains": ["Example.com", "example.com"]},
    )

    report = service.correlate(investigation)

    duplicate_results = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_DUPLICATE_IOC
    ]

    assert len(duplicate_results) == 1
    assert duplicate_results[0].primary.value == "Example.com"
    assert duplicate_results[0].related.value == "example.com"


def test_identical_ioc_is_not_duplicated_by_extractor_assumption(service):
    # extract_iocs() already de-duplicates identical raw strings, so
    # a category with genuinely distinct values produces no
    # duplicate-IOC result.
    investigation = make_investigation(
        iocs={"ipv4": ["1.1.1.1", "2.2.2.2"]},
    )

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_DUPLICATE_IOC for r in report.results
    )


def test_three_way_duplicate_produces_two_results_not_three(service):
    # Linear (n-1) pairing against the canonical form, not full
    # pairwise (n choose 2), to avoid quadratic blowup.
    investigation = make_investigation(
        iocs={"domains": ["EXAMPLE.com", "Example.com", "example.com"]},
    )

    report = service.correlate(investigation)

    duplicate_results = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_DUPLICATE_IOC
    ]

    assert len(duplicate_results) == 2


# ==========================================================
# Cross-category: domain <-> URL host
# ==========================================================


def test_domain_matches_url_host_exactly(service):
    investigation = make_investigation(
        iocs={
            "domains": ["evil.com"],
            "urls": ["https://evil.com/payload.exe"],
        },
    )

    report = service.correlate(investigation)

    matches = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_DOMAIN_URL_HOST
    ]

    assert len(matches) == 1
    assert matches[0].primary.value == "evil.com"
    assert matches[0].related.value == "https://evil.com/payload.exe"


def test_domain_matches_url_subdomain(service):
    investigation = make_investigation(
        iocs={
            "domains": ["evil.com"],
            "urls": ["https://cdn.evil.com/x"],
        },
    )

    report = service.correlate(investigation)

    matches = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_DOMAIN_URL_HOST
    ]

    assert len(matches) == 1
    assert "subdomain" in matches[0].reason.lower()


def test_unrelated_domain_and_url_not_matched(service):
    investigation = make_investigation(
        iocs={
            "domains": ["evil.com"],
            "urls": ["https://benign.com/x"],
        },
    )

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_DOMAIN_URL_HOST for r in report.results
    )


def test_no_domain_url_correlation_when_one_category_missing(service):
    investigation = make_investigation(iocs={"domains": ["evil.com"]})

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_DOMAIN_URL_HOST for r in report.results
    )


# ==========================================================
# Threat-intelligence linkage
# ==========================================================


def test_sha256_linked_to_existing_threat_intel_record(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "a" * 64,
                    "verdict": "Malicious",
                    "detection_ratio": "12/70",
                },
            ],
        },
    )

    report = service.correlate(investigation)

    links = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK
    ]

    assert len(links) == 1
    assert "Malicious" in links[0].reason
    assert "12/70" in links[0].reason


def test_sha256_without_threat_intel_record_not_linked(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={"hashes": []},
    )

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK for r in report.results
    )


def test_other_ioc_types_never_get_threat_intel_link(service):
    investigation = make_investigation(
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={"hashes": [{"sha256": "a" * 64, "verdict": "Clean"}]},
    )

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK for r in report.results
    )


# ----------------------------------------------------------------
# Threat-intelligence linkage -- non-hash categories (Phase 3E)
# ----------------------------------------------------------------


def test_ipv4_linked_to_existing_threat_intel_record(service):
    investigation = make_investigation(
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={
            "ips": [
                {
                    "ip": "1.2.3.4",
                    "verdict": "Malicious",
                    "detection_ratio": "8/70",
                },
            ],
        },
    )

    report = service.correlate(investigation)

    links = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK
    ]

    assert len(links) == 1
    assert "Malicious" in links[0].reason


def test_domain_linked_to_existing_threat_intel_record(service):
    investigation = make_investigation(
        iocs={"domains": ["evilcorp.com"]},
        threat_intelligence={
            "domains": [
                {
                    "domain": "evilcorp.com",
                    "verdict": "Malicious",
                    "detection_ratio": "20/70",
                },
            ],
        },
    )

    report = service.correlate(investigation)

    links = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK
    ]

    assert len(links) == 1
    assert "Malicious" in links[0].reason


def test_url_linked_to_existing_threat_intel_record(service):
    investigation = make_investigation(
        iocs={"urls": ["https://evilcorp.com/payload.exe"]},
        threat_intelligence={
            "urls": [
                {
                    "url": "https://evilcorp.com/payload.exe",
                    "verdict": "Suspicious",
                    "detection_ratio": "4/70",
                },
            ],
        },
    )

    report = service.correlate(investigation)

    links = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK
    ]

    assert len(links) == 1
    assert "Suspicious" in links[0].reason


def test_non_hash_ti_link_created_when_no_sha256_present(service):
    """
    A non-hash TI-link relationship must be generated even when the
    investigation has no SHA256 hashes at all.
    """

    investigation = make_investigation(
        iocs={
            "ipv4": ["1.2.3.4"],
            "domains": ["evilcorp.com"],
            "urls": ["https://evilcorp.com/payload.exe"],
        },
        threat_intelligence={
            "ips": [{"ip": "1.2.3.4", "verdict": "Malicious"}],
            "domains": [{"domain": "evilcorp.com", "verdict": "Malicious"}],
            "urls": [
                {"url": "https://evilcorp.com/payload.exe", "verdict": "Malicious"}
            ],
        },
    )

    report = service.correlate(investigation)

    links = [
        r for r in report.results if r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK
    ]

    assert len(links) == 3


# ==========================================================
# Empty / invalid data
# ==========================================================


def test_empty_investigation_produces_empty_report(service):
    investigation = make_investigation()

    report = service.correlate(investigation)

    assert report.results == []
    assert report.summary.total_evidence_count == 0
    assert report.summary.relationship_count == 0


def test_investigation_with_no_relationships_has_empty_results_but_nonzero_summary(
    service,
):
    investigation = make_investigation(iocs={"ipv4": ["1.2.3.4", "5.6.7.8"]})

    report = service.correlate(investigation)

    assert report.results == []
    assert report.summary.total_evidence_count == 2
    assert report.summary.shared_investigation_evidence_count == 2


def test_malformed_url_value_does_not_crash_correlation(service):
    investigation = make_investigation(
        iocs={"domains": ["evil.com"], "urls": ["not a url at all"]},
    )

    report = service.correlate(investigation)

    # Must not raise, and must not produce a false match.
    assert not any(
        r.relationship_type == RELATIONSHIP_DOMAIN_URL_HOST for r in report.results
    )


def test_missing_threat_intelligence_field_handled(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={},
    )

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK for r in report.results
    )


def test_threat_intel_record_missing_sha256_key_ignored(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={"hashes": [{"verdict": "Malicious"}]},
    )

    report = service.correlate(investigation)

    assert not any(
        r.relationship_type == RELATIONSHIP_THREAT_INTEL_LINK for r in report.results
    )


# ==========================================================
# Determinism and ordering
# ==========================================================


def test_correlation_is_deterministic(service):
    investigation = make_investigation(
        iocs={
            "domains": ["Evil.com", "evil.com"],
            "urls": ["https://evil.com/x"],
            "sha256": ["a" * 64],
        },
        threat_intelligence={
            "hashes": [{"sha256": "a" * 64, "verdict": "Malicious", "detection_ratio": "1/2"}],
        },
    )

    first = service.correlate(investigation)
    second = service.correlate(investigation)

    assert [
        (r.relationship_type, r.primary.value, r.related.value) for r in first.results
    ] == [
        (r.relationship_type, r.primary.value, r.related.value) for r in second.results
    ]


def test_correlated_evidence_count_never_exceeds_total(service):
    # Regression test: a threat-intel link's synthetic
    # "threat_intelligence" related-evidence side must not be
    # counted as extracted evidence, which would otherwise let
    # correlated_evidence_count exceed total_evidence_count.
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={
            "hashes": [
                {"sha256": "a" * 64, "verdict": "Malicious", "detection_ratio": "1/2"},
            ],
        },
    )

    report = service.correlate(investigation)

    assert report.summary.total_evidence_count == 1
    assert report.summary.correlated_evidence_count <= report.summary.total_evidence_count
    assert report.summary.correlated_evidence_count == 1


def test_results_ordered_by_relationship_priority(service):
    investigation = make_investigation(
        iocs={
            "domains": ["Evil.com", "evil.com"],
            "urls": ["https://evil.com/x"],
            "sha256": ["a" * 64],
        },
        threat_intelligence={
            "hashes": [{"sha256": "a" * 64, "verdict": "Malicious", "detection_ratio": "1/2"}],
        },
    )

    report = service.correlate(investigation)

    priorities = [r.priority for r in report.results]

    assert priorities == sorted(priorities)
    # Duplicate-IOC (priority 1) sorts ahead of a threat-intel link
    # (priority 4) given both are present here.
    assert report.results[0].relationship_type == RELATIONSHIP_DUPLICATE_IOC
