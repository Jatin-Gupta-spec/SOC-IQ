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
from app.gui.design.theme.theme_manager import theme_manager


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

        # BATCH 06: severity colors are read live from
        # theme_manager.palette inside data() below (see the
        # ForegroundRole branch) rather than cached on the model, so
        # a runtime palette swap is reflected the next time a cell
        # is painted. Qt views don't repaint on their own just
        # because the underlying palette object changed, though --
        # they only ask for ForegroundRole again when the model
        # tells them to via dataChanged. Connecting here mirrors the
        # pattern ThemeManager already documents for ModernCard
        # ("Widgets that cache palette-derived stylesheets ...
        # should connect to this"): this model doesn't cache colors,
        # but it does need to prompt the view to re-fetch them.
        theme_manager.palette_changed.connect(
            self._on_palette_changed
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

            # BATCH 06: severity colors now come from the same
            # semantic source RiskGaugeWidget already uses
            # (theme_manager.palette.severity_*) instead of a
            # second, independently hardcoded hex palette living
            # only in this model. Read live (not cached on
            # `self`) so a runtime palette swap is picked up the
            # next time this cell is painted -- see
            # `_on_palette_changed()` for how the view is told to
            # re-ask for it.
            palette = theme_manager.palette

            if severity == "LOW":
                return QColor(palette.severity_low)

            if severity == "MEDIUM":
                return QColor(palette.severity_medium)

            if severity == "HIGH":
                return QColor(palette.severity_high)

            if severity == "CRITICAL":
                return QColor(palette.severity_critical)

        return None

    def _on_palette_changed(self) -> None:
        """
        Prompt the view to re-fetch severity cell colors after a
        theme switch.

        Nothing here actually changes: `data()` above already reads
        `theme_manager.palette` live, so the *next* paint of any
        Severity cell already returns the new color. The problem is
        that nothing triggers that next paint on its own -- Qt views
        only re-ask a model for a given role when the model emits
        `dataChanged` for it. This just emits that signal, scoped to
        the Severity column and `ForegroundRole`, so already-rendered
        rows pick up the new palette immediately instead of only
        updating whenever some unrelated reset/scroll happens to
        repaint them.
        """

        if not self._investigations:
            return

        top_left = self.index(0, 2)

        bottom_right = self.index(
            self.rowCount() - 1,
            2,
        )

        self.dataChanged.emit(
            top_left,
            bottom_right,
            [Qt.ItemDataRole.ForegroundRole],
        )

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

        This is the authoritative lookup for "what Investigation is
        currently shown at source row N" -- it always reflects
        whatever `self._investigations` holds right now (post
        sort/filter), so callers resolving an activated row should
        use this instead of keeping a second, independently-ordered
        copy of the investigation list that could drift out of sync
        with what the model last reset/reordered to.
        """

        if row < 0:
            return None

        if row >= len(self._investigations):
            return None

        return self._investigations[row]