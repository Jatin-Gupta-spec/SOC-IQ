"""
SOC-IQ Design System

Metric Card

Enterprise KPI card built on top of ModernCard.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.cards.modern_card import ModernCard
from app.gui.design.tokens import Spacing


class MetricCard(ModernCard):
    """
    Enterprise KPI card.

    Displays:

    • Title
    • Value
    • Subtitle
    • Footer
    • Optional badge
    """

    def __init__(
        self,
        title: str,
        value: str,
        subtitle: str = "",
        footer: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title_label = QLabel(title)
        self._value_label = QLabel(value)
        self._subtitle_label = QLabel(subtitle)

        self._footer_label = QLabel(footer)
        self._badge_label = QLabel()

        self._build_content()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_content(self) -> None:

        layout = self.content_layout()

        header = QHBoxLayout()

        header.addWidget(self._title_label)
        header.addStretch()
        header.addWidget(self._badge_label)

        layout.addLayout(header)

        layout.addSpacing(Spacing.SM)

        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(self._value_label)

        if self._subtitle_label.text():
            layout.addSpacing(Spacing.XS)

            self._subtitle_label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            layout.addWidget(
                self._subtitle_label
            )

        layout.addStretch()

        if self._footer_label.text():
            layout.addSpacing(Spacing.SM)
            layout.addWidget(self._footer_label)

    def _apply_theme(self) -> None:

        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title_label.setFont(
            fonts.label()
        )

        self._value_label.setFont(
            fonts.display()
        )

        self._subtitle_label.setFont(
            fonts.body_small()
        )

        self._footer_label.setFont(
            fonts.caption()
        )

        self._badge_label.setFont(
            fonts.caption()
        )

        self._title_label.setStyleSheet(
            f"color:{palette.text_secondary};"
        )

        self._value_label.setStyleSheet(
            f"color:{palette.text_primary};"
        )

        self._subtitle_label.setStyleSheet(
            f"color:{palette.text_secondary};"
        )

        self._footer_label.setStyleSheet(
            f"color:{palette.text_secondary};"
        )

        self._badge_label.setStyleSheet(
            f"""
            color:{palette.text_primary};
            padding:2px 8px;
            border-radius:10px;
            """
        )

        self._badge_label.hide()

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_value(self, value: str) -> None:
        self._value_label.setText(value)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def set_footer(self, footer: str) -> None:
        self._footer_label.setText(footer)
        self._footer_label.setVisible(bool(footer))

    def set_badge(self, text: str) -> None:
        self._badge_label.setText(text)
        self._badge_label.setVisible(bool(text))

    def clear_badge(self) -> None:
        self._badge_label.clear()
        self._badge_label.hide()