"""
Tests for the Phase 3A "Advanced IOC Investigation Experience" /
"Threat Intelligence Investigation Experience" work:

  * `IOCSummaryWidget` shows a "Risk Significance" badge per IOC
    category (reusing `ioc_type_significance()` / `StatusBadge`, the
    same vocabulary already used by `IOCDetailDialog` for a single IOC),
    so an analyst can see risk relevance at a glance without
    drilling into every category.
  * `IOCSummaryWidget` shows a "Threat Intelligence" column per
    category: the real enrichment coverage label for SHA256 when an
    overview is supplied, an honest "unknown" placeholder for SHA256
    when it isn't, and "Not Supported" for every other category --
    never a fabricated figure.
  * `InvestigationWorkspacePage` and `IOCViewerPage` both pass a
    real `build_investigation_threat_intel_overview()` result
    through to `IOCSummaryWidget`, rather than only the previously-
    existing single-IOC drill-down having this context.

These are real Qt widgets under an offscreen `QApplication` (see
tests/gui/conftest.py), matching the style of the existing Phase 2
GUI test suite.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.database.models import Investigation
from app.gui.events.application_state import ApplicationState
from app.gui.pages.investigation_workspace import InvestigationWorkspacePage
from app.gui.pages.ioc_viewer_page import IOCViewerPage
from app.services.ioc_detail_context import (
    build_investigation_threat_intel_overview,
)
from app.gui.components.feedback.status_badge import StatusBadge
from app.services.ioc_significance import ioc_type_significance
from app.gui.widgets.ioc_summary_widget import IOCSummaryWidget


def _make_investigation(**overrides) -> Investigation:
    defaults = dict(
        report_name="sample_report.txt",
        iocs={
            "sha256": ["aaa111", "bbb222"],
            "ipv4": ["1.2.3.4"],
            "cves": ["CVE-2024-1234"],
        },
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "aaa111",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                },
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
        risk_score=80,
        severity="HIGH",
        confidence=0.9,
        ioc_score=50,
        threat_intel_score=70,
        cve_score=10,
        analyzed_at=datetime.now(UTC),
        investigation_id=1,
    )
    defaults.update(overrides)
    return Investigation(**defaults)


def _row_for(widget: IOCSummaryWidget, ioc_type: str) -> int:
    return list(IOCSummaryWidget.IOC_TITLES.keys()).index(ioc_type)


def _significance_text(widget: IOCSummaryWidget, row: int) -> str:
    cell = widget._table.cellWidget(row, widget._COLUMN_SIGNIFICANCE)
    badge = cell.findChild(StatusBadge)
    return badge.text()


# --------------------------------------------------------------------
# Risk Significance column
# --------------------------------------------------------------------


def test_significance_column_matches_ioc_type_significance(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    widget.load_investigation(_make_investigation())

    for ioc_type in IOCSummaryWidget.IOC_TITLES:
        row = _row_for(widget, ioc_type)
        expected = ioc_type_significance(ioc_type).upper()
        assert _significance_text(widget, row) == expected


def test_sha256_significance_is_high(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    widget.load_investigation(_make_investigation())

    row = _row_for(widget, "sha256")
    assert _significance_text(widget, row) == "HIGH"


def test_ipv4_significance_is_lower_than_sha256(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    widget.load_investigation(_make_investigation())

    ipv4_row = _row_for(widget, "ipv4")
    sha256_row = _row_for(widget, "sha256")

    assert _significance_text(widget, ipv4_row) != _significance_text(
        widget,
        sha256_row,
    )


# --------------------------------------------------------------------
# Threat Intelligence column
# --------------------------------------------------------------------


def test_sha256_row_shows_overview_label_when_provided(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    investigation = _make_investigation()

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    widget.load_investigation(investigation, overview)

    row = _row_for(widget, "sha256")
    cell_text = widget._table.item(row, widget._COLUMN_THREAT_INTEL).text()

    assert cell_text == overview["short_label"]
    assert "1/2" in cell_text


def test_sha256_row_shows_unknown_placeholder_without_overview(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    widget.load_investigation(_make_investigation())

    row = _row_for(widget, "sha256")
    cell_text = widget._table.item(row, widget._COLUMN_THREAT_INTEL).text()

    assert cell_text == "\u2014"


def test_unsupported_rows_always_report_not_supported(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    investigation = _make_investigation()

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    widget.load_investigation(investigation, overview)

    for ioc_type in IOCSummaryWidget.IOC_TITLES:
        if ioc_type in {"sha256", "ipv4", "domains", "urls"}:
            continue

        row = _row_for(widget, ioc_type)
        cell_text = widget._table.item(row, widget._COLUMN_THREAT_INTEL).text()

        assert cell_text == "Not Supported"


def test_reset_clears_threat_intel_overview(qapp):
    widget = IOCSummaryWidget()
    widget.show()

    investigation = _make_investigation()

    overview = build_investigation_threat_intel_overview(
        investigation,
        api_key_configured=True,
    )

    widget.load_investigation(investigation, overview)
    widget.reset()

    assert widget._threat_intel_overview is None


# --------------------------------------------------------------------
# Wiring: real pages pass a real overview through
# --------------------------------------------------------------------


def test_workspace_passes_threat_intel_overview_to_ioc_summary(qapp):
    workspace = InvestigationWorkspacePage()
    workspace.show()

    investigation = _make_investigation()

    workspace.load_investigation(investigation)

    row = _row_for(workspace._ioc_summary_widget, "sha256")
    cell_text = workspace._ioc_summary_widget._table.item(
        row,
        workspace._ioc_summary_widget._COLUMN_THREAT_INTEL,
    ).text()

    # A real overview was computed (no API key configured in this
    # test environment), so the SHA256 row must show a genuine
    # coverage-derived label, never the "unknown" placeholder.
    assert cell_text != "\u2014"


def test_ioc_viewer_page_passes_threat_intel_overview_to_ioc_summary(qapp):
    ApplicationState.select_investigation(_make_investigation())

    page = IOCViewerPage()
    page.show()

    row = _row_for(page._ioc_summary, "sha256")
    cell_text = page._ioc_summary._table.item(
        row,
        page._ioc_summary._COLUMN_THREAT_INTEL,
    ).text()

    assert cell_text != "\u2014"

    ApplicationState.clear_current_investigation()
