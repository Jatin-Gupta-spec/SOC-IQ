"""
Reusable IOC Details widget for the SOC-IQ desktop application.

Displays all IOC values for the IOC type selected
from the IOC Summary table.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QGuiApplication,
)
from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
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

    copy_completed = Signal(
        str,
    )

    def __init__(self) -> None:
        super().__init__()

        self._selected_category_label = QLabel(
            "Selected Category: None",
        )

        self._search_box = QLineEdit()

        self._search_box.setPlaceholderText(
            "Search IOC...",
        )

        self._all_iocs: list[str] = []

        self._table = QTableWidget()

        self._table.setColumnCount(
            1,
        )

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

        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )

        self._build_ui()

        self._connect_signals()

    def _build_ui(
        self,
    ) -> None:
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
            self._selected_category_label,
        )

        layout.addWidget(
            self._search_box,
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

        self._table.customContextMenuRequested.connect(
            self._show_context_menu,
        )

        self._search_box.textChanged.connect(
            self._filter_iocs,
        )

    def _show_context_menu(
        self,
        position,
    ) -> None:
        """
        Show the IOC context menu.
        """

        item = self._table.itemAt(
            position,
        )

        if item is None:
            return

        self._table.selectRow(
            item.row(),
        )

        menu = QMenu(
            self,
        )

        copy_selected_action = QAction(
            "Copy Selected IOC",
            self,
        )

        copy_all_action = QAction(
            "Copy All IOCs",
            self,
        )

        copy_selected_action.triggered.connect(
            self._copy_selected_ioc,
        )

        copy_all_action.triggered.connect(
            self._copy_all_iocs,
        )

        menu.addAction(
            copy_selected_action,
        )

        menu.addAction(
            copy_all_action,
        )

        menu.exec(
            self._table.viewport().mapToGlobal(
                position,
            )
        )

    def _copy_selected_ioc(
        self,
    ) -> None:
        """
        Copy the selected IOC value.
        """

        selected_items = self._table.selectedItems()

        if not selected_items:
            return

        QGuiApplication.clipboard().setText(
            selected_items[0].text(),
        )

        self.copy_completed.emit(
            "IOC copied to clipboard",
        )

    def _copy_all_iocs(
        self,
    ) -> None:
        """
        Copy every IOC value.
        """

        values: list[str] = []

        for row in range(
            self._table.rowCount(),
        ):

            item = self._table.item(
                row,
                0,
            )

            if item is not None:

                values.append(
                    item.text(),
                )

        if not values:
            return

        QGuiApplication.clipboard().setText(
            "\n".join(
                values,
            )
        )

        self.copy_completed.emit(
            f"{len(values)} IOC value(s) copied to clipboard",
        )

    def display_iocs(
        self,
        ioc_type: str,
        values: list[str],
    ) -> None:
        """
        Display IOC values.
        """

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

        title = ioc_titles.get(
            ioc_type,
            ioc_type,
        )

        self._selected_category_label.setText(
            f"Selected Category: {title}"
        )

        self._all_iocs = list(
            values,
        )

        self._populate_table(
            self._all_iocs,
        )

        for row, value in enumerate(
            values,
        ):

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    value,
                ),
            )

        self._table.resizeColumnsToContents()

        if values:

            self._table.selectRow(
                0,
            )

    def _populate_table(
        self,
        values: list[str],
    ) -> None:
        """
        Populate the IOC table.
        """

        self._table.clearContents()

        self._table.setRowCount(
            len(values),
        )

        for row, value in enumerate(
            values,
        ):

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    value,
                ),
            )

        self._table.resizeColumnsToContents()

        if values:

            self._table.selectRow(
                0,
            )

    def _filter_iocs(
        self,
        text: str,
    ) -> None:
        """
        Filter IOC values using the search box.
        """

        search_text = text.lower().strip()

        if not search_text:

            self._populate_table(
                self._all_iocs,
            )

            return

        filtered = [
            value
            for value in self._all_iocs
            if search_text in value.lower()
        ]

        self._populate_table(
            filtered,
        )
  
    def reset(
        self,
    ) -> None:
        """
        Clear the widget.
        """

        self._selected_category_label.setText(
            "Selected Category: None",
        )

        self._search_box.clear()

        self._all_iocs.clear()

        self._table.clearContents()

        self._table.setRowCount(
            0,
        )