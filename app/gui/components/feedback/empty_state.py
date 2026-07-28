"""
SOC-IQ Design System
Empty State

Reusable empty state component.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Spacing


class EmptyState(BaseWidget):
    """
    Reusable empty state widget.

    Displays a title, description and
    optional primary action.
    """

    def __init__(
        self,
        title: str,
        description: str,
        button_text: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._title = QLabel(title)
        self._description = QLabel(description)
        self._button = QPushButton(button_text)

        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.MD)

        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._description.setWordWrap(True)

        layout.addWidget(self._title)
        layout.addWidget(self._description)

        if self._button.text():
            layout.addWidget(
                self._button,
                alignment=Qt.AlignmentFlag.AlignCenter,
            )

        self._button.setVisible(bool(self._button.text()))

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._title.setFont(fonts.heading())
        self._description.setFont(fonts.body())

        self._title.setStyleSheet(
            f"color: {palette.text_primary};"
        )

        self._description.setStyleSheet(
            f"color: {palette.text_secondary};"
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def primary_button(self) -> QPushButton:
        return self._button

    def set_title(self, title: str) -> None:
        self._title.setText(title)

    def set_description(self, description: str) -> None:
        self._description.setText(description)

    def set_button_text(self, text: str) -> None:
        self._button.setText(text)
        self._button.setVisible(bool(text))