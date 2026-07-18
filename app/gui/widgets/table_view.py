"""
Reusable table view for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QTableView,
)


class TableView(QTableView):
    """
    Standard table view used throughout the application.
    """

    def __init__(self) -> None:
        super().__init__()

        self._configure()

    def _configure(self) -> None:
        """
        Configure the default table behavior.
        """

        self.setAlternatingRowColors(True)

        self.setSortingEnabled(False)

        self.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.setShowGrid(False)

        self.verticalHeader().setVisible(False)

        self.horizontalHeader().setStretchLastSection(True)

        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )