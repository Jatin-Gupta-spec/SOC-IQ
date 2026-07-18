"""
IOC Details dialog for the SOC-IQ desktop application.

Displays every IOC value belonging to a selected
IOC category.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QListWidget,
    QVBoxLayout,
)


class IOCDetailsDialog(QDialog):
    """
    Displays all values for a selected IOC type.
    """

    def __init__(
        self,
        title: str,
        values: list[str],
    ) -> None:
        super().__init__()

        self.setWindowTitle(title)

        self.resize(
            700,
            500,
        )

        self._list = QListWidget()

        self._list.addItems(
            values,
        )

        layout = QVBoxLayout()

        layout.addWidget(
            self._list,
        )

        self.setLayout(
            layout,
        )