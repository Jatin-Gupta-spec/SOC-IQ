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

    Displays four primary metrics:

    • Risk Score
    • Investigations
    • IOC Count
    • Threat Intelligence
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._risk_card = MetricCard(
            title="Risk Score",
            value="72",
            subtitle="Current posture",
        )

        self._investigation_card = MetricCard(
            title="Investigations",
            value="18",
            subtitle="Completed analyses",
        )

        self._ioc_card = MetricCard(
            title="IOC Count",
            value="142",
            subtitle="Indicators extracted",
        )

        self._threat_card = MetricCard(
            title="Threat Intelligence",
            value="Healthy",
            subtitle="Provider status",
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

        self._layout.setHorizontalSpacing(Spacing.LG)
        self._layout.setVerticalSpacing(Spacing.LG)

        self._layout.addWidget(
            self._risk_card,
            0,
            0,
        )

        self._layout.addWidget(
            self._investigation_card,
            0,
            1,
        )

        self._layout.addWidget(
            self._ioc_card,
            0,
            2,
        )

        self._layout.addWidget(
            self._threat_card,
            0,
            3,
        )

        for column in range(4):
            self._layout.setColumnStretch(column, 1)

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_metrics(
        self,
        *,
        risk_score: str,
        investigations: str,
        iocs: str,
        threat_status: str,
    ) -> None:
        """
        Update all dashboard metrics.
        """

        self._risk_card.set_value(risk_score)

        self._investigation_card.set_value(
            investigations
        )

        self._ioc_card.set_value(iocs)

        self._threat_card.set_value(
            threat_status
        )