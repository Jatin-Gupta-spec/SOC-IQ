"""
Reusable IOC Details widget for the SOC-IQ desktop application.

Displays all IOC values for the IOC type selected
from the IOC Summary table.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class IOCDetailsWidget(QWidget):
    """
    Displays the individual IOC values for a
    selected IOC category.
    """

    def __init__(self) -> None:
        super().__init__()

        self._table = QTableWidget()

        self._table.setColumnCount(1)

        self._table.setHorizontalHeaderLabels(
            [
                "IOC Value",
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
            self._table,
        )

        self.setLayout(
            layout,
        )

    def display_iocs(
        self,
        values: list[str],
    ) -> None:
        """
        Display IOC values.
        """

        self._table.setRowCount(
            len(values),
        )

        for row, value in enumerate(values):

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(value),
            )

        self._table.resizeColumnsToContents()

    def reset(self) -> None:
        """
        Clear the widget.
        """

        self._table.setRowCount(
            0,
        )