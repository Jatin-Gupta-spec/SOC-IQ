"""
SOC-IQ Dashboard

Analytics Section

Contains the dashboard analytics panels that
will later host interactive Apache ECharts
visualizations.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import (
    EmptyState,
    Panel,
    SectionHeader,
)
from app.gui.design.tokens import Spacing


class AnalyticsSection(QWidget):
    """
    Dashboard analytics section.

    Displays:

    • Risk Overview
    • IOC Distribution

    Chart rendering will be integrated
    in a later sprint.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._risk_panel = Panel()
        self._ioc_panel = Panel()

        self._layout = QGridLayout(self)

        self._build_ui()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        self._layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._layout.setHorizontalSpacing(
            Spacing.LG
        )

        self._layout.setVerticalSpacing(
            Spacing.LG
        )

        self._layout.addWidget(
            self._create_risk_panel(),
            0,
            0,
        )

        self._layout.addWidget(
            self._create_ioc_panel(),
            0,
            1,
        )

        self._layout.setColumnStretch(0, 1)
        self._layout.setColumnStretch(1, 1)

    def _create_risk_panel(self) -> QWidget:

        layout = QVBoxLayout(self._risk_panel)
        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        layout.setSpacing(Spacing.MD)

        layout.addWidget(
            SectionHeader(
                "Risk Overview",
                "Overall security posture",
            )
        )

        layout.addWidget(
            EmptyState(
                title="Risk chart unavailable",
                description=(
                    "Interactive analytics "
                    "will appear here."
                ),
            )
        )

        return self._risk_panel

    def _create_ioc_panel(self) -> QWidget:

        layout = QVBoxLayout(self._ioc_panel)
        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        layout.setSpacing(Spacing.MD)

        layout.addWidget(
            SectionHeader(
                "IOC Distribution",
                "Indicator breakdown",
            )
        )

        layout.addWidget(
            EmptyState(
                title="IOC chart unavailable",
                description=(
                    "Interactive analytics "
                    "will appear here."
                ),
            )
        )

        return self._ioc_panel