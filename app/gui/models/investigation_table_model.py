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

        # Copied defensively: without this, `_all_investigations`
        # held a direct reference to the caller's list. If the
        # caller mutated that same list object in place later
        # (e.g. append) instead of calling `set_investigations()`,
        # this model's notion of the full dataset would silently
        # drift out of sync with what was last reported to the
        # view via begin/endResetModel.
        self._all_investigations = (
            list(investigations) if investigations else []
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
                # `analyzed_at` is not guaranteed to be populated
                # (e.g. an investigation record created before
                # analysis actually completed). Without this guard,
                # a `None` value here raised an uncaught
                # AttributeError from inside a Qt-invoked virtual
                # method (`data()`), which PySide6 cannot recover
                # from cleanly.
                if investigation.analyzed_at is None:
                    return "—"

                return (
                    investigation.analyzed_at
                    .astimezone()
                    .strftime("%Y-%m-%d %H:%M")
                )

        if (
            role == Qt.ItemDataRole.ForegroundRole
            and column == 2
        ):
            severity = (
                investigation.severity.upper()
                if investigation.severity
                else ""
            )

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

            # `report_name`/`severity`/`status` are not guaranteed
            # to be populated on every record (a malformed or
            # partially-written investigation). `.lower()` on
            # `None` would raise and abort filtering entirely,
            # rather than simply excluding that row from the
            # match.
            self._investigations = [
                investigation
                for investigation in self._all_investigations
                if (
                    text
                    in (investigation.report_name or "").lower()
                    or text
                    in (investigation.severity or "").lower()
                    or text
                    in (investigation.status or "").lower()
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
            # `report_name` is not guaranteed to be populated; an
            # unguarded `.lower()` on `None` would raise and abort
            # the sort entirely instead of just placing that row
            # somewhere reasonable.
            self._investigations.sort(
                key=lambda investigation: (
                    (investigation.report_name or "").lower()
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
                        (
                            investigation.severity.upper()
                            if investigation.severity
                            else ""
                        ),
                        0,
                    )
                ),
                reverse=reverse,
            )

        elif column == 3:
            # `risk_score` is not guaranteed to be populated either;
            # sorting `None` against an `int`/`float` raises a
            # `TypeError` in Python 3. Missing scores sort as the
            # lowest value rather than crashing the sort.
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.risk_score
                    if investigation.risk_score is not None
                    else float("-inf")
                ),
                reverse=reverse,
            )

        elif column == 4:
            self._investigations.sort(
                key=lambda investigation: (
                    (investigation.status or "").lower()
                ),
                reverse=reverse,
            )

        elif column == 5:
            # `analyzed_at` may be `None` (see `data()` above).
            # Grouping on "is missing" first avoids ever comparing
            # a `None` against a real `datetime`, which raises a
            # `TypeError` in Python 3 and would abort the sort.
            self._investigations.sort(
                key=lambda investigation: (
                    investigation.analyzed_at is None,
                    investigation.analyzed_at,
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