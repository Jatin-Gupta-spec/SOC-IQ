"""
SOC-IQ Design System
Animated Button

Reusable button component for SOC-IQ.
Future versions will support hover, press,
and fade animations.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class AnimatedButton(BaseWidget):
    """
    Reusable themed button.

    Version 1 provides a stable API and
    theme integration. Animations will be
    introduced in Version 2.
    """

    clicked = Signal()

    def __init__(
        self,
        text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._button = QPushButton(text)

        self._button.clicked.connect(
            self.clicked.emit,
        )

        self._build_ui()
        self._apply_theme()

    # --------------------------------------------------
    # UI
    # --------------------------------------------------

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(0)

        self._button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        layout.addWidget(
            self._button,
        )

    def _apply_theme(self) -> None:
        palette = self.theme.palette
        fonts = self.theme.fonts

        self._button.setFont(
            fonts.body(),
        )

        self._button.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {palette.brand_primary};
                color: {palette.text_primary};
                border: none;
                border-radius: {Radius.BUTTON}px;
                padding: {Spacing.SM}px {Spacing.LG}px;
            }}

            QPushButton:hover {{
                background-color: {palette.brand_hover};
            }}

            QPushButton:pressed {{
                background-color: {palette.brand_pressed};
            }}

            QPushButton:disabled {{
                background-color: {palette.surface_secondary};
                color: {palette.text_disabled};
            }}
            """
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def button(self) -> QPushButton:
        """
        Return the internal QPushButton.

        This method is retained for backward
        compatibility, but new code should
        prefer using the AnimatedButton
        directly via its public API.
        """
        return self._button

    def set_text(
        self,
        text: str,
    ) -> None:
        """Update the button text."""
        self._button.setText(text)

    def text(self) -> str:
        """Return the current button text."""
        return self._button.text()

    def set_enabled(
        self,
        enabled: bool,
    ) -> None:
        """Enable or disable the button."""
        self._button.setEnabled(enabled)

    def is_enabled(self) -> bool:
        """Return whether the button is enabled."""
        return self._button.isEnabled()

    def click(self) -> None:
        """
        Programmatically click the button.
        """
        self._button.click()

    def set_tooltip(
        self,
        text: str,
    ) -> None:
        """Set the button tooltip."""
        self._button.setToolTip(text)

    def set_icon(
        self,
        icon,
    ) -> None:
        """Set the button icon."""
        self._button.setIcon(icon)