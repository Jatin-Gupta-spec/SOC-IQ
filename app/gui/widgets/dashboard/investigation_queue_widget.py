"""
Investigation Queue Widget

Displays the most recent investigations
inside the SOC-IQ dashboard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from app.database.models import Investigation
from app.gui.components.cards.modern_card import ModernCard


class InvestigationQueueWidget(ModernCard):
    """
    Displays the latest investigations.
    """

    def __init__(self) -> None:
        super().__init__()

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        """
        Build widget interface.
        """

        palette = self.theme.palette
        fonts = self.theme.fonts

        layout = QVBoxLayout()

        title = QLabel(
            "Investigation Queue"
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

        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self._table.setAlternatingRowColors(True)

        self._table.setShowGrid(False)

        self._table.horizontalHeader().setStretchLastSection(
            True
        )

        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        layout.addWidget(title)
        layout.addWidget(self._table)

        self.add_layout(layout)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def clear(self) -> None:
        """
        Clear queue.
        """

        self._table.setRowCount(0)

    def load_investigations(
        self,
        investigations: list[Investigation],
    ) -> None:
        """
        Populate investigation queue.
        """

        self.clear()

        self._table.setRowCount(
            len(investigations)
        )

        for row, investigation in enumerate(
            investigations
        ):

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    investigation.report_name
                ),
            )

            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    investigation.severity
                ),
            )

            self._table.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(
                        investigation.risk_score
                    )
                ),
            )

            self._table.setItem(
                row,
                3,
                QTableWidgetItem(
                    investigation.analyzed_at.strftime(
                        "%d %b %H:%M"
                    )
                ),
            )

        self._table.resizeRowsToContents()