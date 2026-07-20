"""
Qt table model for displaying investigation history.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    Qt,
)
from PySide6.QtGui import QColor

from app.database.models import Investigation


class InvestigationTableModel(QAbstractTableModel):
    """
    Model used by QTableView to display investigations.
    """

    HEADERS = (
        "ID",
        "Report",
        "Severity",
        "Risk",
        "Status",
        "Analyzed",
    )

    def __init__(
        self,
        investigations: list[Investigation] | None = None,
    ) -> None:
        super().__init__()

        self._all_investigations = (
            investigations or []
        )

        self._investigations = list(
            self._all_investigations
        )

    def rowCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:
        """
        Return the number of rows.
        """

        if parent.isValid():
            return 0

        return len(self._investigations)

    def columnCount(
        self,
        parent: QModelIndex = QModelIndex(),
    ) -> int:
        """
        Return the number of columns.
        """

        if parent.isValid():
            return 0

        return len(self.HEADERS)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """
        Return table headers.
        """

        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return self.HEADERS[section]

        return None

    def data(
        self,
        index: QModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> Any:
        """
        Return the data displayed in each cell.
        """

        if not index.isValid():
            return None

        investigation = self._investigations[index.row()]
        column = index.column()

        if role == Qt.ItemDataRole.DisplayRole:

            if column == 0:
                return investigation.investigation_id

            if column == 1:
                return investigation.report_name

            if column == 2:
                return investigation.severity

            if column == 3:
                return investigation.risk_score

            if column == 4:
                return investigation.status

            if column == 5:
                return (
                    investigation.analyzed_at
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M")
                )

        if (
            role == Qt.ItemDataRole.ForegroundRole
            and column == 2
        ):
            severity = investigation.severity.upper()

            if severity == "LOW":
                return QColor("#4CAF50")

            if severity == "MEDIUM":
                return QColor("#FFC107")

            if severity == "HIGH":
                return QColor("#FF9800")

            if severity == "CRITICAL":
                return QColor("#F44336")

        return None

    def set_investigations(
        self,
        investigations: list[Investigation],
    ) -> None:
        """
        Replace the model data.
        """

        self.beginResetModel()

        self._all_investigations = investigations

        self._investigations = list(
            investigations,
        )

        self.endResetModel()

    def filter(
        self,
        text: str,
    ) -> None:
        """
        Filter investigations by report name,
        severity, or status.
        """

        self.beginResetModel()

        text = text.lower().strip()

        if not text:

            self._investigations = list(
                self._all_investigations,
            )

        else:

            self._investigations = [
                investigation
                for investigation in self._all_investigations
                if (
                    text in investigation.report_name.lower()
                    or text in investigation.severity.lower()
                    or text in investigation.status.lower()
                )
            ]

        self.endResetModel()

    def sort(
        self,
        column: int,
        order: Qt.SortOrder = Qt.SortOrder.AscendingOrder,
    ) -> None:
        """
        Sort investigations by the selected column.
        """

        reverse = (
            order == Qt.SortOrder.DescendingOrder
        )

        self.beginResetModel()

        if column == 0:
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.investigation_id
                    or 0
                ),
                reverse=reverse,
            )

        elif column == 1:
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.report_name.lower()
                ),
                reverse=reverse,
            )

        elif column == 2:

            severity_order = {
                "LOW": 1,
                "MEDIUM": 2,
                "HIGH": 3,
                "CRITICAL": 4,
            }

            self._investigations.sort(
                key=lambda investigation: (
                    severity_order.get(
                        investigation.severity.upper(),
                        0,
                    )
                ),
                reverse=reverse,
            )

        elif column == 3:
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.risk_score
                ),
                reverse=reverse,
            )

        elif column == 4:
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.status.lower()
                ),
                reverse=reverse,
            )

        elif column == 5:
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.analyzed_at
                ),
                reverse=reverse,
            )

        self.endResetModel()

    def investigation_at(
        self,
        row: int,
    ) -> Investigation | None:
        """
        Return the investigation stored at the given row.
        """

        if row < 0:
            return None

        if row >= len(self._investigations):
            return None

        return self._investigations[row]
    