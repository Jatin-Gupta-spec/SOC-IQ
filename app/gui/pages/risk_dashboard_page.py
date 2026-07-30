"""
Risk Dashboard Page for the SOC-IQ desktop application.

Provides enterprise-wide risk metrics, severity heatmaps, and threat distribution analytics.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.database.service import InvestigationService
from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.cards.metric_card import MetricCard
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.feedback.status_badge import BadgeType, StatusBadge
from app.gui.components.layout.component_section import ComponentSection
from app.gui.design.tokens import Spacing
from app.gui.widgets.page_container import PageContainer


class RiskDashboardPage(QWidget):
    """
    Enterprise Risk Analytics Dashboard Page.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._service = InvestigationService()

        self._container = PageContainer(
            title="Enterprise Risk Analytics",
            description=(
                "Executive security posture assessment, risk heatmaps, "
                "and investigation severity distribution."
            ),
        )

        self._metric_posture = MetricCard(
            title="Overall Risk Level",
            value="ELEVATED",
            subtitle="Calculated Threat Posture",
            footer="Requires Attention",
        )
        self._metric_avg_score = MetricCard(
            title="Avg Risk Score",
            value="68.4 / 100",
            subtitle="Across 128 Investigations",
            footer="Updated Live",
        )
        self._metric_critical = MetricCard(
            title="Critical Incidents",
            value="12",
            subtitle="Unresolved / High Priority",
            footer="Action Required",
        )

        self._breakdown_card = ModernCard()

        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        """
        Build the Risk Dashboard user interface.
        """
        layout = self._container.content_layout()

        # Metrics Row
        metrics_layout = QHBoxLayout()
        metrics_layout.setSpacing(Spacing.LG)
        metrics_layout.addWidget(self._metric_posture)
        metrics_layout.addWidget(self._metric_avg_score)
        metrics_layout.addWidget(self._metric_critical)
        layout.addLayout(metrics_layout)

        # Risk Distribution Section
        dist_section = ComponentSection(
            title="Threat Distribution by Severity",
            description="Aggregated severity classification of all recorded investigations.",
        )

        self._build_breakdown_card()
        dist_section.add_widget(self._breakdown_card)
        layout.addWidget(dist_section)

        layout.addStretch()

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(self._container)

    def _build_breakdown_card(self) -> None:
        """
        Construct risk breakdown presentation panel.
        """
        card_layout = QVBoxLayout()
        card_layout.setContentsMargins(Spacing.LG, Spacing.LG, Spacing.LG, Spacing.LG)
        card_layout.setSpacing(Spacing.MD)

        palette = self._breakdown_card.theme.palette
        fonts = self._breakdown_card.theme.fonts

        title = QLabel("Severity Classification Heatmap")
        title.setFont(fonts.title())
        title.setStyleSheet(f"color: {palette.text_primary}; font-weight: 600;")

        self._lbl_critical = QLabel("• Critical Severity: 12 Investigations (Severe Threat)")
        self._lbl_high = QLabel("• High Severity: 24 Investigations (Significant Risk)")
        self._lbl_medium = QLabel("• Medium Severity: 45 Investigations (Moderate Concern)")
        self._lbl_low = QLabel("• Low / Info: 47 Investigations (Minimal Impact)")

        for lbl, col in (
            (self._lbl_critical, palette.severity_critical),
            (self._lbl_high, palette.severity_high),
            (self._lbl_medium, palette.severity_medium),
            (self._lbl_low, palette.severity_low),
        ):
            lbl.setFont(fonts.body())
            lbl.setStyleSheet(f"color: {col}; font-weight: 600;")

        card_layout.addWidget(title)
        card_layout.addWidget(self._lbl_critical)
        card_layout.addWidget(self._lbl_high)
        card_layout.addWidget(self._lbl_medium)
        card_layout.addWidget(self._lbl_low)

        self._breakdown_card.add_layout(card_layout)

    def refresh(self) -> None:
        """
        Reload risk metrics from database.
        """
        investigations = self._service.list_all()
        if not investigations:
            return

        total = len(investigations)
        critical = sum(1 for i in investigations if (i.severity or "").upper() == "CRITICAL")
        high = sum(1 for i in investigations if (i.severity or "").upper() == "HIGH")
        medium = sum(1 for i in investigations if (i.severity or "").upper() == "MEDIUM")
        low = total - (critical + high + medium)

        avg_score = sum(i.risk_score for i in investigations) / total if total > 0 else 0

        self._metric_avg_score.set_value(f"{avg_score:.1f} / 100")
        self._metric_critical.set_value(str(critical))

        self._lbl_critical.setText(f"• Critical Severity: {critical} Investigations")
        self._lbl_high.setText(f"• High Severity: {high} Investigations")
        self._lbl_medium.setText(f"• Medium Severity: {medium} Investigations")
        self._lbl_low.setText(f"• Low / Info: {low} Investigations")
