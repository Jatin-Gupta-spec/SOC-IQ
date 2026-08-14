"""
Investigation Queue Widget

Displays the most recent investigations
inside the SOC-IQ dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QSizePolicy,
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
from app.gui.design.tokens import Spacing


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

    # BATCH 04: emitted when a row is *activated* (double-click, or
    # Enter/Return with a row selected) -- not on plain single-click
    # selection, so existing single-click row highlighting behavior
    # is unchanged. Carries the actual Investigation the activated
    # row represents.
    investigation_activated = Signal(object)

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

        # BATCH 04: mirrors exactly what load_investigations() hands
        # to self._model.set_investigations(), in the same order, so
        # an activated row's *source* row index can be mapped back to
        # the Investigation object it represents without depending on
        # any undocumented data-role contract on InvestigationTableModel
        # (which is out of scope for this batch).
        self._investigations: list[Investigation] = []

        super().__init__()

        # BATCH 03B: Investigation Queue is the dominant workbench
        # per the target hierarchy, so it should never be capped
        # below its container's available height -- explicit
        # Expanding/Expanding rather than relying on ModernCard's
        # default, so this doesn't silently regress if that default
        # ever changes.
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

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
        # XS rather than SM: the Queue is the primary workbench and
        # gets the most of the row's vertical budget in
        # dashboard_page.py -- every bit not spent on chrome here is
        # a bit more room the table itself gets before its own
        # internal scrolling kicks in.
        layout.setSpacing(Spacing.XS)

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

        # BATCH 03B: the table itself must expand to fill whatever
        # height the Queue's row/stack layout gives it, rather than
        # sizing to its own sizeHint -- this is what lets
        # resizeRowsToContents() (called on every load) actually use
        # the full allocated height instead of the table settling at
        # a smaller natural size and letting its own internal
        # scrollbar hide rows below the fold.
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._table.setFont(
            fonts.body()
        )

        # BATCH 04: pointing-hand cursor + tooltip are the row-level
        # interaction feedback called for in the batch objective --
        # reusing existing hover styling below (QTableView::item:hover
        # was already present pre-Batch-04) rather than adding new
        # animation or restyling the table.
        self._table.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self._table.setToolTip(
            "Double-click a row to open it in the Investigation Workspace"
        )

        self._table.setStyleSheet(
            f"""
            QTableView {{
                background-color: {palette.surface_primary};
                alternate-background-color: {palette.surface_secondary};
                gridline-color: transparent;
                border: none;
                color: {palette.text_primary};
                selection-background-color: {palette.surface_elevated};
                selection-color: {palette.text_primary};
            }}

            QTableView::item {{
                padding: {Spacing.TABLE_CELL_PADDING}px;
                border: none;
                border-bottom: 1px solid {palette.border_subtle};
            }}

            QTableView::item:hover {{
                background-color: {palette.surface_secondary};
            }}

            QTableView::item:selected {{
                background-color: {palette.surface_elevated};
                color: {palette.text_primary};
            }}

            QHeaderView::section {{
                background-color: {palette.surface_primary};
                color: {palette.text_muted};
                border: none;
                border-bottom: 1px solid {palette.border_default};
                padding: {Spacing.TABLE_CELL_PADDING}px;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            """
        )

        # BATCH 04: `activated` fires on double-click and on
        # Enter/Return with a row selected -- covers mouse and
        # keyboard "open this row" without touching single-click
        # selection behavior at all.
        self._table.activated.connect(
            self._on_row_activated
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
    # Interaction
    # --------------------------------------------------

    def _on_row_activated(self, proxy_index) -> None:
        """
        Resolve an activated proxy-model row to the Investigation it
        represents and emit investigation_activated.

        Deliberately does not read the value back off the model via
        a data role: InvestigationTableModel's data-role contract
        isn't defined in the files in scope for this batch, so this
        instead maps the activated row back through the proxy to a
        *source* row index and indexes into self._investigations,
        which was populated in the same order and from the same list
        given to self._model.set_investigations() in
        load_investigations(). If the table is ever resorted/filtered,
        mapToSource() still returns the correct pre-sort/pre-filter
        row, so this stays correct under both.
        """

        if not proxy_index.isValid():
            return

        source_index = self._proxy.mapToSource(proxy_index)

        row = source_index.row()

        if not (0 <= row < len(self._investigations)):
            # Selected row no longer corresponds to loaded data
            # (e.g. a refresh raced with the activation) -- do
            # nothing rather than emit a stale/wrong investigation.
            return

        investigation = self._investigations[row]

        self.investigation_activated.emit(investigation)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def clear(self) -> None:
        """
        Clear queue.
        """

        self._investigations = []

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

        # BATCH 04: kept in lockstep with what's handed to the model
        # so row-activation can resolve back to an Investigation --
        # see _on_row_activated().
        self._investigations = investigations

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