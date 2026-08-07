"""
SOC-IQ Design System
Animated Button

Reusable button component for SOC-IQ.
Future versions will support hover, press,
and fade animations.
"""

from __future__ import annotations

from enum import Enum, auto

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QPushButton,
    QHBoxLayout,
    QSizePolicy,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.design.tokens import Radius, Spacing


class ButtonVariant(Enum):
    """
    Visual weight/role of a button.

    PRIMARY   — the one action on a panel the user should take.
    SECONDARY — supporting actions, lower visual weight.
    OUTLINE   — lowest-emphasis actions, transparent fill.
    DANGER    — destructive actions.
    """

    PRIMARY = auto()
    SECONDARY = auto()
    OUTLINE = auto()
    DANGER = auto()


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
        variant: ButtonVariant = ButtonVariant.PRIMARY,
    ) -> None:
        super().__init__(parent)

        self._variant = variant

        self._button = QPushButton(text)

        self._button.clicked.connect(
            self.clicked.emit,
        )

        self._build_ui()
        self.refresh_theme()

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

        self._button.setMinimumHeight(40)

        layout.addWidget(
            self._button,
        )

    def _apply_theme(self) -> None:
        fonts = self.fonts

        self._button.setFont(
            fonts.body(),
        )

        self._button.setStyleSheet(
            self._variant_stylesheet(),
        )

    def _variant_stylesheet(self) -> str:
        """
        Build the QSS for the current variant.

        Kept as a separate method (rather than inline in
        _apply_theme) so set_variant() can restyle without
        duplicating the base layout/font logic.
        """

        palette = self.palette

        base_padding = (
            f"padding: {Spacing.SM}px {Spacing.LG}px;"
        )
        radius = f"border-radius: {Radius.BUTTON}px;"

        if self._variant is ButtonVariant.SECONDARY:
            return f"""
            QPushButton {{
                background-color: {palette.surface_secondary};
                color: {palette.text_primary};
                border: 1px solid {palette.border_default};
                {radius}
                {base_padding}
            }}

            QPushButton:hover {{
                background-color: {palette.surface_elevated};
                border: 1px solid {palette.border_strong};
            }}

            QPushButton:focus {{
                border: 1px solid {palette.border_focus};
            }}

            QPushButton:pressed {{
                background-color: {palette.surface_primary};
            }}

            QPushButton:disabled {{
                background-color: {palette.surface_secondary};
                color: {palette.text_disabled};
                border: 1px solid {palette.border_subtle};
            }}
            """

        if self._variant is ButtonVariant.OUTLINE:
            return f"""
            QPushButton {{
                background-color: transparent;
                color: {palette.text_secondary};
                border: 1px solid {palette.border_default};
                {radius}
                {base_padding}
            }}

            QPushButton:hover {{
                background-color: {palette.surface_secondary};
                color: {palette.text_primary};
                border: 1px solid {palette.border_strong};
            }}

            QPushButton:focus {{
                border: 1px solid {palette.border_focus};
            }}

            QPushButton:pressed {{
                background-color: {palette.surface_elevated};
            }}

            QPushButton:disabled {{
                color: {palette.text_disabled};
                border: 1px solid {palette.border_subtle};
            }}
            """

        if self._variant is ButtonVariant.DANGER:
            return f"""
            QPushButton {{
                background-color: transparent;
                color: {palette.error};
                border: 1px solid {palette.error};
                {radius}
                {base_padding}
            }}

            QPushButton:hover {{
                background-color: {palette.error};
                color: {palette.text_primary};
            }}

            QPushButton:focus {{
                border: 1px solid {palette.border_focus};
            }}

            QPushButton:pressed {{
                background-color: {palette.error};
            }}

            QPushButton:disabled {{
                color: {palette.text_disabled};
                border: 1px solid {palette.border_subtle};
            }}
            """

        # PRIMARY (default) — preserves the original look exactly.
        return f"""
        QPushButton {{
            background-color: {palette.brand_primary};
            color: {palette.text_primary};
            border: none;
            {radius}
            {base_padding}
        }}

        QPushButton:hover {{
            background-color: {palette.brand_hover};
        }}

        QPushButton:focus {{
            border: 1px solid {palette.border_focus};
        }}

        QPushButton:pressed {{
            background-color: {palette.brand_pressed};
        }}

        QPushButton:disabled {{
            background-color: {palette.surface_secondary};
            color: {palette.text_disabled};
        }}
        """

    def refresh_theme(self) -> None:
        """
        Refresh the button theme.
        """

        self._apply_theme()

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

    def set_variant(
        self,
        variant: ButtonVariant,
    ) -> None:
        """
        Change the button's visual weight/role and restyle.
        """
        self._variant = variant
        self.refresh_theme()    

    def variant(self) -> ButtonVariant:
        """Return the current visual variant."""
        return self._variant