"""
Reusable IOC Details widget for the SOC-IQ desktop application.

Displays all IOC values for the IOC type selected
from the IOC Summary table.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
    QEvent,
)

from PySide6.QtGui import (
    QAction,
    QBrush,
    QColor,
    QGuiApplication,
    QKeySequence,
    QShortcut,
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

from app.gui.design.tokens.colors import Colors


class IOCDetailsWidget(QWidget):
    """
    Displays the individual IOC values for a
    selected IOC category.
    """

    copy_completed = Signal(
        str,
    )

    threat_intel_requested = Signal(
        str,
    )

    # Emitted when the analyst asks to see the full IOC detail
    # experience (value, investigation context, threat-intelligence
    # status, risk significance) for a single selected indicator.
    # Carries the raw IOC category key (e.g. "sha256", not "SHA256
    # Hashes") and the selected value.
    ioc_detail_requested = Signal(
        str,
        str,
    )

    # Column indices for the details table. Column 1 (Threat Intel)
    # is only shown for categories where threat-intelligence
    # enrichment applies (currently SHA256 hashes) -- see
    # `display_iocs()`.
    _COLUMN_VALUE = 0
    _COLUMN_THREAT_INTEL = 1

    def __init__(self) -> None:
        super().__init__()

        # Maps an IOC value (e.g. a SHA256 hash) to its enriched
        # threat-intelligence record for the category currently on
        # display. Populated by `display_iocs()` and consulted by
        # `_populate_table()`/`_open_threat_intel()`. `None` means the
        # current category has no threat-intelligence dimension at
        # all (the Threat Intel column stays hidden), which is
        # distinct from an empty dict (the category supports
        # enrichment but no record exists yet for a given value).
        self._threat_intel_lookup: dict[str, dict] | None = None

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

        self._view_details_button = QPushButton(
            "View Details",
        )

        self._view_details_button.setEnabled(
            False,
        )

        # Raw category key (e.g. "sha256") for the values currently
        # on display, distinct from `_current_category` which holds
        # the human-readable title. Needed so `ioc_detail_requested`
        # can carry the same category key the rest of the codebase
        # (ThreatIntelService, RiskScoringEngine.IOC_WEIGHTS) uses.
        self._current_category_key = ""

        self._statistics_label = QLabel(
            "Showing 0 IOC values",
        )

        self._empty_label = QLabel(
            "No IOC values available.\nSelect an IOC category to begin.",
        )

        self._empty_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter,
        )

        self._empty_label.hide()

        self._all_iocs: list[str] = []

        self._current_category = "Unknown"

        self._visible_iocs: list[str] = []

        self._table = QTableWidget()

        self._table.setColumnCount(
            2,
        )

        self._table.setHorizontalHeaderLabels(
            [
                "Indicator of Compromise",
                "Threat Intel",
            ]
        )

        # Hidden until `display_iocs()` is given a threat-intelligence
        # lookup for the category on display -- most IOC categories
        # (IPs, domains, CVEs, ...) have no threat-intelligence
        # dimension in this workspace, so showing an always-empty
        # column for them would just be dead space.
        self._table.setColumnHidden(
            self._COLUMN_THREAT_INTEL,
            True,
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

        self._table.setAlternatingRowColors(
            True,
        )

        self._table.setSortingEnabled(
            False,
        )

        self._table.setShowGrid(
            False,
        )

        self._table.setWordWrap(
            False,
        )

        self._table.setCornerButtonEnabled(
            False,
        )

        header = self._table.horizontalHeader()

        header.setStretchLastSection(
            True,
        )

        header.setSectionResizeMode(
            self._COLUMN_VALUE,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            self._COLUMN_THREAT_INTEL,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setMinimumSectionSize(
            150,
        )

        self._table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )

        self._build_ui()

        self._connect_signals()

        self._table.hide()

        self._empty_label.show()

        self._table.installEventFilter(
            self,
        )

        self._copy_shortcut = QShortcut(
            QKeySequence.StandardKey.Copy,
            self._table,
        )

        self._copy_shortcut.activated.connect(
            self._copy_selected_ioc,
        )

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

        controls_layout.addWidget(
            self._view_details_button,
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
            self._empty_label,
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

        self._view_details_button.clicked.connect(
            self._request_selected_ioc_detail,
        )

        self._table.itemDoubleClicked.connect(
            self._double_click_copy,
        )

        self._table.itemSelectionChanged.connect(
            self._on_selection_changed,
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

        # Selecting the row before the actions are built (above)
        # means `view_details_action`/`copy_selected_action` act on
        # the row that was right-clicked, matching the existing
        # copy behavior.

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

        view_details_action = QAction(
            "View IOC Details",
            self,
        )

        view_details_action.triggered.connect(
            self._request_selected_ioc_detail,
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
            view_details_action,
        )

        menu.addSeparator()

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

    def _double_click_copy(
        self,
        item: QTableWidgetItem,
    ) -> None:
        """
        Handle a double-click on an IOC row.

        Double-clicking the Threat Intel column jumps to that
        indicator's enrichment record instead of copying, since
        there's nothing useful to copy from a verdict label and the
        analyst's intent there is clearly "show me why". Double-
        clicking anywhere else in the row copies the IOC value, as
        before.
        """

        if item.column() == self._COLUMN_THREAT_INTEL:

            self._open_threat_intel(
                item.row(),
            )

            return

        QGuiApplication.clipboard().setText(
            item.text(),
        )

        self.copy_completed.emit(
            "IOC copied to clipboard",
        )

    def _open_threat_intel(
        self,
        row: int,
    ) -> None:
        """
        Request that the enriched threat-intelligence record for
        the IOC value on `row` be shown, if one exists.
        """

        value_item = self._table.item(
            row,
            self._COLUMN_VALUE,
        )

        if value_item is None:
            return

        value = value_item.text()

        if (
            self._threat_intel_lookup is None
            or value not in self._threat_intel_lookup
        ):
            return

        self.threat_intel_requested.emit(
            value,
        )

    def keyPressEvent(
        self,
        event,
    ) -> None:
        """
        Handle keyboard shortcuts.
        """

        if (
            event.matches(
                QKeySequence.StandardKey.Copy,
            )
            and self._table.hasFocus()
        ):

            self._copy_selected_ioc()

            return

        super().keyPressEvent(
            event,
        )

    def _on_selection_changed(
        self,
    ) -> None:
        """
        Enable/disable "View Details" based on whether a row is
        currently selected.
        """

        self._view_details_button.setEnabled(
            bool(self._table.selectedItems()),
        )

    def _selected_value(
        self,
    ) -> str | None:
        """
        Return the IOC value of the currently selected row, or
        `None` if nothing is selected.
        """

        selected_items = self._table.selectedItems()

        if not selected_items:
            return None

        row = selected_items[0].row()

        value_item = self._table.item(
            row,
            self._COLUMN_VALUE,
        )

        if value_item is None:
            return None

        return value_item.text()

    def _request_selected_ioc_detail(
        self,
    ) -> None:
        """
        Emit `ioc_detail_requested` for the currently selected IOC
        value, if any.
        """

        value = self._selected_value()

        if value is None:
            return

        self.ioc_detail_requested.emit(
            self._current_category_key,
            value,
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
        threat_intel_lookup: dict[str, dict] | None = None,
    ) -> None:
        """
        Display IOC values.

        Args:
            ioc_type:
                The IOC category key (e.g. "sha256", "ipv4").
            values:
                The IOC values belonging to that category.
            threat_intel_lookup:
                Optional mapping of IOC value to its enriched
                threat-intelligence record, for categories that
                have threat-intelligence enrichment (currently
                SHA256 hashes). When provided, the Threat Intel
                column is shown and populated per row; a value with
                no entry in the mapping is shown as "Not Enriched".
                When omitted (the default), the Threat Intel column
                stays hidden -- most IOC categories don't have a
                threat-intelligence dimension in this workspace.
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

        self._current_category = title

        self._current_category_key = ioc_type

        self._threat_intel_lookup = threat_intel_lookup

        self._table.setColumnHidden(
            self._COLUMN_THREAT_INTEL,
            threat_intel_lookup is None,
        )

        self._selected_category_label.setText(
            (
                f"Selected Category: {title} "
                f"({len(values)} IOC"
                f"{'' if len(values) == 1 else 's'})"
            )
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

    # Verdict -> display color, mirrored from the verdict strings
    # produced by `ThreatIntelService` (see
    # `app/threat_intel/service.py`). Kept local to the widget
    # rather than imported from the service, since this is purely a
    # GUI presentation concern and the service has no reason to
    # depend on Qt.
    _VERDICT_COLORS = {
        "Malicious": QColor(Colors.Severity.CRITICAL),
        "Suspicious": QColor(Colors.Status.WARNING),
        "Clean": QColor(Colors.Status.SUCCESS),
    }

    def _build_threat_intel_item(
        self,
        value: str,
    ) -> QTableWidgetItem:
        """
        Build the Threat Intel column cell for a single IOC value.
        """

        record = (
            self._threat_intel_lookup.get(
                value,
            )
            if self._threat_intel_lookup is not None
            else None
        )

        if record is None:

            item = QTableWidgetItem(
                "Not Enriched",
            )

            item.setToolTip(
                "No threat-intelligence record for this indicator.",
            )

            return item

        verdict = record.get(
            "verdict",
            "Unknown",
        )

        item = QTableWidgetItem(
            verdict,
        )

        item.setForeground(
            QBrush(
                self._VERDICT_COLORS.get(
                    verdict,
                    QColor(Colors.Text.DISABLED),
                ),
            ),
        )

        item.setToolTip(
            "Double-click to view the full threat-intelligence record.",
        )

        return item

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

        if values:

            self._empty_label.hide()

            self._table.show()

        else:

            self._table.hide()

            self._empty_label.show()

        self._table.clearContents()

        self._table.setRowCount(
            len(values),
        )

        for row, value in enumerate(
            values,
        ):

            item = QTableWidgetItem(
                value,
            )

            item.setToolTip(
                value,
            )

            self._table.setItem(
                row,
                self._COLUMN_VALUE,
                item,
            )

            if self._threat_intel_lookup is not None:

                self._table.setItem(
                    row,
                    self._COLUMN_THREAT_INTEL,
                    self._build_threat_intel_item(
                        value,
                    ),
                )

        self._table.resizeColumnsToContents()

        if values:

            self._table.selectRow(
                0,
            )

            self._table.scrollToItem(
                self._table.item(
                    0,
                    0,
                ),
            )

            self._table.setFocus()

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
        Export the currently visible IOC values.
        """

        if not self._visible_iocs:

            self.copy_completed.emit(
                "No IOC values to export.",
            )

            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export IOC Values",
            f"{self._current_category.lower().replace(' ', '_')}.txt",
            (
                "Text Files (*.txt);;"
                "CSV Files (*.csv);;"
                "JSON Files (*.json)"
            ),
        )

        if not file_path:
            return

        try:

            if file_path.lower().endswith(
                ".txt",
            ):

                self._export_txt(
                    file_path,
                )

            elif file_path.lower().endswith(
                ".csv",
            ):

                self._export_csv(
                    file_path,
                )

            elif file_path.lower().endswith(
                ".json",
            ):

                self._export_json(
                    file_path,
                )

            else:

                self._export_txt(
                    file_path,
                )

        except OSError as error:

            self.copy_completed.emit(
                f"Export failed:\n{error}"
            )

            return

        self.copy_completed.emit(
            (
                f"Exported "
                f"{len(self._visible_iocs)} IOC value(s)"
                f"to\n{file_path}"
            ),
        )

    def _export_txt(
        self,
        file_path: str,
    ) -> None:
        """
        Export IOC values as a formatted text report.
        """

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as export_file:

            export_file.write(
                "=" * 40 + "\n"
            )

            export_file.write(
                "SOC-IQ IOC Export\n"
            )

            export_file.write(
                "=" * 40 + "\n\n"
            )

            export_file.write(
                f"Category : {self._current_category}\n"
            )

            export_file.write(
                f"Total IOCs : {len(self._visible_iocs)}\n\n"
            )

            export_file.write(
                "-" * 40 + "\n\n"
            )

            export_file.write(
                "\n".join(
                    self._visible_iocs,
                )
            )

            export_file.write(
                "\n\n"
            )

            export_file.write(
                "=" * 40 + "\n"
            )

            export_file.write(
                "Generated by SOC-IQ\n"
            )

            export_file.write(
                "=" * 40
            )


    def _export_csv(
        self,
        file_path: str,
    ) -> None:
        """
        Export IOC values as CSV.
        """

        import csv

        with open(
            file_path,
            "w",
            newline="",
            encoding="utf-8",
        ) as export_file:

            writer = csv.writer(
                export_file,
            )

            writer.writerow(
                [
                    "Category",
                    "IOC Value",
                ]
            )

            for value in self._visible_iocs:

                writer.writerow(
                    [
                        self._current_category,
                        value,
                    ]
                )


    def _export_json(
        self,
        file_path: str,
    ) -> None:
        """
        Export IOC values as JSON.
        """

        import json

        data = {
            "category": self._current_category,
            "ioc_count": len(
                self._visible_iocs,
            ),
            "values": self._visible_iocs,
        }

        with open(
            file_path,
            "w",
            encoding="utf-8",
        ) as export_file:

            json.dump(
                data,
                export_file,
                indent=4,
            )

    def eventFilter(
        self,
        source,
        event,
    ):
        """
        Handle keyboard shortcuts for the IOC table.
        """

        if (
            source is self._table
            and event.type() == QEvent.Type.KeyPress
            and event.key() in (
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
            )
        ):

            self._copy_selected_ioc()

            return True

        return super().eventFilter(
            source,
            event,
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

        self._threat_intel_lookup = None

        self._current_category_key = ""

        self._view_details_button.setEnabled(
            False,
        )

        self._table.setColumnHidden(
            self._COLUMN_THREAT_INTEL,
            True,
        )

        self._search_box.clear()

        self._all_iocs.clear()

        self._visible_iocs.clear()

        self._table.clearContents()

        self._table.setRowCount(
            0,
        )

        self._table.hide()

        self._empty_label.show()

        self._sort_box.setCurrentIndex(
            0,
        )