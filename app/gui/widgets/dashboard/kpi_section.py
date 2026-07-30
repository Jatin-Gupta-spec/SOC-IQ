"""
SOC-IQ Dashboard

KPI Section

Displays the primary dashboard metrics using
enterprise MetricCard components.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QWidget,
)

from app.gui.components import MetricCard
from app.gui.design.tokens import Spacing


class KPISection(QWidget):
    """
    Executive dashboard KPI grid.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._reports_card = MetricCard(
            title="Investigations",
            value="0",
            subtitle="Completed Reports",
            footer="Updated just now",
        )

        self._ioc_card = MetricCard(
            title="Indicators",
            value="0",
            subtitle="Extracted IOCs",
            footer="Across all reports",
        )

        self._risk_card = MetricCard(
            title="High Severity",
            value="0",
            subtitle="Critical Investigations",
            footer="Requires attention",
        )

        self._database_card = MetricCard(
            title="Repository",
            value="ONLINE",
            subtitle="SQLite Database",
            footer="Healthy",
        )

        self._layout = QGridLayout(self)

        self._build_ui()
        self._configure_cards()

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
            Spacing.LG,
        )

        self._layout.setVerticalSpacing(
            Spacing.LG,
        )

        self._layout.addWidget(
            self._reports_card,
            0,
            0,
        )

        self._layout.addWidget(
            self._ioc_card,
            0,
            1,
        )

        self._layout.addWidget(
            self._risk_card,
            0,
            2,
        )

        self._layout.addWidget(
            self._database_card,
            0,
            3,
        )

        for column in range(4):
            self._layout.setColumnStretch(column, 1)

    # --------------------------------------------------
    # Card Styling
    # --------------------------------------------------

    def _configure_cards(self) -> None:

        self._reports_card.set_badge("+12%")
        self._reports_card.set_icon("📄")

        self._ioc_card.set_badge("+38")
        self._ioc_card.set_icon("🎯")

        self._risk_card.set_badge("HIGH")
        self._risk_card.set_icon("🚨")

        self._database_card.set_badge("LIVE")
        self._database_card.set_icon("🟢")

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_metrics(
        self,
        *,
        reports: str,
        iocs: str,
        high_risk: str,
        database: str,
    ) -> None:

        self._reports_card.set_value(reports)

        self._ioc_card.set_value(iocs)

        self._risk_card.set_value(high_risk)

        self._database_card.set_value(database)

    def reports_card(self) -> MetricCard:
        return self._reports_card

    def ioc_card(self) -> MetricCard:
        return self._ioc_card

    def risk_card(self) -> MetricCard:
        return self._risk_card

    def database_card(self) -> MetricCard:
        return self._database_card