"""
Tests for the Phase 3C-1 risk explanation service
(app.services.risk_explanation_service.RiskExplanationService).

Covers: basic score/severity passthrough, IOC evidence
(high/low-weight categories, multiple categories, no IOC data),
threat-intelligence states (available, unavailable, missing,
provider error), correlation (present / not evaluated),
consistency with the existing score/severity, determinism, that no
unsupported per-IOC numeric claim is made when the breakdown cannot
be verified, and safe handling of empty/missing input.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.services.correlation_models import (
    CorrelatedEvidence,
    CorrelationReport,
    CorrelationResult,
    CorrelationSummary,
    RELATIONSHIP_DUPLICATE_IOC,
)
from app.services.risk_explanation_service import (
    RiskExplanationService,
)


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="sample_report.txt",
        iocs={},
        threat_intelligence={},
        risk_score=0,
        severity="LOW",
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime.now(UTC),
        investigation_id=1,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


@pytest.fixture()
def service() -> RiskExplanationService:
    return RiskExplanationService()


# ==========================================================
# Basic: score / severity / confidence passthrough
# ==========================================================


def test_explanation_never_disagrees_with_existing_score(service):
    investigation = make_investigation(
        risk_score=55,
        severity="HIGH",
        confidence=0.8,
    )

    result = service.explain(investigation)

    assert result.score == 55
    assert result.severity == "HIGH"
    assert result.confidence == 0.8
    assert "HIGH" in result.narrative[0]
    assert "55" in result.narrative[0]


def test_explanation_no_evidence(service):
    investigation = make_investigation()

    result = service.explain(investigation)

    assert result.ioc_categories == []
    # Vacuously verified: an empty breakdown sums to 0, matching a
    # 0 ioc_score -- no warning is raised for a genuinely empty
    # investigation.
    assert result.ioc_breakdown_verified is True
    assert "No IOC evidence" in result.narrative[1]
    assert result.warnings == []  # no IOCs -> no breakdown warning


# ==========================================================
# IOC evidence
# ==========================================================


def test_high_weight_ioc_category(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        ioc_score=6,
    )

    result = service.explain(investigation)

    assert result.ioc_breakdown_verified is True
    assert len(result.ioc_categories) == 1
    category = result.ioc_categories[0]
    assert category.ioc_type == "sha256"
    assert category.significance == "High"
    assert category.points == 6


def test_low_weight_ioc_category(service):
    investigation = make_investigation(
        iocs={"ipv4": ["1.2.3.4"]},
        ioc_score=1,
    )

    result = service.explain(investigation)

    assert result.ioc_breakdown_verified is True
    category = result.ioc_categories[0]
    assert category.significance == "Low"
    assert category.points == 1


def test_multiple_ioc_categories(service):
    investigation = make_investigation(
        iocs={
            "sha256": ["a" * 64],
            "ipv4": ["1.2.3.4", "5.6.7.8"],
            "domains": ["example.com"],
        },
        ioc_score=(1 * 6) + (2 * 1) + (1 * 2),
    )

    result = service.explain(investigation)

    assert result.ioc_breakdown_verified is True
    assert {c.ioc_type for c in result.ioc_categories} == {
        "sha256",
        "ipv4",
        "domains",
    }
    # Highest-points category sorts first (sha256: 6 pts).
    assert result.ioc_categories[0].ioc_type == "sha256"


def test_no_ioc_data_categories_empty(service):
    investigation = make_investigation(iocs={})

    result = service.explain(investigation)

    assert result.ioc_categories == []
    # Vacuously verified: empty breakdown sums to 0, matching the
    # default 0 ioc_score.
    assert result.ioc_breakdown_verified is True


def test_unverified_ioc_breakdown_omits_numeric_claim_in_narrative(
    service,
):
    """
    If the persisted ioc_score does not match what the public
    weight table would produce (e.g. the engine's weighting
    diverged from this decomposition), the narrative must not
    assert a specific numeric per-category contribution -- only
    describe the categories qualitatively, per PHASE3C-1 section 8.
    """

    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        ioc_score=999,  # deliberately inconsistent with weight * count
    )

    result = service.explain(investigation)

    assert result.ioc_breakdown_verified is False
    assert any(
        "did not sum" in warning for warning in result.warnings
    )

    ioc_narrative = result.narrative[1]
    assert "999" in ioc_narrative  # aggregate score still reported
    assert "contribute to the existing risk assessment" in (
        ioc_narrative
    )
    # No per-category numeric ("6 points", "X pts") claim.
    assert "largest single contributor" not in ioc_narrative


def test_cve_score_reported_separately_from_ioc_weighting(service):
    investigation = make_investigation(
        iocs={"cves": ["CVE-2024-0001"]},
        ioc_score=8,
        cve_score=10,
    )

    result = service.explain(investigation)

    assert any(
        "discovered CVE" in line for line in result.narrative
    )
    assert result.ioc_categories[0].ioc_type == "cves"
    assert result.ioc_categories[0].points == 8


# ==========================================================
# Threat intelligence
# ==========================================================


def test_threat_intel_available(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        ioc_score=6,  # matches weight(sha256)=6 * count=1
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "a" * 64,
                    "verdict": "Malicious",
                    "malicious": 3,
                    "suspicious": 0,
                }
            ],
            "status": "ok",
            "coverage": {"requested": 1, "succeeded": 1},
        },
        threat_intel_score=15,
    )

    result = service.explain(
        investigation, api_key_configured=True
    )

    assert result.threat_intel_state == "enriched"
    assert result.threat_intel_malicious_hash_count == 1
    assert result.threat_intel_suspicious_hash_count == 0
    assert "checked against VirusTotal" in (
        result.threat_intel_message
    )
    assert result.warnings == []


def test_threat_intel_unavailable_no_api_key(service):
    # `coverage.requested` must be > 0 for the overview builder to
    # even consider the "no API key" state -- with requested == 0
    # it reads as "no hash indicators were extracted" instead (see
    # build_investigation_threat_intel_overview()), which is the
    # real shape analyzer.py's MissingAPIKeyError branch actually
    # produces. This test exercises the state as a state, using a
    # coverage shape where hashes were identified but the key is
    # absent.
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={
            "hashes": [],
            "status": "unavailable",
            "reason": "missing_api_key",
            "coverage": {"requested": 1, "succeeded": 0},
        },
    )

    result = service.explain(
        investigation, api_key_configured=False
    )

    assert result.threat_intel_state == "no_api_key"
    assert "No VirusTotal API key" in result.threat_intel_message
    assert any(
        "incomplete" in warning for warning in result.warnings
    )


def test_threat_intel_missing_api_key_no_coverage_reads_as_not_enriched(
    service,
):
    """
    The real shape `app/analyzer.py` produces when
    `MissingAPIKeyError` is raised (no `coverage` key at all) is
    honestly reported as "not enriched" rather than fabricating a
    more specific state the underlying data doesn't support -- this
    is existing, pre-Phase-3C-1 behavior of
    `build_investigation_threat_intel_overview()`, reused as-is.
    """

    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        ioc_score=6,  # matches weight(sha256)=6 * count=1
        threat_intelligence={
            "hashes": [],
            "status": "unavailable",
            "reason": "missing_api_key",
        },
    )

    result = service.explain(
        investigation, api_key_configured=False
    )

    assert result.threat_intel_state == "not_enriched"
    assert result.warnings == []


def test_threat_intel_missing_entirely(service):
    investigation = make_investigation(iocs={}, threat_intelligence={})

    result = service.explain(investigation)

    assert result.threat_intel_state == "not_enriched"
    assert (
        "No threat-intelligence check has been recorded"
        in result.threat_intel_message
    )
    assert result.warnings == []  # not_enriched is not "incomplete"


def test_threat_intel_provider_error(service):
    investigation = make_investigation(
        iocs={"sha256": ["a" * 64]},
        threat_intelligence={
            "hashes": [],
            "status": "partial",
            "coverage": {
                "requested": 1,
                "succeeded": 0,
                "rate_limited": True,
            },
        },
    )

    result = service.explain(
        investigation, api_key_configured=True
    )

    assert result.threat_intel_state == "provider_error"
    assert "rate limit" in result.threat_intel_message.lower()
    assert any(
        "incomplete" in warning for warning in result.warnings
    )


# ----------------------------------------------------------------
# Threat intelligence -- non-hash categories (Phase 3E parity)
# ----------------------------------------------------------------


def test_risk_explanation_counts_malicious_non_hash_records(service):
    """
    A malicious IP/domain/URL verdict must be reflected in the
    analyst-facing malicious/suspicious counts, not just malicious
    SHA256 hashes.
    """

    investigation = make_investigation(
        iocs={"ipv4": ["1.2.3.4"], "domains": ["evilcorp.com"]},
        threat_intelligence={
            "hashes": [],
            "ips": [
                {
                    "ip": "1.2.3.4",
                    "verdict": "Malicious",
                    "malicious": 5,
                    "suspicious": 0,
                }
            ],
            "domains": [
                {
                    "domain": "evilcorp.com",
                    "verdict": "Suspicious",
                    "malicious": 0,
                    "suspicious": 2,
                }
            ],
            "status": "ok",
            "coverage": {"requested": 2, "succeeded": 2},
        },
        threat_intel_score=27,
    )

    result = service.explain(
        investigation, api_key_configured=True
    )

    assert result.threat_intel_state == "enriched"
    assert result.threat_intel_malicious_hash_count == 1
    assert result.threat_intel_suspicious_hash_count == 1


def test_risk_explanation_counts_malicious_url_record(service):
    investigation = make_investigation(
        iocs={"urls": ["https://evilcorp.com/payload.exe"]},
        threat_intelligence={
            "hashes": [],
            "urls": [
                {
                    "url": "https://evilcorp.com/payload.exe",
                    "verdict": "Malicious",
                    "malicious": 10,
                    "suspicious": 0,
                }
            ],
            "status": "ok",
            "coverage": {"requested": 1, "succeeded": 1},
        },
        threat_intel_score=50,
    )

    result = service.explain(
        investigation, api_key_configured=True
    )

    assert result.threat_intel_malicious_hash_count == 1


def test_risk_explanation_counts_span_all_four_categories_together(service):
    investigation = make_investigation(
        iocs={
            "sha256": ["a" * 64],
            "ipv4": ["1.2.3.4"],
            "domains": ["evilcorp.com"],
            "urls": ["https://evilcorp.com/payload.exe"],
        },
        threat_intelligence={
            "hashes": [{"sha256": "a" * 64, "verdict": "Malicious"}],
            "ips": [{"ip": "1.2.3.4", "verdict": "Malicious"}],
            "domains": [{"domain": "evilcorp.com", "verdict": "Suspicious"}],
            "urls": [
                {"url": "https://evilcorp.com/payload.exe", "verdict": "Suspicious"}
            ],
            "status": "ok",
            "coverage": {"requested": 4, "succeeded": 4},
        },
        threat_intel_score=14,
    )

    result = service.explain(
        investigation, api_key_configured=True
    )

    assert result.threat_intel_malicious_hash_count == 2
    assert result.threat_intel_suspicious_hash_count == 2


# ==========================================================
# Correlation
# ==========================================================


def _correlation_report(count: int) -> CorrelationReport:
    if count == 0:
        return CorrelationReport(
            results=[],
            summary=CorrelationSummary(2, 0, 0, 2),
        )

    result = CorrelationResult(
        relationship_type=RELATIONSHIP_DUPLICATE_IOC,
        primary=CorrelatedEvidence("domains", "Example.com", "example.com"),
        related=CorrelatedEvidence("domains", "example.com", "example.com"),
        reason="Same normalized domain.",
    )
    return CorrelationReport(
        results=[result],
        summary=CorrelationSummary(2, 2, 1, 2),
    )


def test_correlations_present(service):
    investigation = make_investigation(
        iocs={"domains": ["Example.com", "example.com"]},
    )

    result = service.explain(
        investigation,
        correlation_report=_correlation_report(1),
    )

    assert result.correlation_evaluated is True
    assert result.correlation_relationship_count == 1
    assert "not an additional contribution" in (
        result.correlation_summary
    )


def test_no_correlations(service):
    investigation = make_investigation(
        iocs={"ipv4": ["1.2.3.4"], "domains": ["example.com"]},
    )

    result = service.explain(
        investigation,
        correlation_report=_correlation_report(0),
    )

    assert result.correlation_evaluated is True
    assert result.correlation_relationship_count == 0
    assert "No supported deterministic relationships" in (
        result.correlation_summary
    )


def test_correlation_not_supplied_is_distinct_from_zero(service):
    investigation = make_investigation()

    result = service.explain(investigation, correlation_report=None)

    assert result.correlation_evaluated is False
    assert "not evaluated" in result.correlation_summary


# ==========================================================
# Consistency
# ==========================================================


def test_consistency_across_severities(service):
    for severity, score in (
        ("LOW", 5),
        ("MEDIUM", 30),
        ("HIGH", 60),
        ("CRITICAL", 95),
    ):
        investigation = make_investigation(
            risk_score=score, severity=severity
        )
        result = service.explain(investigation)
        assert result.score == score
        assert result.severity == severity


# ==========================================================
# Determinism
# ==========================================================


def test_determinism(service):
    investigation = make_investigation(
        iocs={
            "sha256": ["a" * 64],
            "ipv4": ["1.2.3.4", "5.6.7.8"],
        },
        ioc_score=8,
        threat_intelligence={
            "hashes": [{"verdict": "Malicious"}],
            "status": "ok",
            "coverage": {"requested": 1, "succeeded": 1},
        },
        threat_intel_score=5,
    )

    first = service.explain(
        investigation,
        correlation_report=_correlation_report(1),
        api_key_configured=True,
    )
    second = service.explain(
        investigation,
        correlation_report=_correlation_report(1),
        api_key_configured=True,
    )

    assert first == second


# ==========================================================
# Unsupported claims
# ==========================================================


def test_no_unsupported_exact_point_claim_per_ioc(service):
    """
    The narrative should never claim that one specific IOC value
    changed the score by an exact amount -- only category-level,
    engine-exposed weight information.
    """

    investigation = make_investigation(
        iocs={"sha256": ["a" * 64, "b" * 64]},
        ioc_score=12,
    )

    result = service.explain(investigation)

    full_text = " ".join(result.narrative)
    assert "this exact IOC" not in full_text.lower()
    assert "increased the risk score by" not in full_text.lower()


# ==========================================================
# Empty input
# ==========================================================


def test_none_investigation_raises_safely(service):
    with pytest.raises(ValueError):
        service.explain(None)


def test_completely_empty_investigation_is_handled_safely(service):
    investigation = make_investigation(
        iocs={},
        threat_intelligence={},
        risk_score=0,
        severity="LOW",
        confidence=0.0,
        ioc_score=0,
        threat_intel_score=0,
        cve_score=0,
    )

    result = service.explain(investigation)

    assert result.score == 0
    assert result.ioc_categories == []
    assert result.threat_intel_state == "not_enriched"
    assert result.correlation_evaluated is False
    assert isinstance(result.narrative, list) and result.narrative
