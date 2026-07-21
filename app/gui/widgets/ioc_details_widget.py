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
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
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

        self._sort_box = QComboBox()

        self._sort_box.addItems(
            [
                "A → Z",
                "Z → A",
            ]
        )

        self._export_button = QPushButton(
            "Export",
        )

        self._statistics_label = QLabel(
            "Showing 0 IOC values",
        )

        self._all_iocs: list[str] = []

        self._visible_iocs: list[str] = []

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

        controls_layout = QHBoxLayout()

        controls_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        controls_layout.setSpacing(
            8,
        )

        controls_layout.addWidget(
            self._search_box,
            1,
        )

        controls_layout.addWidget(
            self._sort_box,
        )

        controls_layout.addWidget(
            self._export_button,
        )

        layout.addWidget(
            self._selected_category_label,
        )

        layout.addLayout(
            controls_layout,
        )

        layout.addWidget(
            self._statistics_label,
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

        self._sort_box.currentIndexChanged.connect(
            lambda: self._filter_iocs(
                self._search_box.text(),
            ),
        )

        self._export_button.clicked.connect(
            self._export_visible_iocs,
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

        copy_filtered_action = QAction(
            "Copy Search Results",
            self,
        )

        copy_all_action = QAction(
            "Copy All IOCs",
            self,
        )

        copy_selected_action.triggered.connect(
            self._copy_selected_ioc,
        )

        copy_filtered_action.triggered.connect(
            self._copy_filtered_iocs,
        )

        copy_all_action.triggered.connect(
            self._copy_all_iocs,
        )

        menu.addAction(
            copy_selected_action,
        )

        menu.addAction(
            copy_filtered_action,
        )

        menu.addSeparator()

        menu.addAction(
            copy_all_action,
        )

        menu.exec(
            self._table.viewport().mapToGlobal(
                position,
            )
        )

    def _copy_filtered_iocs(
        self,
    ) -> None:
        """
        Copy the currently visible IOC values.
        """

        if not self._visible_iocs:
            return

        QGuiApplication.clipboard().setText(
            "\n".join(
                self._visible_iocs,
            )
        )

        self.copy_completed.emit(
            (
                f"{len(self._visible_iocs)} "
                f"search result(s) copied"
            ),
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

        self._update_statistics(
            len(values),
        )

    def _populate_table(
        self,
        values: list[str],
    ) -> None:
        """
        Populate the IOC table.
        """

        self._visible_iocs = list(
            values,
        )

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

    def _update_statistics(
        self,
        visible_count: int,
    ) -> None:
        """
        Update the IOC statistics label.
        """

        total_count = len(
            self._all_iocs,
        )

        if visible_count == 0:

            self._statistics_label.setText(
                "No IOC values found",
            )

        elif visible_count == total_count:

            self._statistics_label.setText(
                f"Showing {total_count} IOC value(s)",
            )

        else:

            self._statistics_label.setText(
                (
                    f"Showing {visible_count} "
                    f"of {total_count} IOC value(s)"
                ),
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

            filtered = list(
                self._all_iocs,
            )

        else:

            filtered = [
                value
                for value in self._all_iocs
                if search_text in value.lower()
            ]

        reverse = (
            self._sort_box.currentText()
            == "Z → A"
        )

        filtered.sort(
            reverse=reverse,
        )

        self._populate_table(
            filtered,
        )

        self._update_statistics(
            len(filtered),
        )

    def _export_visible_iocs(
        self,
    ) -> None:
        """
        Placeholder for IOC export.
        """

        self.copy_completed.emit(
            "IOC export feature coming next...",
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

        self._statistics_label.setText(
            "Showing 0 IOC values",
        )

        self._search_box.clear()

        self._all_iocs.clear()

        self._visible_iocs.clear()

        self._table.clearContents()

        self._table.setRowCount(
            0,
        )

        self._sort_box.setCurrentIndex(
            0,
        )