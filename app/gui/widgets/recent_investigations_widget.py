"""
Recent investigations widget.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)

from PySide6.QtGui import (
    QAction,
    QColor,
)

from PySide6.QtWidgets import (
    QHeaderView,
    QMenu,
    QTableWidget,
    QTableWidgetItem,
)


class RecentInvestigationsWidget(QTableWidget):
    """
    Displays the latest investigations.
    """

    investigation_selected = Signal(object)

    export_requested = Signal(object)

    delete_requested = Signal(object)

    HEADERS = [
        "ID",
        "Report",
        "Severity",
        "Risk",
        "Status",
        "Analyzed",
    ]

    def __init__(self) -> None:
        super().__init__()

        self.setColumnCount(
            len(self.HEADERS),
        )

        self.setHorizontalHeaderLabels(
            self.HEADERS,
        )

        self.verticalHeader().hide()

        self.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )

        self.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )

        self.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection,
        )

        self.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch,
        )

        self.setAlternatingRowColors(
            True,
        )

        self.cellDoubleClicked.connect(
            self._row_activated,
        )

        self.setSortingEnabled(
            True,
        )

        self.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu,
        )

        self.customContextMenuRequested.connect(
            self._show_context_menu,
        )

    def load_investigations(
        self,
        investigations,
    ) -> None:

        self.setSortingEnabled(
            False,
        )

        self._investigations = investigations

        self.setRowCount(
            len(investigations),
        )

        for row, investigation in enumerate(
            investigations,
        ):

            investigation_id = (
                str(investigation.investigation_id)
                if investigation.investigation_id is not None
                else "-"
            )

            id_item = QTableWidgetItem(
                investigation_id,
            )

            id_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )

            self.setItem(
                row,
                0,
                id_item,
            )

            self.setItem(
                row,
                1,
                QTableWidgetItem(
                    investigation.report_name,
                ),
            )

            severity_item = QTableWidgetItem(
                investigation.severity,
            )

            severity_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )

            severity = (
                investigation.severity.upper()
            )

            if severity == "CRITICAL":

                severity_item.setText(
                    "🟥 CRITICAL",
                )

                severity_item.setBackground(
                    QColor("#C62828"),
                )

                severity_item.setForeground(
                    QColor("#FFFFFF"),
                )

            elif severity == "HIGH":

                severity_item.setText(
                    "🟧 HIGH",
                )

                severity_item.setBackground(
                    QColor("#EF6C00"),
                )

            elif severity == "MEDIUM":

                severity_item.setText(
                    "🟨 MEDIUM",
                )

                severity_item.setBackground(
                    QColor("#F9A825"),
                )

            else:

                severity_item.setText(
                    "🟩 LOW",
                )

                severity_item.setBackground(
                    QColor("#2E7D32"),
                )

            self.setItem(
                row,
                2,
                severity_item,
            )

            risk_item = QTableWidgetItem(
                str(
                    investigation.risk_score,
                ),
            )

            risk_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )

            self.setItem(
                row,
                3,
                risk_item,
            )

            status_item = QTableWidgetItem(
                investigation.status,
            )

            status_item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter,
            )

            self.setItem(
                row,
                4,
                status_item,
            )

            self.setItem(
                row,
                5,
                QTableWidgetItem(
                    investigation.analyzed_at.strftime(
                        "%Y-%m-%d %H:%M",
                    ),
                ),
            )

            tooltip = (
                f"Investigation #{investigation_id}\n\n"
                f"Report: {investigation.report_name}\n"
                f"Severity: {investigation.severity}\n"
                f"Risk Score: {investigation.risk_score}\n"
                f"Status: {investigation.status}\n"
                f"Analyzed: "
                f"{investigation.analyzed_at.strftime('%d %b %Y %H:%M')}"
            )

            for column in range(
                self.columnCount(),
            ):
                item = self.item(
                    row,
                    column,
                )

                if item is not None:
                    item.setToolTip(
                        tooltip,
                    )

        self.setSortingEnabled(
            True,
        )

    def _row_activated(
        self,
        row: int,
        column: int,
    ) -> None:
        """
        Emit the selected investigation.
        """

        if row >= len(self._investigations):
            return

        self.investigation_selected.emit(
            self._investigations[row],
        )

    def _show_context_menu(
        self,
        position,
    ) -> None:
        """
        Display the investigation context menu.
        """

        row = self.currentRow()

        if row < 0:
            return

        menu = QMenu(self)

        open_action = QAction(
            "Open Investigation",
            self,
        )

        open_action.triggered.connect(
            lambda: self.investigation_selected.emit(
                self._investigations[row],
            ),
        )

        export_action = QAction(
            "Export Investigation",
            self,
        )

        export_action.triggered.connect(
            lambda: self.export_requested.emit(
                self._investigations[row],
            ),
        )

        copy_action = QAction(
            "Copy Report Name",
            self,
        )

        delete_action = QAction(
            "Delete Investigation",
            self,
        )

        delete_action.triggered.connect(
            lambda: self.delete_requested.emit(
                self._investigations[row],
            ),
        )

        menu.addAction(
            open_action,
        )

        menu.addSeparator()

        menu.addAction(
            export_action,
        )

        menu.addAction(
            copy_action,
        )

        menu.addSeparator()

        menu.addAction(
            delete_action,
        )

        menu.exec(
            self.viewport().mapToGlobal(
                position,
            ),
        )