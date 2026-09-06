"""
Reusable Evidence Correlation widget for the SOC-IQ desktop
application.

Displays deterministic relationships between evidence already
present in the current investigation, as produced by
`CorrelationService` (app/services/correlation_service.py) and
converted to display rows by
`app.gui.services.investigation_correlation_context`.

This widget does not calculate any correlation itself -- it only
renders a `CorrelationReport` it is given.
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

from app.gui.components.feedback.empty_state import EmptyState
from app.gui.services.investigation_correlation_context import (
    build_correlation_rows,
    build_correlation_summary_text,
)
from app.services.correlation_models import CorrelationReport

_COLUMN_PRIMARY = 0
_COLUMN_RELATIONSHIP = 1
_COLUMN_RELATED = 2
_COLUMN_REASON = 3


class CorrelationWidget(QWidget):
    """
    Displays evidence correlations for the current investigation.
    """

    def __init__(self) -> None:
        super().__init__()

        self._summary_label = QLabel("")

        self._summary_label.setWordWrap(True)

        self._summary_label.setVisible(False)

        # Shown instead of the table when there are no relationships
        # to list -- either because the investigation has no
        # evidence at all, or because no supported deterministic
        # relationship was found among the evidence it does have
        # (see PHASE3_PART3B section 17: "Correlation Empty State").
        self._empty_state = EmptyState(
            "No Correlations Found",
            "No supported deterministic relationships were "
            "identified from the available evidence.",
        )

        self._empty_state.setVisible(False)

        self._table = QTableWidget()

        self._table.setColumnCount(4)

        self._table.setHorizontalHeaderLabels(
            [
                "Primary Evidence",
                "Relationship",
                "Related Evidence",
                "Reason",
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

        self._table.setAlternatingRowColors(
            True,
        )

        self._table.setWordWrap(
            False,
        )

        header = self._table.horizontalHeader()

        header.setStretchLastSection(
            True,
        )

        header.setSectionResizeMode(
            _COLUMN_PRIMARY,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            _COLUMN_RELATIONSHIP,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            _COLUMN_RELATED,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self._build_ui()

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
            self._summary_label,
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

    def load_report(self, report: CorrelationReport) -> None:
        """
        Display a correlation report.

        Args:
            report:
                The `CorrelationReport` produced by
                `CorrelationService.correlate()` for the current
                investigation.
        """

        rows = build_correlation_rows(report)

        self._summary_label.setText(
            build_correlation_summary_text(report),
        )

        self._summary_label.setVisible(True)

        has_rows = bool(rows)

        self._table.setVisible(has_rows)

        self._empty_state.setVisible(not has_rows)

        self._table.setRowCount(len(rows))

        for row_index, row in enumerate(rows):

            self._table.setItem(
                row_index,
                _COLUMN_PRIMARY,
                QTableWidgetItem(
                    f"{row.primary_type_title}: {row.primary_value}",
                ),
            )

            self._table.setItem(
                row_index,
                _COLUMN_RELATIONSHIP,
                QTableWidgetItem(
                    row.relationship_label,
                ),
            )

            self._table.setItem(
                row_index,
                _COLUMN_RELATED,
                QTableWidgetItem(
                    f"{row.related_type_title}: {row.related_value}",
                ),
            )

            self._table.setItem(
                row_index,
                _COLUMN_REASON,
                QTableWidgetItem(
                    row.reason,
                ),
            )

        self._table.resizeColumnsToContents()

    def reset(self) -> None:
        """
        Reset the widget.
        """

        self._table.setRowCount(0)

        self._summary_label.setVisible(False)

        self._empty_state.setVisible(False)

        self._table.setVisible(True)
