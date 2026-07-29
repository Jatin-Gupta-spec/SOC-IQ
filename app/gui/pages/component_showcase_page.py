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
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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

        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self._description.setWordWrap(True)

        self._content_layout.addWidget(self._title)
        self._content_layout.addWidget(self._description)
        self._content_layout.addWidget(self._cards_header)
        self._content_layout.addStretch()

        self.layout().addWidget(self._scroll_area)

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