"""
Reusable Risk Explanation widget for the SOC-IQ desktop application.

Renders a `RiskExplanation` (app/services/risk_explanation_models.py),
produced by `RiskExplanationService` (app/services/
risk_explanation_service.py, Phase 3C-1), as the analyst-facing
"Why this risk?" section of the Investigation Workspace (Phase
3C-2).

This widget performs no risk calculation and no data fetching of
its own -- it only renders a `RiskExplanation` it is given, the
same way `CorrelationWidget` only renders a `CorrelationReport` it
is given. Every value shown here already exists on the
`RiskExplanation`; this widget adds no numbers that service did not
already compute.

Traceability: clicking a contributing IOC category emits
`evidence_category_selected` so the page can drill into that
category's IOC details; clicking "View Related Evidence" emits
`correlation_view_requested` so the page can switch to the
Correlations tab. This widget does not perform navigation itself --
see PHASE3C-2 section 5 and section 12 ("do not introduce another
state manager").
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.feedback.empty_state import EmptyState
from app.services.risk_explanation_models import RiskExplanation

_COLUMN_CATEGORY = 0
_COLUMN_SIGNIFICANCE = 1
_COLUMN_INDICATORS = 2
_COLUMN_CONTRIBUTION = 3

# Shown in the Contribution column when the per-category point
# breakdown was not verified against the investigation's recorded
# IOC score (`RiskExplanation.ioc_breakdown_verified`). Naming a
# specific point value here would be an unsupported claim -- see
# PHASE3C-2 section 6 ("Important Claim Rule") -- so the column
# falls back to a qualitative label instead.
_CONTRIBUTION_NOT_ITEMIZED = "Not itemized"

# Default message shown when building the explanation failed. Never
# exposes the underlying exception to the analyst -- see PHASE3C-2
# section 10.
_DEFAULT_ERROR_MESSAGE = (
    "The risk explanation for this investigation could not be "
    "loaded. The existing risk score and severity above are "
    "unaffected."
)


class RiskExplanationWidget(QWidget):
    """
    Displays the "why this risk?" explanation for the current
    investigation: narrative summary, contributing IOC evidence,
    and correlation context. Threat-intelligence context is folded
    into the narrative (it is already shown in full on the Threat
    Intelligence tab) so this section stays concise rather than
    duplicating that table (see PHASE3C-2 section 11).
    """

    evidence_category_selected = Signal(str)
    correlation_view_requested = Signal()

    def __init__(self) -> None:
        super().__init__()

        # Wraps every "real content" widget below, so it can be
        # hidden as one unit whenever `show_error()` is showing the
        # error state instead (see `_set_error_visible()`).
        self._content = QWidget()

        self._narrative_label = QLabel("")
        self._narrative_label.setWordWrap(True)

        self._warnings_label = QLabel("")
        self._warnings_label.setWordWrap(True)
        self._warnings_label.setObjectName("riskExplanationWarnings")
        self._warnings_label.setVisible(False)

        self._evidence_table = QTableWidget()
        self._evidence_table.setColumnCount(4)
        self._evidence_table.setHorizontalHeaderLabels(
            [
                "IOC Category",
                "Significance",
                "Indicators",
                "Contribution",
            ]
        )
        self._evidence_table.verticalHeader().setVisible(False)
        self._evidence_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )
        self._evidence_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )
        self._evidence_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection,
        )
        self._evidence_table.setWordWrap(False)

        header = self._evidence_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(
            _COLUMN_CATEGORY,
            QHeaderView.ResizeMode.Stretch,
        )

        self._evidence_table.cellClicked.connect(
            self._on_evidence_row_clicked,
        )

        # Shown instead of the evidence table when the investigation
        # has no IOC evidence at all -- distinct from an unverified
        # breakdown, which still shows the table (see PHASE3C-2
        # section 9: "no evidence" empty state).
        self._evidence_empty_state = EmptyState(
            "No Contributing Evidence",
            "No IOC evidence was extracted for this investigation.",
        )
        self._evidence_empty_state.setVisible(False)

        self._correlation_label = QLabel("")
        self._correlation_label.setWordWrap(True)

        self._view_correlations_button = QPushButton(
            "View Related Evidence",
        )
        self._view_correlations_button.setVisible(False)
        self._view_correlations_button.clicked.connect(
            self.correlation_view_requested.emit,
        )

        # Shown instead of `self._content` when building the
        # explanation failed (see `show_error()`). Never displays
        # the raw exception -- PHASE3C-2 section 10.
        self._error_state = EmptyState(
            "Risk Explanation Unavailable",
            _DEFAULT_ERROR_MESSAGE,
        )
        self._error_state.setVisible(False)

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)

        content_layout.addWidget(self._narrative_label)
        content_layout.addWidget(self._warnings_label)
        content_layout.addWidget(self._evidence_table)
        content_layout.addWidget(self._evidence_empty_state)
        content_layout.addWidget(self._correlation_label)
        content_layout.addWidget(self._view_correlations_button)

        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(self._content)
        layout.addWidget(self._error_state)

        self.setLayout(layout)

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def load_explanation(self, explanation: RiskExplanation) -> None:
        """
        Display a `RiskExplanation` built for the current
        investigation.
        """

        self._set_error_visible(False)

        self._narrative_label.setText(
            "\n".join(
                f"\u2022 {sentence}" for sentence in explanation.narrative
            )
        )

        if explanation.warnings:
            self._warnings_label.setText(
                "\n".join(
                    f"Note: {warning}" for warning in explanation.warnings
                )
            )
            self._warnings_label.setVisible(True)
        else:
            self._warnings_label.setText("")
            self._warnings_label.setVisible(False)

        self._load_evidence_table(explanation)

        self._correlation_label.setText(explanation.correlation_summary)

        can_view_correlations = (
            explanation.correlation_evaluated
            and explanation.correlation_relationship_count > 0
        )

        self._view_correlations_button.setVisible(can_view_correlations)

    def show_error(self, message: str = _DEFAULT_ERROR_MESSAGE) -> None:
        """
        Show a safe, professional error message instead of an
        explanation, e.g. after `RiskExplanationService.explain()`
        raised. Never pass a raw exception message here -- see
        PHASE3C-2 section 10.
        """

        self._error_state.set_description(message)

        self._set_error_visible(True)

    def reset(self) -> None:
        """
        Reset the widget to its default, empty state.
        """

        self._set_error_visible(False)

        self._narrative_label.setText("")

        self._warnings_label.setText("")
        self._warnings_label.setVisible(False)

        self._evidence_table.setRowCount(0)
        self._evidence_table.setVisible(True)
        self._evidence_empty_state.setVisible(False)

        self._correlation_label.setText("")

        self._view_correlations_button.setVisible(False)

    # ------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------

    def _set_error_visible(self, visible: bool) -> None:
        """
        Toggle between the error state and normal content, as one
        unit.
        """

        self._content.setVisible(not visible)
        self._error_state.setVisible(visible)

    def _load_evidence_table(self, explanation: RiskExplanation) -> None:
        """
        Populate the contributing-evidence table from
        `explanation.ioc_categories`.
        """

        categories = explanation.ioc_categories

        has_categories = bool(categories)

        self._evidence_table.setVisible(has_categories)
        self._evidence_empty_state.setVisible(not has_categories)

        self._evidence_table.setRowCount(len(categories))

        for row, category in enumerate(categories):

            category_item = QTableWidgetItem(category.ioc_type_title)
            # Stash the raw type key (not the display title) on the
            # row's first item, so `_on_evidence_row_clicked()` can
            # emit the same key `IOCSummaryWidget.select_category()`
            # expects, without a second lookup table.
            category_item.setData(Qt.ItemDataRole.UserRole, category.ioc_type)

            self._evidence_table.setItem(
                row,
                _COLUMN_CATEGORY,
                category_item,
            )

            self._evidence_table.setItem(
                row,
                _COLUMN_SIGNIFICANCE,
                QTableWidgetItem(category.significance),
            )

            self._evidence_table.setItem(
                row,
                _COLUMN_INDICATORS,
                QTableWidgetItem(str(category.count)),
            )

            contribution_text = (
                f"{category.points} pts"
                if explanation.ioc_breakdown_verified
                else _CONTRIBUTION_NOT_ITEMIZED
            )

            self._evidence_table.setItem(
                row,
                _COLUMN_CONTRIBUTION,
                QTableWidgetItem(contribution_text),
            )

        self._evidence_table.resizeColumnsToContents()

    def _on_evidence_row_clicked(self, row: int, column: int) -> None:
        """
        Emit `evidence_category_selected` for the clicked row's IOC
        category.
        """

        del column

        item = self._evidence_table.item(row, _COLUMN_CATEGORY)

        if item is None:
            return

        ioc_type = item.data(Qt.ItemDataRole.UserRole)

        if not ioc_type:
            return

        self.evidence_category_selected.emit(ioc_type)
