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

        self._investigations = investigations or []

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

        if (
            not index.isValid()
            or role != Qt.ItemDataRole.DisplayRole
        ):
            return None

        investigation = self._investigations[index.row()]

        column = index.column()

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

        return None

    def set_investigations(
        self,
        investigations: list[Investigation],
    ) -> None:
        """
        Replace the model data.
        """

        self.beginResetModel()

        self._investigations = investigations

        self.endResetModel()

    def investigation_at(
        self,
        row: int,
    ) -> Investigation | None:
        """
        Return the investigation stored at the given row.

        Parameters
        ----------
        row:
            Row index.

        Returns
        -------
        Investigation | None
            The investigation if the row is valid,
            otherwise None.
        """

        if row < 0:
            return None

        if row >= len(self._investigations):
            return None

        return self._investigations[row]