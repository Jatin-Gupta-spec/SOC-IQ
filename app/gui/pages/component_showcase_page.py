"""
SOC-IQ Design System

Component Showcase Page

Internal development page used to preview and
validate reusable UI components.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
    QVBoxLayout,
)

from app.gui.components.buttons.animated_button import AnimatedButton
from app.gui.components.buttons.icon_button import IconButton
from app.gui.components.feedback.status_badge import (
    BadgeType,
    StatusBadge,
)
from app.gui.components.feedback.loading_skeleton import (
    LoadingSkeleton,
)
from app.gui.components.feedback.toast_notification import (
    ToastNotification,
    ToastType,
)
from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.cards.metric_card import MetricCard
from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.layout.component_section import (
    ComponentSection,
)
from app.gui.design.tokens import Spacing
from app.gui.widgets.page_container import PageContainer


class ComponentShowcasePage(PageContainer):
    """
    Internal page used to preview every reusable
    design system component.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__()

        self.set_title(
            "SOC-IQ Design System"
        )

        self.set_description(
            "Internal showcase of reusable UI components."
        )

        self._create_demo_components()
        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # Component Creation
    # --------------------------------------------------

    def _create_demo_components(self) -> None:

        self._cards_section = ComponentSection(
            title="Cards",
            description="Reusable card components.",
        )

        self._buttons_section = ComponentSection(
            title="Buttons",
            description="Reusable button components.",
        )

        self._primary_button = AnimatedButton(
            "Analyze Report",
        )

        self._secondary_button = AnimatedButton(
            "Export Report",
        )

        self._icon_button = IconButton(
            QIcon(),
            tooltip="Settings",
        )

        self._status_section = ComponentSection(
            title="Status Badges",
            description="Semantic status and severity indicators.",
        )

        self._default_badge = StatusBadge(
            "Default",
            BadgeType.DEFAULT,
        )

        self._success_badge = StatusBadge(
            "Success",
            BadgeType.SUCCESS,
        )

        self._warning_badge = StatusBadge(
            "Warning",
            BadgeType.WARNING,
        )

        self._error_badge = StatusBadge(
            "Error",
            BadgeType.ERROR,
        )

        self._info_badge = StatusBadge(
            "Info",
            BadgeType.INFO,
        )

        self._low_badge = StatusBadge(
            "Low",
            BadgeType.LOW,
        )

        self._medium_badge = StatusBadge(
            "Medium",
            BadgeType.MEDIUM,
        )

        self._high_badge = StatusBadge(
            "High",
            BadgeType.HIGH,
        )

        self._critical_badge = StatusBadge(
            "Critical",
            BadgeType.CRITICAL,
        )

        self._feedback_section = ComponentSection(
            title="Feedback",
            description="Loading indicators and notification components.",
        )

        self._loading_skeleton = LoadingSkeleton(
            rows=3,
        )

        self._success_toast = ToastNotification(
            "Report analysed successfully.",
            ToastType.SUCCESS,
        )

        self._warning_toast = ToastNotification(
            "Threat intelligence rate limit approaching.",
            ToastType.WARNING,
        )

        self._error_toast = ToastNotification(
            "Unable to connect to VirusTotal.",
            ToastType.ERROR,
        )

        self._info_toast = ToastNotification(
            "Ready for analysis.",
            ToastType.INFO,
        )

        # ------------------------------------------
        # Modern Card
        # ------------------------------------------

        self._modern_card = ModernCard()
        self._modern_card.setMinimumWidth(320)

        modern_title = QLabel("Modern Card")
        modern_description = QLabel(
            "Base reusable surface used across "
            "the SOC-IQ dashboard."
        )

        self._modern_card.add_widget(modern_title)
        self._modern_card.add_widget(
            modern_description
        )
        self._modern_card.add_stretch()

        # ------------------------------------------
        # Glass Card
        # ------------------------------------------

        self._glass_card = GlassCard()
        self._glass_card.setMinimumWidth(320)

        glass_title = QLabel("Glass Card")
        glass_description = QLabel(
            "Elevated translucent surface "
            "for premium widgets."
        )

        self._glass_card.add_widget(glass_title)
        self._glass_card.add_widget(
            glass_description
        )
        self._glass_card.add_stretch()

        # ------------------------------------------
        # Metric Card
        # ------------------------------------------

        self._metric_card = MetricCard(
            title="Reports",
            value="128",
            subtitle="Analysed Reports",
            footer="Updated just now",
        )

        self._metric_card.setMinimumWidth(320)

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:

        cards_layout = QHBoxLayout()

        cards_layout.setSpacing(
            Spacing.LG
        )

        cards_layout.addWidget(
            self._modern_card,
            1,
        )

        cards_layout.addWidget(
            self._glass_card,
            1,
        )

        cards_layout.addWidget(
            self._metric_card,
            1,
        )

        self._cards_section.add_layout(
            cards_layout,
        )

        self.content_layout().addWidget(
            self._cards_section,
        )

        buttons_layout = QHBoxLayout()

        buttons_layout.setSpacing(
            Spacing.LG,
        )

        buttons_layout.addWidget(
            self._primary_button,
        )

        buttons_layout.addWidget(
            self._secondary_button,
        )

        buttons_layout.addWidget(
            self._icon_button,
        )

        buttons_layout.addStretch()

        self._buttons_section.add_layout(
            buttons_layout,
        )

        self.content_layout().addWidget(
            self._buttons_section,
        )

        status_layout = QHBoxLayout()

        status_layout.setSpacing(
            Spacing.MD,
        )

        status_layout.addWidget(self._default_badge)
        status_layout.addWidget(self._success_badge)
        status_layout.addWidget(self._warning_badge)
        status_layout.addWidget(self._error_badge)
        status_layout.addWidget(self._info_badge)
        status_layout.addWidget(self._low_badge)
        status_layout.addWidget(self._medium_badge)
        status_layout.addWidget(self._high_badge)
        status_layout.addWidget(self._critical_badge)

        status_layout.addStretch()

        self._status_section.add_layout(
            status_layout,
        )

        self.content_layout().addWidget(
            self._status_section,
        )

        feedback_layout = QVBoxLayout()

        feedback_layout.setSpacing(
            Spacing.MD,
        )

        feedback_layout.addWidget(
            self._loading_skeleton,
        )

        feedback_layout.addWidget(
            self._success_toast,
        )

        feedback_layout.addWidget(
            self._warning_toast,
        )

        feedback_layout.addWidget(
            self._error_toast,
        )

        feedback_layout.addWidget(
            self._info_toast,
        )

        self._feedback_section.add_layout(
            feedback_layout,
        )

        self.content_layout().addWidget(
            self._feedback_section,
        )

        self.content_layout().addStretch()

    # --------------------------------------------------
    # Theme
    # --------------------------------------------------

    def _apply_theme(self) -> None:

        palette = self.theme.palette
        fonts = self.theme.fonts

        for label in self.findChildren(QLabel):

            if label.text() in (
                "Modern Card",
                "Glass Card",
            ):
                label.setFont(
                    fonts.title()
                )

                label.setStyleSheet(
                    f"color:{palette.text_primary};"
                )

            elif (
                "surface" in label.text().lower()
                or "premium" in label.text().lower()
            ):
                label.setFont(
                    fonts.body()
                )

                label.setStyleSheet(
                    f"color:{palette.text_secondary};"
                )