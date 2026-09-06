"""
Tests for `app.services.dashboard_aggregation` (Phase 4H Part 1).

Pure functions over a `list[Investigation]` -- no database, no
network, no Qt. Written with pytest to match this repo's newer test
files (e.g. tests/test_dashboard_services.py), which this module's
functions were extracted out of.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.services.dashboard_aggregation import (
    compute_dashboard_metrics,
    compute_ioc_distribution,
    compute_severity_distribution,
    compute_status_counts,
    compute_threat_intel_coverage_percent,
)


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="report.txt",
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={"status": "ok"},
        risk_score=10,
        severity="LOW",
        confidence=0.5,
        ioc_score=1,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime(2024, 3, 15, 9, 30, tzinfo=UTC),
    )
    defaults.update(overrides)
    return Investigation(**defaults)


# ==========================================================
# compute_ioc_distribution
# ==========================================================


def test_ioc_distribution_empty_when_no_investigations():
    assert compute_ioc_distribution([]) == {}


def test_ioc_distribution_sums_across_investigations():
    investigations = [
        make_investigation(iocs={"ipv4": ["1.1.1.1", "2.2.2.2"], "domains": ["a.com"]}),
        make_investigation(iocs={"ipv4": ["3.3.3.3"]}),
    ]

    assert compute_ioc_distribution(investigations) == {"ipv4": 3, "domains": 1}


def test_ioc_distribution_handles_investigation_with_no_iocs():
    investigations = [make_investigation(iocs={})]

    assert compute_ioc_distribution(investigations) == {}


# ==========================================================
# compute_severity_distribution
# ==========================================================


def test_severity_distribution_empty_when_no_investigations():
    assert compute_severity_distribution([]) == {}


def test_severity_distribution_groups_by_severity():
    investigations = [
        make_investigation(severity="LOW"),
        make_investigation(severity="LOW"),
        make_investigation(severity="HIGH"),
        make_investigation(severity="CRITICAL"),
    ]

    assert compute_severity_distribution(investigations) == {
        "LOW": 2,
        "HIGH": 1,
        "CRITICAL": 1,
    }


def test_severity_distribution_is_case_insensitive():
    investigations = [
        make_investigation(severity="critical"),
        make_investigation(severity="Critical"),
        make_investigation(severity="CRITICAL"),
    ]

    assert compute_severity_distribution(investigations) == {"CRITICAL": 3}


def test_severity_distribution_groups_missing_severity_as_unknown():
    investigations = [make_investigation(severity=""), make_investigation(severity=None)]

    assert compute_severity_distribution(investigations) == {"UNKNOWN": 2}


# ==========================================================
# compute_status_counts
# ==========================================================


def test_status_counts_empty_when_no_investigations():
    assert compute_status_counts([]) == {}


def test_status_counts_groups_by_real_status_field():
    investigations = [
        make_investigation(status="COMPLETED"),
        make_investigation(status="COMPLETED"),
    ]

    assert compute_status_counts(investigations) == {"COMPLETED": 2}


def test_status_counts_does_not_invent_workflow_vocabulary():
    # Regression guard: this must never fabricate an
    # open/in_progress/closed-style breakdown that does not exist in
    # persisted data -- see the function's own docstring.
    investigations = [make_investigation(status="COMPLETED")]

    result = compute_status_counts(investigations)

    assert "open" not in result
    assert "in_progress" not in result
    assert "closed" not in result
    assert result == {"COMPLETED": 1}


def test_status_counts_groups_missing_status_as_unknown():
    investigations = [make_investigation(status="")]

    assert compute_status_counts(investigations) == {"UNKNOWN": 1}


# ==========================================================
# compute_dashboard_metrics
# ==========================================================


def test_dashboard_metrics_all_zero_when_no_investigations():
    assert compute_dashboard_metrics([]) == {
        "report_count": 0,
        "total_iocs": 0,
        "high_risk": 0,
    }


def test_dashboard_metrics_counts_reports_and_iocs():
    investigations = [
        make_investigation(iocs={"ipv4": ["1.1.1.1", "2.2.2.2"]}, severity="LOW"),
        make_investigation(iocs={"domains": ["a.com"]}, severity="MEDIUM"),
    ]

    metrics = compute_dashboard_metrics(investigations)

    assert metrics["report_count"] == 2
    assert metrics["total_iocs"] == 3
    assert metrics["high_risk"] == 0


@pytest.mark.parametrize(
    "severities,expected_high_risk",
    [
        (["LOW", "MEDIUM"], 0),
        (["HIGH"], 1),
        (["CRITICAL"], 1),
        (["HIGH", "CRITICAL", "LOW"], 2),
        (["high", "Critical"], 2),
    ],
)
def test_dashboard_metrics_high_risk_counts_high_and_critical_only(
    severities, expected_high_risk
):
    investigations = [make_investigation(severity=severity) for severity in severities]

    metrics = compute_dashboard_metrics(investigations)

    assert metrics["high_risk"] == expected_high_risk


# ==========================================================
# compute_threat_intel_coverage_percent
# ==========================================================


def test_threat_intel_coverage_none_when_no_investigations():
    assert compute_threat_intel_coverage_percent([]) is None


def test_threat_intel_coverage_none_when_nothing_ever_requested():
    investigations = [
        make_investigation(threat_intelligence={}),
        make_investigation(
            threat_intelligence={"status": "no_indicators", "coverage": {"requested": 0, "succeeded": 0}}
        ),
    ]

    assert compute_threat_intel_coverage_percent(investigations) is None


def test_threat_intel_coverage_computed_from_persisted_counts():
    investigations = [
        make_investigation(
            threat_intelligence={"coverage": {"requested": 4, "succeeded": 3}}
        ),
        make_investigation(
            threat_intelligence={"coverage": {"requested": 6, "succeeded": 3}}
        ),
    ]

    # (3 + 3) / (4 + 6) * 100 = 60.0
    assert compute_threat_intel_coverage_percent(investigations) == 60.0


def test_threat_intel_coverage_zero_percent_when_every_request_failed():
    investigations = [
        make_investigation(
            threat_intelligence={"coverage": {"requested": 5, "succeeded": 0}}
        ),
    ]

    # Genuine 0% -- distinct from "no data at all" (None).
    assert compute_threat_intel_coverage_percent(investigations) == 0.0


def test_threat_intel_coverage_ignores_malformed_coverage_data():
    investigations = [
        make_investigation(
            threat_intelligence={"coverage": {"requested": "not-a-number", "succeeded": 1}}
        ),
        make_investigation(
            threat_intelligence={"coverage": {"requested": 2, "succeeded": 2}}
        ),
    ]

    # The malformed entry is skipped entirely rather than crashing or
    # being coerced into a guess.
    assert compute_threat_intel_coverage_percent(investigations) == 100.0


def test_threat_intel_coverage_rounds_to_one_decimal_place():
    investigations = [
        make_investigation(
            threat_intelligence={"coverage": {"requested": 3, "succeeded": 1}}
        ),
    ]

    # 1/3 * 100 = 33.333... -> rounded, not truncated or fabricated
    # extra precision.
    assert compute_threat_intel_coverage_percent(investigations) == 33.3
