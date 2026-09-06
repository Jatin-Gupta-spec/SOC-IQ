"""
Tests for the Phase 2 Part 1 "Investigation -> IOC -> Threat
Intelligence" drill-down.

Covers:
  * IOCDetailsWidget shows/hides the Threat Intel column based on
    whether a lookup was supplied, and renders per-row verdicts.
  * Double-clicking an enriched Threat Intel cell requests
    navigation to that indicator's record; double-clicking a
    non-enriched cell does nothing.
  * InvestigationWorkspacePage wires IOC selection to the lookup,
    and wires the drill-down request to the Threat Intelligence tab
    and row selection.
  * ThreatIntelligenceWidget.select_hash() finds/selects a matching
    row and reports when no match exists.

These are real Qt widgets under an offscreen QApplication (see
tests/gui/conftest.py), not mocks -- the goal is to catch actual
wiring mistakes (wrong signal, wrong tab index, stale lookup) that
a pure-logic test would miss.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.database.models import Investigation
from app.gui.pages.investigation_workspace import InvestigationWorkspacePage
from app.gui.widgets.ioc_details_widget import IOCDetailsWidget
from app.gui.widgets.threat_intelligence_widget import ThreatIntelligenceWidget


def _make_investigation(**overrides) -> Investigation:
    """
    Build a minimal, valid Investigation for widget tests.
    """

    defaults = dict(
        report_name="sample_report.txt",
        iocs={
            "sha256": ["aaa111", "bbb222", "ccc333"],
            "ipv4": ["1.2.3.4"],
        },
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "aaa111",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                },
                {
                    "sha256": "bbb222",
                    "verdict": "Clean",
                    "detection_ratio": "0/70",
                },
            ],
            "status": "ok",
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
# IOCDetailsWidget
# --------------------------------------------------------------------


def test_threat_intel_column_hidden_without_lookup(qapp):
    widget = IOCDetailsWidget()

    widget.display_iocs("ipv4", ["1.2.3.4"])

    assert widget._table.isColumnHidden(
        IOCDetailsWidget._COLUMN_THREAT_INTEL,
    )


def test_threat_intel_column_shown_with_lookup(qapp):
    widget = IOCDetailsWidget()

    lookup = {
        "aaa111": {"sha256": "aaa111", "verdict": "Malicious"},
    }

    widget.display_iocs("sha256", ["aaa111", "bbb222"], lookup)

    assert not widget._table.isColumnHidden(
        IOCDetailsWidget._COLUMN_THREAT_INTEL,
    )

    assert widget._table.item(0, IOCDetailsWidget._COLUMN_THREAT_INTEL).text() == (
        "Malicious"
    )

    # bbb222 has no entry in the lookup -- must read as not enriched,
    # never as silently blank or as an error.
    assert widget._table.item(1, IOCDetailsWidget._COLUMN_THREAT_INTEL).text() == (
        "Not Enriched"
    )


def test_double_click_threat_intel_cell_emits_signal_for_enriched_value(qapp):
    widget = IOCDetailsWidget()

    lookup = {
        "aaa111": {"sha256": "aaa111", "verdict": "Malicious"},
    }

    widget.display_iocs("sha256", ["aaa111"], lookup)

    received: list[str] = []
    widget.threat_intel_requested.connect(received.append)

    item = widget._table.item(0, IOCDetailsWidget._COLUMN_THREAT_INTEL)
    widget._double_click_copy(item)

    assert received == ["aaa111"]


def test_double_click_threat_intel_cell_does_nothing_for_unenriched_value(qapp):
    widget = IOCDetailsWidget()

    lookup = {
        "aaa111": {"sha256": "aaa111", "verdict": "Malicious"},
    }

    widget.display_iocs("sha256", ["aaa111", "ccc333"], lookup)

    received: list[str] = []
    widget.threat_intel_requested.connect(received.append)

    item = widget._table.item(1, IOCDetailsWidget._COLUMN_THREAT_INTEL)
    widget._double_click_copy(item)

    assert received == []


def test_double_click_value_cell_still_copies_as_before(qapp):
    """
    The pre-existing "double-click a value to copy it" behavior must
    be unaffected by the new Threat Intel column.
    """

    widget = IOCDetailsWidget()

    widget.display_iocs("ipv4", ["1.2.3.4"])

    received: list[str] = []
    widget.copy_completed.connect(received.append)

    item = widget._table.item(0, IOCDetailsWidget._COLUMN_VALUE)
    widget._double_click_copy(item)

    assert received == ["IOC copied to clipboard"]


def test_reset_hides_threat_intel_column_and_clears_lookup(qapp):
    widget = IOCDetailsWidget()

    lookup = {"aaa111": {"sha256": "aaa111", "verdict": "Malicious"}}
    widget.display_iocs("sha256", ["aaa111"], lookup)

    widget.reset()

    assert widget._threat_intel_lookup is None
    assert widget._table.isColumnHidden(
        IOCDetailsWidget._COLUMN_THREAT_INTEL,
    )


# --------------------------------------------------------------------
# ThreatIntelligenceWidget.select_hash
# --------------------------------------------------------------------


def test_select_hash_finds_and_selects_matching_row(qapp):
    widget = ThreatIntelligenceWidget()

    investigation = _make_investigation()
    widget.load_investigation(investigation)

    found = widget.select_hash("bbb222")

    assert found is True
    assert widget._table.currentRow() == 1


def test_select_hash_returns_false_when_not_found(qapp):
    widget = ThreatIntelligenceWidget()

    investigation = _make_investigation()
    widget.load_investigation(investigation)

    assert widget.select_hash("does-not-exist") is False


# --------------------------------------------------------------------
# ThreatIntelligenceWidget -- multi-category display/selection (Phase 3E)
# --------------------------------------------------------------------


def _make_multi_type_investigation(**overrides) -> Investigation:
    """
    Investigation with an enriched record in each of the four TI
    categories, for exercising non-hash display/selection.
    """

    defaults = dict(
        report_name="multi_type_report.txt",
        iocs={
            "sha256": ["aaa111"],
            "ipv4": ["1.2.3.4"],
            "domains": ["evilcorp.com"],
            "urls": ["https://evilcorp.com/payload.exe"],
        },
        threat_intelligence={
            "hashes": [
                {
                    "sha256": "aaa111",
                    "verdict": "Malicious",
                    "detection_ratio": "10/70",
                },
            ],
            "ips": [
                {
                    "ip": "1.2.3.4",
                    "verdict": "Malicious",
                    "detection_ratio": "8/70",
                },
            ],
            "domains": [
                {
                    "domain": "evilcorp.com",
                    "verdict": "Suspicious",
                    "detection_ratio": "4/70",
                },
            ],
            "urls": [
                {
                    "url": "https://evilcorp.com/payload.exe",
                    "verdict": "Malicious",
                    "detection_ratio": "15/70",
                },
            ],
            "status": "ok",
        },
        risk_score=90,
        severity="CRITICAL",
        confidence=0.95,
        ioc_score=50,
        threat_intel_score=80,
        cve_score=10,
        analyzed_at=datetime.now(UTC),
        investigation_id=2,
    )

    defaults.update(overrides)

    return Investigation(**defaults)


def test_widget_displays_all_four_ti_categories(qapp):
    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    assert widget._table.rowCount() == 4

    type_labels = {
        widget._table.item(row, 1).text() for row in range(widget._table.rowCount())
    }

    assert type_labels == {"SHA256", "IPv4", "Domain", "URL"}


def test_widget_row_values_match_indicator_for_each_category(qapp):
    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    values_by_type = {
        widget._table.item(row, 1).text(): widget._table.item(row, 0).text()
        for row in range(widget._table.rowCount())
    }

    assert values_by_type["SHA256"] == "aaa111"
    assert values_by_type["IPv4"] == "1.2.3.4"
    assert values_by_type["Domain"] == "evilcorp.com"
    assert values_by_type["URL"] == "https://evilcorp.com/payload.exe"


def test_select_indicator_finds_sha256_row(qapp):
    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    assert widget.select_indicator("aaa111") is True
    assert widget._table.item(widget._table.currentRow(), 1).text() == "SHA256"


def test_select_indicator_finds_ipv4_row(qapp):
    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    assert widget.select_indicator("1.2.3.4") is True
    assert widget._table.item(widget._table.currentRow(), 1).text() == "IPv4"


def test_select_indicator_finds_domain_row(qapp):
    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    assert widget.select_indicator("evilcorp.com") is True
    assert widget._table.item(widget._table.currentRow(), 1).text() == "Domain"


def test_select_indicator_finds_url_row(qapp):
    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    assert (
        widget.select_indicator("https://evilcorp.com/payload.exe") is True
    )
    assert widget._table.item(widget._table.currentRow(), 1).text() == "URL"


def test_select_hash_alias_still_works_for_non_hash_indicator(qapp):
    """
    `select_hash()` is kept as a backward-compatible alias for
    `select_indicator()` -- it must still work for non-hash values
    passed to it by older call sites.
    """

    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    assert widget.select_hash("1.2.3.4") is True


def test_open_details_works_for_each_category(qapp, monkeypatch):
    """
    Double-clicking (via `_open_details`) must open successfully for
    every TI category, not just SHA256 hashes.
    """

    widget = ThreatIntelligenceWidget()

    widget.load_investigation(_make_multi_type_investigation())

    opened_payloads: list[dict] = []

    class _FakeDialog:
        def __init__(self, title, data):
            opened_payloads.append(data)

        def exec(self):
            return None

    monkeypatch.setattr(
        "app.gui.widgets.threat_intelligence_widget.ThreatIntelligenceDetailsDialog",
        _FakeDialog,
    )

    for row in range(widget._table.rowCount()):
        widget._open_details(row, 0)

    assert len(opened_payloads) == widget._table.rowCount()

    opened_type_labels = {payload["type_label"] for payload in opened_payloads}

    assert opened_type_labels == {"SHA256", "IPv4", "Domain", "URL"}


# --------------------------------------------------------------------
# InvestigationWorkspacePage integration
# --------------------------------------------------------------------


def test_workspace_attaches_threat_intel_lookup_for_sha256(qapp):
    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    workspace._ioc_summary_widget.ioc_selected.emit(
        "sha256",
        ["aaa111", "bbb222", "ccc333"],
    )

    details = workspace._ioc_details_widget

    assert not details._table.isColumnHidden(
        IOCDetailsWidget._COLUMN_THREAT_INTEL,
    )

    assert details._table.item(0, 1).text() == "Malicious"
    assert details._table.item(1, 1).text() == "Clean"
    assert details._table.item(2, 1).text() == "Not Enriched"


def test_workspace_does_not_attach_lookup_for_unsupported_categories(qapp):
    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    workspace._ioc_summary_widget.ioc_selected.emit("emails", ["test@example.com"])

    assert workspace._ioc_details_widget._table.isColumnHidden(
        IOCDetailsWidget._COLUMN_THREAT_INTEL,
    )


def test_workspace_drill_down_switches_to_threat_intel_tab_and_selects_row(qapp):
    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    workspace._tab_widget.setCurrentIndex(workspace._TAB_IOCS)

    workspace._on_threat_intel_requested("bbb222")

    assert workspace._tab_widget.currentIndex() == workspace._TAB_THREAT_INTEL
    assert workspace._threat_summary_widget._table.currentRow() == 1


def test_workspace_drill_down_reports_status_when_hash_missing(qapp):
    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    messages: list[str] = []
    workspace.status_message.connect(messages.append)

    workspace._on_threat_intel_requested("does-not-exist")

    assert len(messages) == 1
    assert "no longer available" in messages[0]


def test_workspace_reset_clears_threat_intel_lookup(qapp):
    workspace = InvestigationWorkspacePage()

    investigation = _make_investigation()
    workspace.load_investigation(investigation)

    assert workspace._threat_intel_by_value

    workspace._reset_workspace()

    assert workspace._threat_intel_by_value == {}
