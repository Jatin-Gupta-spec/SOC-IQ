"""
Investigation Queue Widget

Displays the most recent investigations
inside the SOC-IQ dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QHeaderView,
    QTableView,
    QVBoxLayout,
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

    def __init__(self) -> None:
        super().__init__()

        self._model = InvestigationTableModel()

        self._proxy = InvestigationProxyModel()

        self._proxy.setSourceModel(
            self._model
        )

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """
        Build widget interface.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        layout = QVBoxLayout()

        title = QLabel(
            "Investigation Queue"
        )

        title.setFont(
            fonts.title()
        )

        title.setStyleSheet(
            f"""
            color: {palette.text_primary};
            font-weight: 600;
            """
        )

        self._table = QTableView()

        self._table.setModel(
            self._proxy
        )

        self._table.setSortingEnabled(
            True
        )

        self._table.sortByColumn(
            5,
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

        self._table.setSortingEnabled(
            True
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

        layout.addWidget(title)

        layout.addWidget(
            self._table
        )

        self.add_layout(
            layout
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