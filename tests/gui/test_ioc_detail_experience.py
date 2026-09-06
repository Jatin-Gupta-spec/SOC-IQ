"""
Tests for the Phase 2 Part 2A "select an IOC -> see its full
detail" experience.

Covers:
  * IOCDetailsWidget's "View Details" button/context-menu action:
    enabled state tracks row selection, emits the raw category key
    + value, and existing copy/threat-intel-drilldown behavior is
    unaffected.
  * IOCDetailDialog renders each threat-intelligence state
    correctly and only offers the "view full record" action when
    enriched.
  * InvestigationWorkspacePage wires row selection through to
    ApplicationState and to the dialog with the correct context,
    handles a missing investigation safely, and the dialog's
    "view record" action reuses the existing drill-down to the
    Threat Intelligence tab.

These are real Qt widgets under an offscreen QApplication (see
tests/gui/conftest.py), not mocks.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.gui.events.application_state import ApplicationState
from app.gui.pages.investigation_workspace import InvestigationWorkspacePage
from app.services.ioc_detail_context import (
    TI_STATE_ENRICHED,
    TI_STATE_NO_API_KEY,
    TI_STATE_UNSUPPORTED_TYPE,
    build_ioc_detail_context,
)
from app.gui.widgets.ioc_detail_dialog import IOCDetailDialog
from app.gui.widgets.ioc_details_widget import IOCDetailsWidget


def _make_investigation(**overrides) -> Investigation:
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
                    "reputation": -20,
                    "last_analysis_date": "2026-01-01T00:00:00+00:00",
                },
            ],
            "status": "ok",
            "coverage": {
                "status": "ok",
                "requested": 1,
                "succeeded": 1,
                "failed": 0,
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


# --------------------------------------------------------------------
# IOCDetailsWidget -- View Details selection/emission
# --------------------------------------------------------------------


def test_view_details_disabled_with_no_iocs(qapp):
    widget = IOCDetailsWidget()

    widget.display_iocs("ipv4", [])

    assert widget._view_details_button.isEnabled() is False


def test_view_details_enabled_after_populate_auto_selects_first_row(qapp):
    """
    `_populate_table()` auto-selects the first row whenever there
    are values to show, so "View Details" should already be usable
    right after a category is picked, without an extra click.
    """

    widget = IOCDetailsWidget()

    widget.display_iocs("ipv4", ["1.2.3.4"])

    assert widget._view_details_button.isEnabled() is True


def test_view_details_emits_type_and_value(qapp):
    widget = IOCDetailsWidget()

    widget.display_iocs("sha256", ["aaa111", "bbb222"])

    widget._table.selectRow(1)

    received: list[tuple[str, str]] = []
    widget.ioc_detail_requested.connect(
        lambda ioc_type, value: received.append((ioc_type, value)),
    )

    widget._request_selected_ioc_detail()

    assert received == [("sha256", "bbb222")]


def test_view_details_does_nothing_without_selection(qapp):
    widget = IOCDetailsWidget()

    widget.display_iocs("ipv4", [])

    received: list[tuple[str, str]] = []
    widget.ioc_detail_requested.connect(
        lambda ioc_type, value: received.append((ioc_type, value)),
    )

    widget._request_selected_ioc_detail()

    assert received == []


def test_reset_disables_view_details_and_clears_category_key(qapp):
    widget = IOCDetailsWidget()

    widget.display_iocs("sha256", ["aaa111"])
    widget._table.selectRow(0)

    widget.reset()

    assert widget._view_details_button.isEnabled() is False
    assert widget._current_category_key == ""


def test_existing_double_click_copy_still_works_alongside_view_details(qapp):
    """
    Adding "View Details" must not disturb the pre-existing
    double-click-to-copy behavior pinned by Part 1's tests.
    """

    widget = IOCDetailsWidget()

    widget.display_iocs("ipv4", ["1.2.3.4"])

    received: list[str] = []
    widget.copy_completed.connect(received.append)

    item = widget._table.item(0, IOCDetailsWidget._COLUMN_VALUE)
    widget._double_click_copy(item)

    assert received == ["IOC copied to clipboard"]


# --------------------------------------------------------------------
# IOCDetailDialog
# --------------------------------------------------------------------


def test_dialog_shows_view_record_button_when_enriched(qapp):
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {"aaa111": investigation.threat_intelligence["hashes"][0]},
        api_key_configured=True,
    )

    dialog = IOCDetailDialog(context)

    assert context["threat_intel"]["state"] == TI_STATE_ENRICHED
    assert hasattr(dialog, "_view_record_button")


def test_dialog_has_no_view_record_button_when_unsupported(qapp):
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "emails",
        "user@example.com",
        {},
        api_key_configured=True,
    )

    dialog = IOCDetailDialog(context)

    assert context["threat_intel"]["state"] == TI_STATE_UNSUPPORTED_TYPE
    assert not hasattr(dialog, "_view_record_button")


def test_dialog_has_no_view_record_button_when_no_api_key(qapp):
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {},
        api_key_configured=False,
    )

    dialog = IOCDetailDialog(context)

    assert context["threat_intel"]["state"] == TI_STATE_NO_API_KEY
    assert not hasattr(dialog, "_view_record_button")


def test_dialog_view_record_click_emits_signal_with_value(qapp):
    investigation = _make_investigation()

    context = build_ioc_detail_context(
        investigation,
        "sha256",
        "aaa111",
        {"aaa111": investigation.threat_intelligence["hashes"][0]},
        api_key_configured=True,
    )

    dialog = IOCDetailDialog(context)

    received: list[str] = []
    dialog.threat_intel_requested.connect(received.append)

    dialog._on_view_record_clicked()

    assert received == ["aaa111"]


# --------------------------------------------------------------------
# InvestigationWorkspacePage integration
# --------------------------------------------------------------------


def test_workspace_records_selected_ioc_on_application_state(qapp):
    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    ApplicationState.select_investigation(investigation)

    # Avoid actually opening a blocking modal dialog in the test --
    # patch IOCDetailDialog.exec() to a no-op, since the goal here is
    # to verify wiring (selection recorded, dialog gets the right
    # context), not modal event-loop behavior.
    from app.gui.widgets import ioc_detail_dialog as dialog_module

    original_exec = dialog_module.IOCDetailDialog.exec
    dialog_module.IOCDetailDialog.exec = lambda self: None

    try:
        workspace._on_ioc_detail_requested("sha256", "aaa111")
    finally:
        dialog_module.IOCDetailDialog.exec = original_exec

    selected = ApplicationState.get_selected_ioc()

    assert selected is not None
    assert selected.ioc_type == "sha256"
    assert selected.value == "aaa111"

    ApplicationState.clear_current_investigation()


def test_workspace_handles_missing_investigation_gracefully(qapp):
    workspace = InvestigationWorkspacePage()

    received: list[str] = []
    workspace.status_message.connect(received.append)

    # No investigation loaded -- must not raise, and must tell the
    # analyst rather than silently doing nothing.
    workspace._on_ioc_detail_requested("sha256", "aaa111")

    assert received == ["No investigation is currently loaded."]


def test_workspace_dialog_view_record_reuses_threat_intel_drilldown(qapp):
    """
    The dialog's "view full record" action must land the analyst on
    the same Threat Intelligence tab/row as the existing Part 1
    drill-down, not a second parallel navigation path.
    """

    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    from app.gui.widgets import ioc_detail_dialog as dialog_module

    created_dialogs = []
    original_init = dialog_module.IOCDetailDialog.__init__

    def _capturing_init(self, context, parent=None):
        original_init(self, context, parent)
        created_dialogs.append(self)

    dialog_module.IOCDetailDialog.__init__ = _capturing_init
    dialog_module.IOCDetailDialog.exec = lambda self: None

    try:
        workspace._on_ioc_detail_requested("sha256", "aaa111")
    finally:
        dialog_module.IOCDetailDialog.__init__ = original_init
        dialog_module.IOCDetailDialog.exec = (
            dialog_module.QDialog.exec
        )

    assert len(created_dialogs) == 1

    created_dialogs[0]._on_view_record_clicked()

    assert workspace._tab_widget.currentIndex() == (
        workspace._TAB_THREAT_INTEL
    )
