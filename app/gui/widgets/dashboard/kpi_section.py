"""
SOC-IQ Dashboard

KPI Section

Displays the primary dashboard metrics using
reusable MetricCard components.
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
    Dashboard KPI section.

    Displays the four primary dashboard metrics:

    • Reports
    • IOCs
    • High Risk
    • Database
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._reports_card = MetricCard(
            title="Reports",
            value="0",
            subtitle="Analyzed Reports",
            footer="Ready",
        )

        self._ioc_card = MetricCard(
            title="IOCs",
            value="0",
            subtitle="Indicators Extracted",
            footer="Ready",
        )

        self._risk_card = MetricCard(
            title="High Risk",
            value="0",
            subtitle="Critical Investigations",
            footer="No Active Alerts",
        )

        self._database_card = MetricCard(
            title="Database",
            value="Disconnected",
            subtitle="SQLite Repository",
            footer="Waiting",
        )

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
            1,
            0,
        )

        self._layout.addWidget(
            self._database_card,
            1,
            1,
        )

        self._layout.setColumnStretch(
            0,
            1,
        )

        self._layout.setColumnStretch(
            1,
            1,
        )

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
        """
        Update all dashboard KPI values.
        """

        self._reports_card.set_value(
            reports,
        )

        self._ioc_card.set_value(
            iocs,
        )

        self._risk_card.set_value(
            high_risk,
        )

        self._database_card.set_value(
            database,
        )

    def reports_card(self) -> MetricCard:
        """Return the reports metric card."""
        return self._reports_card

    def ioc_card(self) -> MetricCard:
        """Return the IOC metric card."""
        return self._ioc_card

    def risk_card(self) -> MetricCard:
        """Return the risk metric card."""
        return self._risk_card

    def database_card(self) -> MetricCard:
        """Return the database metric card."""
        return self._database_card