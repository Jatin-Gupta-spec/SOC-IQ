"""
SOC-IQ Dashboard

System Status Section

Displays operational health information for
SOC-IQ services.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import (
    Panel,
    SectionHeader,
    StatusBadge,
)
from app.gui.design.tokens import Spacing


class SystemStatusSection(QWidget):
    """
    Dashboard system status section.

    Displays:

    • Database status
    • Threat Intelligence status
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._layout = QGridLayout(self)

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(Spacing.LG)
        self._layout.setVerticalSpacing(Spacing.LG)

        self._layout.addWidget(
            self._create_database_panel(),
            0,
            0,
        )

        self._layout.addWidget(
            self._create_threat_panel(),
            0,
            1,
        )

        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)

    def _create_database_panel(self) -> QWidget:

        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        layout.setSpacing(Spacing.MD)

        layout.addWidget(
            SectionHeader(
                "Database Health",
                "Repository status",
            )
        )

        layout.addWidget(
            StatusBadge("Connected")
        )

        layout.addWidget(
            QLabel("SQLite Repository")
        )

        layout.addWidget(
            QLabel("Last Sync: 10:42")
        )

        layout.addStretch()

        return panel

    def _create_threat_panel(self) -> QWidget:

        panel = Panel()

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )
        layout.setSpacing(Spacing.MD)

        layout.addWidget(
            SectionHeader(
                "Threat Intelligence",
                "External providers",
            )
        )

        layout.addWidget(
            StatusBadge("Operational")
        )

        layout.addWidget(
            QLabel("VirusTotal Provider")
        )

        layout.addWidget(
            QLabel("Last Update: 10:41")
        )

        layout.addStretch()

        return panel