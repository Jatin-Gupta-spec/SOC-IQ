"""
Investigation Queue Widget

Displays the most recent investigations
inside the SOC-IQ dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QStackedLayout,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.components.cards.modern_card import ModernCard
from app.gui.models.investigation_proxy_model import (
    InvestigationProxyModel,
)
from app.gui.models.investigation_table_model import (
    InvestigationTableModel,
)


class InvestigationQueueWidget(ModernCard):
    """
    Displays the latest investigations.
    """

    # Column the table is sorted by on load, named rather than left
    # as a bare index so a future reordering of
    # InvestigationTableModel's columns can't silently change what
    # gets sorted. NOTE: this should ideally reference a column
    # enum/constant exposed by InvestigationTableModel itself once
    # one exists — 5 is presumed to be "Analyzed At" based on
    # current default sort behavior; confirm against the model.
    _DEFAULT_SORT_COLUMN = 5

    def __init__(self) -> None:

        # self._model / self._proxy must be set before
        # super().__init__() runs: ModernCard.__init__() calls
        # _build_contents() (below) as part of its own
        # construction, and _build_contents() depends on both
        # being present. Do not reorder this without also checking
        # ModernCard's init sequence.
        self._model = InvestigationTableModel()

        self._proxy = InvestigationProxyModel()

        self._proxy.setSourceModel(
            self._model
        )

        super().__init__()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_contents(self) -> None:
        """
        Build widget interface.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        layout = QVBoxLayout()

        header_row = QHBoxLayout()

        title = QLabel(
            "Investigation Queue"
        )

        title.setFont(
            fonts.title()
        )

        title.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 600;"
        )

        self._count_label = QLabel("0 records")

        self._count_label.setFont(fonts.caption())

        self._count_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._count_label)

        self._table = QTableView()

        self._table.setModel(
            self._proxy
        )

        self._table.setSortingEnabled(
            True
        )

        self._table.sortByColumn(
            self._DEFAULT_SORT_COLUMN,
            Qt.SortOrder.DescendingOrder,
        )

        self._table.verticalHeader().hide()

        self._table.setAlternatingRowColors(
            True
        )

        self._table.setShowGrid(
            False
        )

        self._table.setSelectionBehavior(
            QTableView.SelectionBehavior.SelectRows
        )

        self._table.setSelectionMode(
            QTableView.SelectionMode.SingleSelection
        )

        self._table.setEditTriggers(
            QTableView.EditTrigger.NoEditTriggers
        )

        self._table.horizontalHeader().setStretchLastSection(
            True
        )

        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self._table.horizontalHeader().setHighlightSections(
            False
        )

        # Empty state — shown instead of a zero-row table, matching
        # the treatment used elsewhere on the dashboard rather than
        # a blank table with only a header row.
        self._empty_state = self._build_empty_state(palette, fonts)

        self._stack = QStackedLayout()
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty_state)

        layout.addLayout(header_row)
        layout.addLayout(self._stack)

        self.add_layout(
            layout
        )

        self._set_populated(False)

    def _build_empty_state(self, palette, fonts) -> QWidget:
        container = QWidget()

        empty_layout = QVBoxLayout(container)
        empty_layout.addStretch()

        title_label = QLabel("No investigations yet")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(fonts.body())
        title_label.setStyleSheet(
            f"color: {palette.text_secondary}; font-weight: 600;"
        )

        description_label = QLabel(
            "Completed investigations will appear here once a "
            "report has been analyzed."
        )
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setFont(fonts.caption())
        description_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        empty_layout.addWidget(title_label)
        empty_layout.addWidget(description_label)
        empty_layout.addStretch()

        return container

    def _set_populated(self, populated: bool) -> None:
        self._stack.setCurrentWidget(
            self._table if populated else self._empty_state
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def clear(self) -> None:
        """
        Clear queue.
        """

        self._model.set_investigations(
            []
        )

        self._count_label.setText("0 records")

        self._set_populated(False)

    def load_investigations(
        self,
        investigations: list[Investigation],
    ) -> None:
        """
        Populate investigation queue.
        """

        self._model.set_investigations(
            investigations
        )

        self._table.resizeRowsToContents()

        count = len(investigations)

        self._count_label.setText(
            f"{count} record" if count == 1 else f"{count} records"
        )

        self._set_populated(count > 0)

    def filter(
        self,
        text: str,
    ) -> None:
        """
        Filter investigations.
        """

        self._proxy.setFilterFixedString(
            text
        )

        # Filtering changes how many rows are visible without going
        # through load_investigations(), so the count label and
        # empty-state switch have to be refreshed here too —
        # otherwise a filter that matches zero rows leaves the table
        # showing a bare header instead of the empty state, and the
        # count label keeps showing the pre-filter total.
        visible_count = self._proxy.rowCount()

        self._count_label.setText(
            f"{visible_count} record" if visible_count == 1 else f"{visible_count} records"
        )

        self._set_populated(visible_count > 0)