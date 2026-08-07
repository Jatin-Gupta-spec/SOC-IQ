"""
SOC-IQ Dashboard

KPI Section

Displays the primary dashboard metrics using
enterprise MetricCard components.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components import BaseWidget, MetricCard
from app.gui.design.tokens import Spacing


class KPISection(BaseWidget):
    """
    Executive dashboard KPI grid.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._eyebrow_label = QLabel("KEY METRICS")

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

        self._outer_layout = QVBoxLayout(self)
        self._layout = QGridLayout()

        self._build_ui()
        self.refresh_theme()
        self._configure_cards()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        self._outer_layout.setContentsMargins(0, 0, 0, 0)
        self._outer_layout.setSpacing(Spacing.SM)

        self._outer_layout.addWidget(self._eyebrow_label)

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(Spacing.LG)
        self._layout.setVerticalSpacing(Spacing.LG)

        self._layout.addWidget(self._reports_card, 0, 0)
        self._layout.addWidget(self._ioc_card, 0, 1)
        self._layout.addWidget(self._risk_card, 0, 2)
        self._layout.addWidget(self._database_card, 0, 3)

        for column in range(4):
            self._layout.setColumnStretch(column, 1)

        self._outer_layout.addLayout(self._layout)

    def refresh_theme(self) -> None:
        """
        Refresh the KPI section styling.
        """

        self._eyebrow_label.setFont(
            self.fonts.label(),
        )

        self._eyebrow_label.setStyleSheet(
            f"""
            color: {self.palette.text_muted};
            font-weight: 700;
            letter-spacing: 1.5px;
            """
        )

    # --------------------------------------------------
    # Card Styling
    # --------------------------------------------------

    def _configure_cards(self) -> None:
        # Plain, widely-supported geometric glyphs (Geometric
        # Shapes Unicode block) instead of icon-font-dependent
        # symbols that fall back to "tofu" boxes on systems
        # without the right font installed.

        self._reports_card.set_icon("■")
        self._ioc_card.set_icon("●")
        self._risk_card.set_icon("▲")
        self._database_card.set_icon("◆")

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
        reports_badge: str = "",
        iocs_badge: str = "",
        risk_badge: str = "",
        database_badge: str = "",
    ) -> None:
        """
        Update KPI values.

        Badges are optional and reflect real state passed in by
        the caller (e.g. a trend or live indicator computed by
        DashboardController). Omitting a badge hides it — there
        is no default/placeholder badge text.
        """

        self._reports_card.set_value(reports)
        self._ioc_card.set_value(iocs)
        self._risk_card.set_value(high_risk)
        self._database_card.set_value(database)

        if reports_badge:
            self._reports_card.set_badge(reports_badge)
        else:
            self._reports_card.clear_badge()

        if iocs_badge:
            self._ioc_card.set_badge(iocs_badge)
        else:
            self._ioc_card.clear_badge()

        if risk_badge:
            self._risk_card.set_badge(risk_badge)
        else:
            self._risk_card.clear_badge()

        if database_badge:
            self._database_card.set_badge(database_badge)
        else:
            self._database_card.clear_badge()

    def reports_card(self) -> MetricCard:
        return self._reports_card

    def ioc_card(self) -> MetricCard:
        return self._ioc_card

    def risk_card(self) -> MetricCard:
        return self._risk_card

    def database_card(self) -> MetricCard:
        return self._database_card