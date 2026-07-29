"""
SOC-IQ Design System
Component Showcase Page

Internal development page used to preview and
validate reusable UI components.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QHBoxLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.components.cards.glass_card import GlassCard
from app.gui.components.cards.metric_card import MetricCard

from app.gui.components.layout import SectionHeader
from app.gui.design.tokens import Spacing
from app.gui.widgets.page_container import PageContainer


class ComponentShowcasePage(PageContainer):
    """
    Internal page that showcases every reusable
    design system component.

    This page is intended for development and
    visual validation only.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._scroll_area = QScrollArea(self)
        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout(self._content_widget)

        self._title = QLabel("SOC-IQ Design System")
        self._description = QLabel(
            "Internal showcase of reusable UI components."
        )

        self._cards_header = SectionHeader(
            "Cards",
            "Reusable card components."
        )

        # ----------------------------------
        # Demo Components
        # ----------------------------------

        self._modern_card = ModernCard()
        self._modern_card.setMinimumWidth(320)

        self._glass_card = GlassCard()
        self._glass_card.setMinimumWidth(320)

        self._metric_card = MetricCard(
            title="Reports",
            value="128",
            subtitle="Analysed Reports",
            footer="Updated just now",
        )
        self._metric_card.setMinimumWidth(320)

        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self._scroll_area.setWidget(self._content_widget)

        self._content_layout.setContentsMargins(
            Spacing.XL,
            Spacing.XL,
            Spacing.XL,
            Spacing.XL,
        )

        self._content_layout.setSpacing(Spacing.XL)

        # ----------------------------------
        # Cards Layout
        # ----------------------------------

        cards_layout = QHBoxLayout()

        cards_layout.setSpacing(Spacing.LG)

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

        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._description.setWordWrap(True)

        self._content_layout.addWidget(self._title)
        self._content_layout.addWidget(self._description)

        self._content_layout.addWidget(
            self._cards_header,
        )

        self._content_layout.addLayout(
            cards_layout,
        )

        self._content_layout.addStretch()

        self.layout().addWidget(
            self._scroll_area,
        )

    # --------------------------------------------------
    # Theme
    # --------------------------------------------------

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title.setFont(fonts.display())
        self._description.setFont(fonts.body())

        self._title.setStyleSheet(
            f"color: {palette.text_primary};"
        )

        self._description.setStyleSheet(
            f"color: {palette.text_secondary};"
        )