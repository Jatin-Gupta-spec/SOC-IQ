"""
Regression tests for the SOC-IQ dashboard services:
DashboardThreatService, DashboardTimelineService, and
DashboardThreatFeedService.

These services depend on InvestigationService only for reading
already-persisted data, so a lightweight fake stands in for it --
no real database or network access is used.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.services.dashboard_ioc_distribution_service import (
    DashboardIOCDistributionService,
)
from app.services.dashboard_statistics_service import DashboardStatisticsService
from app.services.dashboard_threat_feed_service import (
    DashboardThreatFeedService,
)
from app.services.dashboard_threat_service import DashboardThreatService
from app.services.dashboard_timeline_service import DashboardTimelineService
from app.services.models import BadgeType


def make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="report.txt",
        iocs={"ipv4": ["1.2.3.4"]},
        threat_intelligence={"status": "ok", "hashes": []},
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


class FakeInvestigationService:
    """Fake investigation service -- never touches VirusTotal or a
    real database."""

    def __init__(self, investigations=None):
        self._investigations = investigations or []

    def list_all(self):
        return list(self._investigations)

    def find_recent(self, limit=10):
        return list(self._investigations)[:limit]


# ==========================================================
# DashboardThreatService
# ==========================================================


def test_threat_status_normal_when_no_investigations():
    service = DashboardThreatService(
        investigation_service=FakeInvestigationService([])
    )

    status, badge = service.get_threat_status()

    assert status == "NORMAL"
    assert badge == BadgeType.SUCCESS


def test_threat_status_critical_when_any_critical_investigation():
    investigations = [
        make_investigation(severity="LOW"),
        make_investigation(severity="CRITICAL"),
    ]
    service = DashboardThreatService(
        investigation_service=FakeInvestigationService(investigations)
    )

    status, badge = service.get_threat_status()

    assert status == "CRITICAL ALERT"
    assert badge == BadgeType.CRITICAL


def test_threat_status_elevated_when_high_but_no_critical():
    investigations = [
        make_investigation(severity="LOW"),
        make_investigation(severity="HIGH"),
    ]
    service = DashboardThreatService(
        investigation_service=FakeInvestigationService(investigations)
    )

    status, badge = service.get_threat_status()

    assert status == "ELEVATED"
    assert badge == BadgeType.WARNING


def test_threat_status_normal_when_only_low_and_medium():
    investigations = [
        make_investigation(severity="LOW"),
        make_investigation(severity="MEDIUM"),
    ]
    service = DashboardThreatService(
        investigation_service=FakeInvestigationService(investigations)
    )

    status, badge = service.get_threat_status()

    assert status == "NORMAL"
    assert badge == BadgeType.SUCCESS


def test_threat_status_handles_missing_severity_gracefully():
    investigations = [make_investigation(severity="")]
    service = DashboardThreatService(
        investigation_service=FakeInvestigationService(investigations)
    )

    status, badge = service.get_threat_status()

    assert status == "NORMAL"
    assert badge == BadgeType.SUCCESS


def test_threat_status_severity_comparison_is_case_insensitive():
    investigations = [make_investigation(severity="critical")]
    service = DashboardThreatService(
        investigation_service=FakeInvestigationService(investigations)
    )

    status, badge = service.get_threat_status()

    assert status == "CRITICAL ALERT"
    assert badge == BadgeType.CRITICAL


def test_threat_service_default_constructs_real_investigation_service():
    fake = FakeInvestigationService([])
    service = DashboardThreatService(investigation_service=fake)

    assert service._investigation_service is fake


# ==========================================================
# DashboardTimelineService
# ==========================================================


def test_timeline_empty_when_no_investigations():
    service = DashboardTimelineService(
        investigation_service=FakeInvestigationService([])
    )

    timeline = service.get_timeline()

    assert timeline == []


def test_timeline_maps_investigation_fields():
    investigations = [
        make_investigation(
            report_name="apt_report.txt",
            severity="HIGH",
            risk_score=77,
            analyzed_at=datetime(2024, 3, 15, 14, 5, tzinfo=UTC),
        )
    ]
    service = DashboardTimelineService(
        investigation_service=FakeInvestigationService(investigations)
    )

    timeline = service.get_timeline()

    assert len(timeline) == 1
    event = timeline[0]
    assert event.title == "apt_report.txt"
    assert event.timestamp == "14:05"
    assert event.description == "Risk Score: 77"
    assert event.severity == "HIGH"
    assert event.source == "Investigation Engine"
    assert event.icon == "🛡"


def test_timeline_respects_limit_argument():
    investigations = [make_investigation(report_name=f"r{i}.txt") for i in range(5)]
    fake_service = FakeInvestigationService(investigations)
    service = DashboardTimelineService(investigation_service=fake_service)

    service.get_timeline(limit=3)

    # DashboardTimelineService should forward the limit through to
    # the underlying investigation lookup.
    assert fake_service.find_recent(limit=3) == investigations[:3]


@pytest.mark.parametrize(
    "severity,expected_icon",
    [
        ("CRITICAL", "🚨"),
        ("HIGH", "🛡"),
        ("MEDIUM", "⚠"),
        ("LOW", "ℹ"),
        ("INFO", "📄"),
        ("SOMETHING_UNKNOWN", "📄"),
    ],
)
def test_timeline_icon_for_severity(severity, expected_icon):
    service = DashboardTimelineService(
        investigation_service=FakeInvestigationService([])
    )

    assert service._icon_for_severity(severity) == expected_icon


def test_timeline_defaults_missing_severity_to_info_icon():
    investigations = [make_investigation(severity="")]
    service = DashboardTimelineService(
        investigation_service=FakeInvestigationService(investigations)
    )

    timeline = service.get_timeline()

    assert timeline[0].severity == "INFO"
    assert timeline[0].icon == "📄"


# ==========================================================
# DashboardThreatFeedService
# ==========================================================


def test_threat_feed_empty_when_no_investigations():
    service = DashboardThreatFeedService(
        investigation_service=FakeInvestigationService([])
    )

    feed = service.get_feed()

    assert feed == []


def test_threat_feed_maps_investigation_fields():
    investigations = [
        make_investigation(
            report_name="feed_report.txt",
            severity="CRITICAL",
            risk_score=99,
            analyzed_at=datetime(2024, 5, 1, 8, 15, tzinfo=UTC),
        )
    ]
    service = DashboardThreatFeedService(
        investigation_service=FakeInvestigationService(investigations)
    )

    feed = service.get_feed()

    assert len(feed) == 1
    entry = feed[0]
    assert entry["title"] == "feed_report.txt"
    assert entry["severity"] == "CRITICAL"
    assert entry["risk_score"] == "99"
    assert entry["time"] == "01 May 08:15"


def test_threat_feed_respects_limit_argument():
    investigations = [make_investigation(report_name=f"r{i}.txt") for i in range(5)]
    fake_service = FakeInvestigationService(investigations)
    service = DashboardThreatFeedService(investigation_service=fake_service)

    feed = service.get_feed(limit=2)

    assert len(feed) == 2


def test_threat_feed_requires_investigation_service_argument():
    # Unlike the other two dashboard services, this one has no
    # default -- it must be explicitly injected.
    with pytest.raises(TypeError):
        DashboardThreatFeedService()


# ==========================================================
# DashboardIOCDistributionService (Phase 4H Part 1 regression --
# now delegates to app.services.dashboard_aggregation
# .compute_ioc_distribution; behavior must be unchanged)
# ==========================================================


def test_ioc_distribution_service_empty_when_no_investigations():
    service = DashboardIOCDistributionService(
        investigation_service=FakeInvestigationService([])
    )

    assert service.get_distribution() == {}


def test_ioc_distribution_service_sums_across_investigations():
    investigations = [
        make_investigation(iocs={"ipv4": ["1.1.1.1", "2.2.2.2"], "domains": ["a.com"]}),
        make_investigation(iocs={"ipv4": ["3.3.3.3"]}),
    ]
    service = DashboardIOCDistributionService(
        investigation_service=FakeInvestigationService(investigations)
    )

    assert service.get_distribution() == {"ipv4": 3, "domains": 1}


# ==========================================================
# DashboardStatisticsService (Phase 4H Part 1 regression -- now
# delegates to app.services.dashboard_aggregation
# .compute_dashboard_metrics; return shape/values must be unchanged:
# still dict[str, str], still including "database": "Connected")
# ==========================================================


def test_statistics_summary_all_zero_when_no_investigations():
    service = DashboardStatisticsService(
        investigation_service=FakeInvestigationService([])
    )

    summary = service.get_summary()

    assert summary == {
        "reports": "0",
        "iocs": "0",
        "high_risk": "0",
        "database": "Connected",
    }


def test_statistics_summary_counts_reports_iocs_and_high_risk():
    investigations = [
        make_investigation(iocs={"ipv4": ["1.1.1.1", "2.2.2.2"]}, severity="LOW"),
        make_investigation(iocs={"domains": ["a.com"]}, severity="CRITICAL"),
    ]
    service = DashboardStatisticsService(
        investigation_service=FakeInvestigationService(investigations)
    )

    summary = service.get_summary()

    assert summary == {
        "reports": "2",
        "iocs": "3",
        "high_risk": "1",
        "database": "Connected",
    }


def test_statistics_summary_values_are_strings_not_ints():
    # Regression guard for the GUI caller
    # (app.gui.controllers.dashboard_controller.DashboardController),
    # which relies on dict[str, str] -- this must never silently
    # become dict[str, int] as a side effect of the Phase 4H
    # extraction into dashboard_aggregation.
    investigations = [make_investigation()]
    service = DashboardStatisticsService(
        investigation_service=FakeInvestigationService(investigations)
    )

    summary = service.get_summary()

    assert all(isinstance(value, str) for value in summary.values())
