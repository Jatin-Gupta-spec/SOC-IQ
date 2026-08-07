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
from app.logger import logger


class RiskDashboardPage(QWidget):
    """
    Enterprise Risk Analytics Dashboard Page.
    """

    _SEVERITY_LEVELS = (
        "CRITICAL",
        "HIGH",
        "MEDIUM",
    )

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

        self._severity_labels = {
            "CRITICAL": QLabel("• Critical Severity: 12 Investigations (Severe Threat)"),
            "HIGH": QLabel("• High Severity: 24 Investigations (Significant Risk)"),
            "MEDIUM": QLabel("• Medium Severity: 45 Investigations (Moderate Concern)"),
            "LOW": QLabel("• Low / Info: 47 Investigations (Minimal Impact)"),
        }

        severity_colors = {
            "CRITICAL": palette.severity_critical,
            "HIGH": palette.severity_high,
            "MEDIUM": palette.severity_medium,
            "LOW": palette.severity_low,
        }

        for severity, label in self._severity_labels.items():
            label.setFont(fonts.body())
            label.setStyleSheet(
                f"color: {severity_colors[severity]}; font-weight: 600;"
            )

        card_layout.addWidget(title)

        for label in self._severity_labels.values():
            card_layout.addWidget(label)

        self._breakdown_card.add_layout(card_layout)

    def refresh(self) -> None:
        """
        Reload risk metrics from database.
        """
        try:
            investigations = self._service.list_all()

        except Exception:
            # A locked/corrupted database or disk error here would
            # otherwise propagate straight out of refresh() and crash
            # the page. The repository layer is right to raise rather
            # than swallow this -- but showing a stale/blank dashboard
            # is safer for a SOC analyst than an unhandled exception,
            # as long as we're honest that the data couldn't be loaded
            # rather than implying "zero investigations exist."
            logger.exception(
                "Failed to load investigations for risk dashboard."
            )

            self._metric_posture.set_value("UNKNOWN")
            self._metric_avg_score.set_value("N/A")
            self._metric_critical.set_value("N/A")

            for label in self._severity_labels.values():
                label.setText("• Data unavailable — could not load investigations")

            return

        if not investigations:
            self._metric_posture.set_value("NOMINAL")
            self._metric_avg_score.set_value("0.0 / 100")
            self._metric_critical.set_value("0")

            # These labels live in self._severity_labels (built in
            # _build_breakdown_card) -- self._lbl_critical etc. were
            # never created and referencing them here raised an
            # unhandled AttributeError on every fresh install / empty
            # database, before a single investigation existed.
            self._severity_labels["CRITICAL"].setText(
                "• Critical Severity: 0 Investigations"
            )
            self._severity_labels["HIGH"].setText(
                "• High Severity: 0 Investigations"
            )
            self._severity_labels["MEDIUM"].setText(
                "• Medium Severity: 0 Investigations"
            )
            self._severity_labels["LOW"].setText(
                "• Low / Info: 0 Investigations"
            )
            return

        total = len(investigations)
        critical = sum(
            1 for i in investigations
            if (i.severity or "").upper() == self._SEVERITY_LEVELS[0]
        )
        high = sum(
            1 for i in investigations
            if (i.severity or "").upper() == self._SEVERITY_LEVELS[1]
        )
        medium = sum(
            1 for i in investigations
            if (i.severity or "").upper() == self._SEVERITY_LEVELS[2]
        )
        low = total - (critical + high + medium)

        avg_score = sum(i.risk_score for i in investigations) / total if total > 0 else 0

        if critical > 0 or avg_score >= 75:
            posture = "CRITICAL"
        elif high > 0 or avg_score >= 50:
            posture = "ELEVATED"
        else:
            posture = "NOMINAL"

        self._metric_posture.set_value(posture)
        self._metric_avg_score.set_value(f"{avg_score:.1f} / 100")
        self._metric_critical.set_value(str(critical))

        self._severity_labels["CRITICAL"].setText(
            f"• Critical Severity: {critical} Investigations"
        )

        self._severity_labels["HIGH"].setText(
            f"• High Severity: {high} Investigations"
        )

        self._severity_labels["MEDIUM"].setText(
            f"• Medium Severity: {medium} Investigations"
        )

        self._severity_labels["LOW"].setText(
            f"• Low / Info: {low} Investigations"
        )