"""
Tests for the "selected IOC" tracking added to `ApplicationState`
for Phase 2 Part 2A.

Covers:
  * Selecting/clearing an individual IOC independent of the
    current investigation.
  * A newly selected investigation clears any previously selected
    IOC, since a selected IOC belongs to whichever investigation
    was active when it was picked.
  * Explicitly clearing the current investigation also clears the
    selected IOC.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import Investigation
from app.gui.events.application_state import ApplicationState, SelectedIOC


def _make_investigation(investigation_id: int) -> Investigation:
    return Investigation(
        report_name="report.txt",
        iocs={"sha256": ["aaa111"], "ipv4": ["1.2.3.4"]},
        threat_intelligence={},
        risk_score=10,
        severity="LOW",
        confidence=0.5,
        ioc_score=5,
        threat_intel_score=0,
        cve_score=0,
        analyzed_at=datetime.now(UTC),
        investigation_id=investigation_id,
    )


def test_set_and_get_selected_ioc(qapp):
    ApplicationState.select_investigation(_make_investigation(1))

    ApplicationState.set_selected_ioc("sha256", "aaa111")

    selected = ApplicationState.get_selected_ioc()

    assert selected == SelectedIOC(ioc_type="sha256", value="aaa111")

    ApplicationState.clear_current_investigation()


def test_no_selected_ioc_by_default(qapp):
    ApplicationState.clear_current_investigation()

    assert ApplicationState.get_selected_ioc() is None


def test_clear_selected_ioc(qapp):
    ApplicationState.select_investigation(_make_investigation(1))
    ApplicationState.set_selected_ioc("sha256", "aaa111")

    ApplicationState.clear_selected_ioc()

    assert ApplicationState.get_selected_ioc() is None

    ApplicationState.clear_current_investigation()


def test_selecting_a_new_investigation_clears_the_selected_ioc(qapp):
    ApplicationState.select_investigation(_make_investigation(1))
    ApplicationState.set_selected_ioc("sha256", "aaa111")

    assert ApplicationState.get_selected_ioc() is not None

    ApplicationState.select_investigation(_make_investigation(2))

    assert ApplicationState.get_selected_ioc() is None

    ApplicationState.clear_current_investigation()


def test_clearing_the_current_investigation_clears_the_selected_ioc(qapp):
    ApplicationState.select_investigation(_make_investigation(1))
    ApplicationState.set_selected_ioc("sha256", "aaa111")

    ApplicationState.clear_current_investigation()

    assert ApplicationState.get_selected_ioc() is None
    assert ApplicationState.get_current_investigation() is None
