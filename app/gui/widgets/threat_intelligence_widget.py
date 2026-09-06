"""
Reusable Threat Intelligence widget for the SOC-IQ desktop application.

This widget displays VirusTotal enrichment results
for a completed investigation.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.components.feedback.empty_state import EmptyState
from app.gui.widgets.threat_intelligence_details_dialog import (
    ThreatIntelligenceDetailsDialog,
)


class ThreatIntelligenceWidget(QWidget):
    """
    Displays Threat Intelligence information.
    """

    # Maps each TI category key (as stored on
    # `investigation.threat_intelligence`) to the record field that
    # holds the indicator's value and a display label for the
    # "Type" column. Order here is also display order in the
    # aggregate table -- hashes first, matching the pre-Phase-3E
    # behavior, so existing row-index expectations are unaffected
    # for hash-only investigations.
    _TI_CATEGORIES: tuple[tuple[str, str, str], ...] = (
        ("hashes", "sha256", "SHA256"),
        ("ips", "ip", "IPv4"),
        ("domains", "domain", "Domain"),
        ("urls", "url", "URL"),
    )

    def __init__(self) -> None:
        super().__init__()

        self._threat_data: list[dict] = []

        # Compact "what does the overall enrichment state look
        # like" summary line, set via `load_investigation()`'s
        # `overview` argument. Hidden while empty (e.g. before an
        # investigation is loaded) so it never shows a stale label.
        self._overview_label = QLabel("")

        self._overview_label.setWordWrap(True)

        self._overview_label.setVisible(False)

        # Shown instead of the table when there is nothing to list
        # (no SHA256 hashes were extracted, no API key is
        # configured, etc.) -- see `_apply_overview()`. Reuses the
        # existing design-system empty state rather than leaving an
        # analyst looking at a bare, unexplained 0-row table.
        self._empty_state = EmptyState(
            "No Threat Intelligence Data",
            "This investigation has no threat-intelligence records "
            "to display.",
        )

        self._empty_state.setVisible(False)

        self._table = QTableWidget()

        self._table.setColumnCount(4)

        self._table.setHorizontalHeaderLabels(
            [
                "Indicator",
                "Type",
                "Verdict",
                "Detection Ratio",
            ]
        )

        self._table.verticalHeader().setVisible(
            False,
        )

        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )

        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )

        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection,
        )

        self._table.horizontalHeader().setStretchLastSection(
            True,
        )

        self._table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )

        self._build_ui()

        self._table.cellDoubleClicked.connect(
            self._open_details,
        )

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.addWidget(
            self._overview_label,
        )

        layout.addWidget(
            self._table,
        )

        layout.addWidget(
            self._empty_state,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
        overview: dict | None = None,
    ) -> None:
        """
        Display threat intelligence for an investigation.

        Args:
            investigation:
                The investigation to display.
            overview:
                Optional result of
                `build_investigation_threat_intel_overview()`. When
                provided, drives the summary label above the table
                and the empty-state message shown when there are no
                enriched records -- so the analyst sees *why*
                nothing is listed (no API key, no hash indicators,
                provider error, ...) instead of a bare empty table.
        """

        threat_intelligence = (
            investigation.threat_intelligence or {}
        )

        # Aggregate all four enrichable TI categories (hashes, ips,
        # domains, urls) into one flat, displayable list. Each entry
        # keeps its original record plus the value/type this widget
        # needs, so downstream code (details dialog, selection) can
        # keep working with the original record shape.
        self._threat_data = []

        for category, value_field, type_label in self._TI_CATEGORIES:

            for record in threat_intelligence.get(category, []) or []:

                if not record.get(value_field):
                    continue

                self._threat_data.append(
                    {
                        "record": record,
                        "value_field": value_field,
                        "type_label": type_label,
                    }
                )

        self._apply_overview(overview)

        self._table.setRowCount(
            len(self._threat_data),
        )

        for row, entry in enumerate(
            self._threat_data,
        ):

            record = entry["record"]

            value = record.get(
                entry["value_field"],
                "Unknown",
            )

            verdict = record.get(
                "verdict",
                "Unknown",
            )

            detection_ratio = record.get(
                "detection_ratio",
                "N/A",
            )

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    str(value),
                ),
            )

            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    entry["type_label"],
                ),
            )

            self._table.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(verdict),
                ),
            )

            self._table.setItem(
                row,
                3,
                QTableWidgetItem(
                    str(detection_ratio),
                ),
            )

        self._table.resizeColumnsToContents()

    def _apply_overview(
        self,
        overview: dict | None,
    ) -> None:
        """
        Update the summary label and switch between the table and
        the empty state, based on whether there is any data to
        show and (optionally) the investigation-level overview.
        """

        has_data = bool(self._threat_data)

        self._table.setVisible(has_data)

        self._empty_state.setVisible(not has_data)

        if overview is not None:

            if has_data:

                self._overview_label.setText(
                    overview["message"],
                )

                self._overview_label.setVisible(True)

            else:

                self._overview_label.setVisible(False)

                self._empty_state.set_description(
                    overview["message"],
                )

        else:

            self._overview_label.setVisible(False)

    def _open_details(
        self,
        row: int,
        column: int,
    ) -> None:
        """
        Open the complete threat intelligence
        record for the selected row.
        """

        if not self._threat_data:
            return

        if row < 0:
            return

        if row >= len(self._threat_data):
            return

        dialog = ThreatIntelligenceDetailsDialog(
            "Threat Intelligence Details",
            self._threat_data[row],
        )

        dialog.exec()

    def select_indicator(
        self,
        value: str,
    ) -> bool:
        """
        Select and scroll to the row for a given indicator value.

        Used to drive the "IOC -> Threat Intelligence" drill-down
        from the IOC Details view: when an analyst asks to see the
        enrichment record for a specific indicator (SHA256, IPv4,
        domain, or URL), this focuses that exact row instead of
        leaving them to scan the table. Each row's own value field
        (see `_TI_CATEGORIES`) is checked, so a match is found
        regardless of which of the four categories the indicator
        belongs to.

        Returns:
            True if a matching row was found and selected, False
            otherwise (e.g. the investigation was reloaded and the
            indicator is no longer present).
        """

        for row, entry in enumerate(
            self._threat_data,
        ):

            record = entry["record"]

            if record.get(entry["value_field"]) != value:
                continue

            self._table.selectRow(
                row,
            )

            self._table.scrollToItem(
                self._table.item(
                    row,
                    0,
                ),
            )

            return True

        return False

    def select_hash(
        self,
        sha256: str,
    ) -> bool:
        """
        Select and scroll to the row for a given SHA256 hash.

        Backward-compatible alias for `select_indicator()`, kept so
        existing callers written specifically for hash lookups
        don't need to change. New code -- and any caller that may
        be handed a non-hash indicator -- should call
        `select_indicator()` directly.

        Returns:
            True if a matching row was found and selected, False
            otherwise.
        """

        return self.select_indicator(
            sha256,
        )

    def reset(
        self,
    ) -> None:
        """
        Reset the widget.
        """

        self._threat_data.clear()

        self._table.setRowCount(
            0,
        )

        self._overview_label.setVisible(False)

        self._empty_state.setVisible(False)

        self._table.setVisible(True)