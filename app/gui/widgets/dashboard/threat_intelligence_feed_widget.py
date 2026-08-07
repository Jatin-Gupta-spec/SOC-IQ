"""
Threat Intelligence Feed Widget

Displays the latest threat intelligence
activity on the dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QHeaderView,
    QStackedLayout,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.feedback.status_badge import (
    BadgeType,
    StatusBadge,
)


class ThreatIntelligenceFeedWidget(
    ModernCard,
):
    """
    Dashboard threat intelligence feed.
    """

    _SEVERITY_BADGE_MAP = {
        "LOW": BadgeType.LOW,
        "MEDIUM": BadgeType.MEDIUM,
        "HIGH": BadgeType.HIGH,
        "CRITICAL": BadgeType.CRITICAL,
        "INFO": BadgeType.INFO,
    }

    def __init__(
        self,
        parent=None,
    ) -> None:
        super().__init__(parent)

        palette = self.theme.palette
        fonts = self.theme.fonts

        header_row = QHBoxLayout()

        title = QLabel(
            "Threat Intelligence Feed"
        )

        title.setFont(
            fonts.title()
        )

        title.setStyleSheet(
            f"color: {palette.text_primary}; font-weight: 600;"
        )

        self._count_label = QLabel("0 entries")

        self._count_label.setFont(fonts.caption())

        self._count_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        header_row.addWidget(title)
        header_row.addStretch()
        header_row.addWidget(self._count_label)

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

        self._empty_state = self._build_empty_state(palette, fonts)

        self._stack = QStackedLayout()
        self._stack.addWidget(self._table)
        self._stack.addWidget(self._empty_state)

        layout = QVBoxLayout()

        layout.addLayout(header_row)
        layout.addLayout(self._stack)

        self.add_layout(
            layout
        )

        self._set_populated(False)

    def _build_empty_state(self, palette, fonts) -> QWidget:
        container = QWidget()

        empty_layout = QVBoxLayout(container)
        empty_layout.addStretch()

        title_label = QLabel("No threat intelligence activity")
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label.setFont(fonts.body())
        title_label.setStyleSheet(
            f"color: {palette.text_secondary}; font-weight: 600;"
        )

        description_label = QLabel(
            "New indicator lookups and enrichment results will "
            "appear here."
        )
        description_label.setWordWrap(True)
        description_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description_label.setFont(fonts.caption())
        description_label.setStyleSheet(
            f"color: {palette.text_muted};"
        )

        empty_layout.addWidget(title_label)
        empty_layout.addWidget(description_label)
        empty_layout.addStretch()

        return container

    def _set_populated(self, populated: bool) -> None:
        self._stack.setCurrentWidget(
            self._table if populated else self._empty_state
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

            # .get() with defaults throughout: a single malformed or
            # partial threat-intel entry (e.g. an enrichment result
            # that failed halfway through) should degrade to "--"
            # cells, not crash the whole dashboard render.
            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    item.get("title", "Unknown")
                ),
            )

            # Severity rendered as a real StatusBadge cell widget
            # instead of plain table text — matches the severity
            # treatment used in the investigation queue and the
            # featured investigation card.
            severity_text = str(item.get("severity", "INFO")).upper()

            badge = StatusBadge(
                severity_text,
                self._SEVERITY_BADGE_MAP.get(
                    severity_text,
                    BadgeType.DEFAULT,
                ),
            )

            self._table.setCellWidget(
                row,
                1,
                badge,
            )

            self._table.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(item.get("risk_score", "--"))
                ),
            )

            self._table.setItem(
                row,
                3,
                QTableWidgetItem(
                    item.get("time", "--")
                ),
            )

        count = len(feed)

        self._count_label.setText(
            f"{count} entry" if count == 1 else f"{count} entries"
        )

        self._set_populated(count > 0)

    def clear(self) -> None:
        """
        Clear the feed.
        """

        self._table.setRowCount(0)

        self._count_label.setText("0 entries")

        self._set_populated(False)