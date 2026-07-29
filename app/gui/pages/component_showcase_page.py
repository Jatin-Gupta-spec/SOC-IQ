"""
SOC-IQ Design System

Component Showcase Page

Internal development page used to preview and
validate reusable UI components.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
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