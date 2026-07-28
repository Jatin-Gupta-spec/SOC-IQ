"""
SOC-IQ Design System
Metric Card

Reusable KPI card built on top of ModernCard.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Spacing


class MetricCard(ModernCard):
    """
    Reusable metric card.

    Displays a title, a primary metric value,
    and an optional subtitle.
    """

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title_label = QLabel(title)
        self._value_label = QLabel(value)
        self._subtitle_label = QLabel(subtitle)

        self._build_content()
        self._apply_metric_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_content(self) -> None:
        layout = self.content_layout()

        layout.addWidget(self._title_label)
        layout.addSpacing(Spacing.SM)
        layout.addWidget(self._value_label)

        if self._subtitle_label.text():
            layout.addSpacing(Spacing.XS)
            layout.addWidget(self._subtitle_label)

        layout.addStretch()

    def _apply_metric_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title_label.setFont(fonts.label())
        self._value_label.setFont(fonts.display())
        self._subtitle_label.setFont(fonts.body_small())

        self._title_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

        self._value_label.setStyleSheet(
            f"color: {palette.text_primary};"
        )

        self._subtitle_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def title(self) -> str:
        return self._title_label.text()

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def value(self) -> str:
        return self._value_label.text()

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def subtitle(self) -> str:
        return self._subtitle_label.text()