"""
Reusable IOC summary widget for the SOC-IQ desktop application.

This widget displays all extracted Indicators of Compromise
for a completed investigation.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation


class IOCSummaryWidget(QWidget):
    """
    Displays extracted Indicators of Compromise.
    """

    ioc_selected = Signal(
        str,
        list,
    )

    def __init__(self) -> None:
        super().__init__()

        self._ioc_data: dict[str, list[str]] = {}

        self._table = QTableWidget()
        self._table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self._table.setColumnCount(2)

        self._table.setHorizontalHeaderLabels(
            [
                "IOC Type",
                "Count",
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

        self._table.cellClicked.connect(
            self._row_clicked,
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
            self._table,
            1,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display IOC information for an investigation.
        """

        self._ioc_data = investigation.iocs

        print("\n===== IOC DATA =====")
        print(investigation.iocs)
        print("====================\n")

        ioc_titles = {
            "ipv4": "IPv4 Addresses",
            "domains": "Domains",
            "urls": "URLs",
            "emails": "Emails",
            "md5": "MD5 Hashes",
            "sha1": "SHA1 Hashes",
            "sha256": "SHA256 Hashes",
            "cves": "CVEs",
            "windows_file_paths": "Windows File Paths",
            "windows_registry_keys": "Registry Keys",
        }

        self._table.setRowCount(
            len(ioc_titles),
        )

        for row, (key, title) in enumerate(
            ioc_titles.items()
        ):
            values = self._ioc_data.get(
                key,
                [],
            )

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    title,
                ),
            )

            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(len(values)),
                ),
            )

        self._table.resizeColumnsToContents()

        self._table.resizeRowsToContents()

        self._table.updateGeometry()

        self.updateGeometry()

    def _row_clicked(
        self,
        row: int,
        column: int,
    ) -> None:
        """
        Handle IOC table row selection.
        """

        del column

        ioc_titles = {
            "ipv4": "IPv4 Addresses",
            "domains": "Domains",
            "urls": "URLs",
            "emails": "Emails",
            "md5": "MD5 Hashes",
            "sha1": "SHA1 Hashes",
            "sha256": "SHA256 Hashes",
            "cves": "CVEs",
            "windows_file_paths": "Windows File Paths",
            "windows_registry_keys": "Registry Keys",
        }

        keys = list(
            ioc_titles.keys()
        )

        if row >= len(keys):
            return

        key = keys[row]

        values = self._ioc_data.get(
            key,
            [],
        )

        self.ioc_selected.emit(
            key,
            values,
        )

    def reset(self) -> None:
        """
        Reset the widget.
        """

        self._ioc_data.clear()

        self._table.setRowCount(
            0,
        )