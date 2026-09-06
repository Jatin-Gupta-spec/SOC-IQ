"""
Tests for the Phase 3C-2 "Why this risk?" analyst decision context
UI: `RiskExplanationWidget` (app/gui/widgets/risk_explanation_widget.py)
and its integration into `InvestigationWorkspacePage`
(app/gui/pages/investigation_workspace.py).

Covers:
  * RiskExplanationWidget renders a `RiskExplanation` directly:
    narrative, score/severity, contributing evidence, and that no
    unsupported per-category point claim is ever shown when the
    breakdown is unverified.
  * Empty states: no contributing evidence, no correlations.
  * Error state: a safe message is shown, never a raw exception.
  * InvestigationWorkspacePage wires a real investigation through
    `RiskExplanationService` into the widget, respects the
    currently selected investigation, refreshes on investigation
    switch without leaking stale data, and completes the
    "Risk explanation -> Contributing IOC -> IOC context" and
    "Risk explanation -> Correlation -> Related evidence"
    drill-downs using existing navigation.
  * A service failure is handled safely (no crash, no raw
    exception shown).

These are real Qt widgets under an offscreen QApplication (see
tests/gui/conftest.py), matching the existing style of
tests/gui/test_investigation_workspace_threat_intel.py.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.gui.pages.investigation_workspace import InvestigationWorkspacePage
from app.gui.widgets.ioc_details_widget import IOCDetailsWidget
from app.gui.widgets.risk_explanation_widget import RiskExplanationWidget
from app.services.correlation_models import (
    RELATIONSHIP_DUPLICATE_IOC,
    CorrelatedEvidence,
    CorrelationReport,
    CorrelationResult,
    CorrelationSummary,
)
from app.services.risk_explanation_models import (
    IocCategoryContribution,
    RiskExplanation,
)
from app.services.risk_explanation_service import RiskExplanationService


def _make_investigation(**overrides) -> Investigation:
    """
    Build a minimal, valid Investigation for widget/page tests,
    matching the fixture style already used by
    tests/gui/test_investigation_workspace_threat_intel.py.
    """

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
                },
            ],
            "status": "ok",
            "coverage": {"requested": 2, "succeeded": 2},
        },
        # sha256 weight 6 * 2 + ipv4 weight 1 * 1 = 13, so this
        # matches the real scoring engine's weights and yields a
        # verified breakdown by default.
        risk_score=80,
        severity="HIGH",
        confidence=0.9,
        ioc_score=13,
        threat_intel_score=70,
        cve_score=10,
        analyzed_at=datetime.now(UTC),
        investigation_id=1,
    )

    defaults.update(overrides)

    return Investigation(**defaults)


def _make_explanation(**overrides) -> RiskExplanation:
    """
    Build a `RiskExplanation` directly, for widget-level tests that
    don't need a full `RiskExplanationService.explain()` call.
    """

    defaults = dict(
        investigation_id=1,
        report_name="sample_report.txt",
        score=80,
        severity="HIGH",
        confidence=0.9,
        ioc_score=12,
        threat_intel_score=70,
        cve_score=0,
        ioc_categories=[
            IocCategoryContribution(
                ioc_type="sha256",
                ioc_type_title="SHA256 Hash",
                count=2,
                weight=6,
                significance="High",
                points=12,
            ),
        ],
        ioc_breakdown_verified=True,
        threat_intel_state="enriched",
        threat_intel_message="1/2 hash indicator(s) were enriched.",
        threat_intel_short_label="Enriched (1/2)",
        threat_intel_requested=2,
        threat_intel_succeeded=1,
        threat_intel_malicious_hash_count=1,
        threat_intel_suspicious_hash_count=0,
        correlation_evaluated=True,
        correlation_relationship_count=1,
        correlation_summary=(
            "1 relationship(s) were identified across 2 of this "
            "investigation's evidence item(s)."
        ),
        narrative=[
            "This investigation is rated HIGH with a risk score of "
            "80/100 (confidence 0.90).",
            "12 of the total score come from extracted IOC evidence.",
        ],
        warnings=[],
    )

    defaults.update(overrides)

    return RiskExplanation(**defaults)


# --------------------------------------------------------------------
# RiskExplanationWidget
# --------------------------------------------------------------------


def test_widget_renders_narrative(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    explanation = _make_explanation()

    widget.load_explanation(explanation)

    for sentence in explanation.narrative:
        assert sentence in widget._narrative_label.text()


def test_widget_shows_verified_contribution_points(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation())

    assert widget._evidence_table.isVisible()
    assert widget._evidence_table.rowCount() == 1
    assert widget._evidence_table.item(0, 0).text() == "SHA256 Hash"
    assert widget._evidence_table.item(0, 3).text() == "12 pts"


def test_widget_omits_points_when_breakdown_unverified(qapp):
    """
    PHASE3C-2 section 6: never display an unsupported per-category
    point claim.
    """

    widget = RiskExplanationWidget()
    widget.show()

    explanation = _make_explanation(ioc_breakdown_verified=False)

    widget.load_explanation(explanation)

    contribution_cell = widget._evidence_table.item(0, 3).text()

    assert contribution_cell == "Not itemized"
    assert "12" not in contribution_cell


def test_widget_shows_warnings_when_present(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    explanation = _make_explanation(
        warnings=["The per-category IOC point breakdown was unverified."],
    )

    widget.load_explanation(explanation)

    assert widget._warnings_label.isVisible()
    assert "unverified" in widget._warnings_label.text()


def test_widget_hides_warnings_when_absent(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation(warnings=[]))

    assert not widget._warnings_label.isVisible()


def test_widget_no_evidence_shows_empty_state(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    explanation = _make_explanation(ioc_categories=[])

    widget.load_explanation(explanation)

    assert not widget._evidence_table.isVisible()
    assert widget._evidence_empty_state.isVisible()


def test_widget_no_correlation_relationships_hides_view_button(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    explanation = _make_explanation(
        correlation_evaluated=True,
        correlation_relationship_count=0,
        correlation_summary=(
            "No supported deterministic relationships were "
            "identified among this investigation's evidence."
        ),
    )

    widget.load_explanation(explanation)

    assert not widget._view_correlations_button.isVisible()
    assert "No supported" in widget._correlation_label.text()


def test_widget_correlation_relationships_shows_view_button(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation())

    assert widget._view_correlations_button.isVisible()


def test_widget_view_correlations_button_emits_signal(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation())

    received = []
    widget.correlation_view_requested.connect(lambda: received.append(True))

    widget._view_correlations_button.click()

    assert received == [True]


def test_widget_evidence_row_click_emits_category(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation())

    received = []
    widget.evidence_category_selected.connect(received.append)

    widget._evidence_table.cellClicked.emit(0, 0)

    assert received == ["sha256"]


def test_widget_show_error_hides_content_and_never_leaks_exception(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation())

    widget.show_error("boom: raw traceback should never land here")

    # The widget itself never invents this text -- it only shows
    # whatever safe message the caller passed. This test asserts
    # the *mechanism* (content hidden, error shown) works; callers
    # are responsible for never passing a raw exception message
    # (see InvestigationWorkspacePage._load_risk_explanation, which
    # always uses the widget's own safe default).
    assert not widget._content.isVisible()
    assert widget._error_state.isVisible()


def test_widget_reset_clears_state(qapp):
    widget = RiskExplanationWidget()
    widget.show()

    widget.load_explanation(_make_explanation())
    widget.show_error()

    widget.reset()

    assert widget._content.isVisible()
    assert not widget._error_state.isVisible()
    assert widget._narrative_label.text() == ""
    assert widget._evidence_table.rowCount() == 0
    assert not widget._view_correlations_button.isVisible()


# --------------------------------------------------------------------
# InvestigationWorkspacePage integration
# --------------------------------------------------------------------


def test_workspace_loads_real_risk_explanation(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    widget = workspace._risk_explanation_widget

    assert widget._content.isVisible()
    assert "HIGH" in widget._narrative_label.text()
    assert "80" in widget._narrative_label.text()
    assert widget._evidence_table.rowCount() == 2


def test_workspace_switching_investigation_refreshes_explanation(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    first = _make_investigation(
        investigation_id=1,
        iocs={"sha256": ["aaa111", "bbb222"]},
        ioc_score=12,
        severity="HIGH",
        risk_score=80,
    )
    workspace.load_investigation(first)

    widget = workspace._risk_explanation_widget

    assert widget._evidence_table.rowCount() == 1
    assert "HIGH" in widget._narrative_label.text()

    second = _make_investigation(
        investigation_id=2,
        iocs={"ipv4": ["9.9.9.9"]},
        ioc_score=1,
        severity="LOW",
        risk_score=5,
        confidence=0.2,
    )
    workspace.load_investigation(second)

    assert widget._evidence_table.rowCount() == 1
    assert widget._evidence_table.item(0, 0).text() == "IPv4 Address"
    assert "LOW" in widget._narrative_label.text()
    # The stale HIGH-severity investigation's data must not survive
    # into the second investigation's explanation.
    assert "aaa111" not in widget._narrative_label.text()


def test_workspace_reset_clears_risk_explanation(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    workspace._reset_workspace()

    widget = workspace._risk_explanation_widget

    assert widget._narrative_label.text() == ""
    assert widget._evidence_table.rowCount() == 0


def test_workspace_no_investigation_no_crash(qapp):
    """
    PHASE3C-2 section 15: "no selected investigation" must not
    crash the workspace.
    """

    workspace = InvestigationWorkspacePage()
    workspace.show()

    # No investigation was ever loaded -- refresh() should have
    # already reset to the empty state during __init__.
    assert workspace._empty_state.isVisible()
    assert not workspace._tab_widget.isVisible()


def test_workspace_evidence_selection_drills_to_ioc_tab(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    workspace._risk_explanation_widget.evidence_category_selected.emit(
        "sha256",
    )

    assert workspace._tab_widget.currentIndex() == workspace._TAB_IOCS

    details = workspace._ioc_details_widget

    assert not details._table.isColumnHidden(
        IOCDetailsWidget._COLUMN_THREAT_INTEL,
    )
    assert details._table.rowCount() == 2


def test_workspace_correlation_view_drills_to_correlations_tab(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    workspace._tab_widget.setCurrentIndex(workspace._TAB_OVERVIEW)

    workspace._risk_explanation_widget.correlation_view_requested.emit()

    assert workspace._tab_widget.currentIndex() == workspace._TAB_CORRELATIONS


def test_workspace_handles_risk_explanation_service_failure(qapp, monkeypatch):
    """
    PHASE3C-2 section 10: a service failure must not crash the
    workspace or leave a raw exception on screen.
    """

    workspace = InvestigationWorkspacePage()
    workspace.show()

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated failure with sensitive traceback details")

    monkeypatch.setattr(
        workspace._risk_explanation_service,
        "explain",
        _boom,
    )

    investigation = _make_investigation()

    # Must not raise.
    workspace.load_investigation(investigation)

    widget = workspace._risk_explanation_widget

    assert widget._error_state.isVisible()
    assert not widget._content.isVisible()
    assert "simulated failure" not in widget._error_state._description.text()

    # The rest of the workspace (existing risk score) must still be
    # correct and unaffected by the explanation failure.
    assert workspace._risk_summary_widget._risk_score_row._value_label.text() == "80"


def test_workspace_no_ioc_evidence_empty_state(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation(
        iocs={},
        ioc_score=0,
    )
    workspace.load_investigation(investigation)

    widget = workspace._risk_explanation_widget

    assert not widget._evidence_table.isVisible()
    assert widget._evidence_empty_state.isVisible()


def test_workspace_no_correlations_empty_state(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation(iocs={"ipv4": ["1.2.3.4"]})
    workspace.load_investigation(investigation)

    widget = workspace._risk_explanation_widget

    # A single, uncorrelated IOC yields zero relationships.
    assert not widget._view_correlations_button.isVisible()


# --------------------------------------------------------------------
# RiskExplanationService wiring sanity (real service, real
# CorrelationReport, not just the domain-layer tests already in
# tests/test_risk_explanation_service.py)
# --------------------------------------------------------------------


def test_workspace_passes_real_correlation_report_to_service(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation(
        iocs={
            "domains": ["Example.com"],
            "urls": ["https://example.com/malware"],
        },
        ioc_score=5,
    )

    workspace.load_investigation(investigation)

    widget = workspace._risk_explanation_widget

    # domains weight 2 + urls weight 3 = 5, matches ioc_score above,
    # so this is a verified breakdown with a real correlation
    # relationship (domain/URL host match) surfaced through to the
    # explanation.
    assert widget._view_correlations_button.isVisible()
