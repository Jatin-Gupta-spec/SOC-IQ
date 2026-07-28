"""
SOC-IQ Design System
Section Header

Reusable section header for pages and cards.
"""

from __future__ import annotations

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Spacing


class SectionHeader(BaseWidget):
    """
    Standard section header.

    Displays a title and an optional subtitle.
    """

    def __init__(
        self,
        title: str,
        subtitle: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title_label = QLabel(title)
        self._subtitle_label = QLabel(subtitle)

        self._build_ui()
        self._apply_theme()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.XS)

        layout.addWidget(self._title_label)

        if self._subtitle_label.text():
            layout.addWidget(self._subtitle_label)

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title_label.setFont(fonts.heading())
        self._subtitle_label.setFont(fonts.body_small())

        self._title_label.setStyleSheet(
            f"color: {palette.text_primary};"
        )

        self._subtitle_label.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

    # -----------------------------
    # Public API
    # -----------------------------

    def set_title(self, title: str) -> None:
        self._title_label.setText(title)

    def set_subtitle(self, subtitle: str) -> None:
        self._subtitle_label.setText(subtitle)
        self._subtitle_label.setVisible(bool(subtitle))

    def title(self) -> str:
        return self._title_label.text()

    def subtitle(self) -> str:
        return self._subtitle_label.text()