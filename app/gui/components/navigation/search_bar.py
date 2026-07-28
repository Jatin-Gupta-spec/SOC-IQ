"""
SOC-IQ Design System
Search Bar

Reusable search component for SOC-IQ.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class SearchBar(BaseWidget):
    """
    Reusable search bar.

    Provides a themed search input with
    an integrated clear button.
    """

    text_changed = Signal(str)
    search_requested = Signal(str)

    def __init__(
        self,
        placeholder: str = "Search...",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._line_edit = QLineEdit()
        self._clear_button = QPushButton("×")

        self._line_edit.setPlaceholderText(placeholder)

        self._build_ui()
        self._connect_signals()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(Spacing.SM)

        self._clear_button.setFixedWidth(32)

        layout.addWidget(self._line_edit)
        layout.addWidget(self._clear_button)

    def _connect_signals(self) -> None:
        self._line_edit.textChanged.connect(self.text_changed)

        self._line_edit.returnPressed.connect(
            lambda: self.search_requested.emit(self.text())
        )

        self._clear_button.clicked.connect(self.clear)

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._line_edit.setFont(fonts.body())

        self.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {palette.background_secondary};
                color: {palette.text_primary};
                border: 1px solid {palette.border_default};
                border-radius: {Radius.INPUT}px;
                padding: {Spacing.SM}px;
            }}

            QLineEdit:focus {{
                border: 1px solid {palette.border_focus};
            }}

            QPushButton {{
                background-color: {palette.surface_secondary};
                color: {palette.text_primary};
                border: 1px solid {palette.border_default};
                border-radius: {Radius.BUTTON}px;
            }}

            QPushButton:hover {{
                background-color: {palette.surface_hover};
            }}

            QPushButton:pressed {{
                background-color: {palette.surface_pressed};
            }}
            """
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def text(self) -> str:
        return self._line_edit.text()

    def set_text(self, text: str) -> None:
        self._line_edit.setText(text)

    def clear(self) -> None:
        self._line_edit.clear()

    def line_edit(self) -> QLineEdit:
        return self._line_edit