"""
Reusable IOC Details widget for the SOC-IQ desktop application.

Displays all IOC values for the IOC type selected
from the IOC Summary table.
"""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QHeaderView,
    QPushButton,
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

        self._copy_button = QPushButton(
            "Copy Selected IOC",
        )

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

        self._connect_signals()

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
            self._copy_button,
        )

        layout.addWidget(
            self._table,
        )

        self.setLayout(
            layout,
        )

    def _connect_signals(
        self,
    ) -> None:
        """
        Connect widget signals.
        """

        self._copy_button.clicked.connect(
            self._copy_selected_ioc,
        )

    def _copy_selected_ioc(
        self,
    ) -> None:
        """
        Copy the selected IOC value to the clipboard.
        """

        selected_items = self._table.selectedItems()

        if not selected_items:
            return

        clipboard = QGuiApplication.clipboard()

        clipboard.setText(
            selected_items[0].text(),
        )

    def display_iocs(
        self,
        ioc_type: str,
        values: list[str],
    ) -> None:
        """
        Display IOC values.
        """

        del ioc_type

        self._table.clearContents()

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

        if values:
            self._table.selectRow(0)

    def reset(
        self,
    ) -> None:
        """
        Clear the widget.
        """

        self._table.clearContents()

        self._table.setRowCount(
            0,
        )