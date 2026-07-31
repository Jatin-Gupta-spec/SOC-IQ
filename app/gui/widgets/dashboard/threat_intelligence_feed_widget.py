"""
Threat Intelligence Feed Widget

Displays the latest threat intelligence
activity on the dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.gui.components.cards.modern_card import ModernCard


class ThreatIntelligenceFeedWidget(
    ModernCard,
):
    """
    Dashboard threat intelligence feed.
    """

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        palette = self.theme.palette
        fonts = self.theme.fonts

        title = QLabel(
            "Threat Intelligence Feed"
        )

        title.setFont(
            fonts.title()
        )

        title.setStyleSheet(
            f"""
            color: {palette.text_primary};
            font-weight: 600;
            """
        )

        self._table = QTableWidget()

        self._table.setColumnCount(4)

        self._table.setHorizontalHeaderLabels(
            [
                "Report",
                "Severity",
                "Risk",
                "Time",
            ]
        )

        self._table.verticalHeader().hide()

        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self._table.setSelectionBehavior(
            QTableWidget.SelectRows
        )

        self._table.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

        self._table.setAlternatingRowColors(
            True
        )

        layout = QVBoxLayout()

        layout.addWidget(title)

        layout.addWidget(
            self._table
        )

        self.add_layout(
            layout
        )

    def load_feed(
        self,
        feed: list[dict[str, str]],
    ) -> None:
        """
        Populate the table.
        """

        self._table.setRowCount(
            len(feed)
        )

        for row, item in enumerate(feed):

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    item["title"]
                ),
            )

            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    item["severity"]
                ),
            )

            self._table.setItem(
                row,
                2,
                QTableWidgetItem(
                    item["risk_score"]
                ),
            )

            self._table.setItem(
                row,
                3,
                QTableWidgetItem(
                    item["time"]
                ),
            )