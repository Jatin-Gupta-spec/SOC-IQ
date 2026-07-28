"""
SOC-IQ Design System
Stylesheet Builder

Generates reusable Qt stylesheets from the active theme.
"""

from __future__ import annotations

from app.gui.design.theme.palette import Palette
from app.gui.design.tokens import Radius, Spacing


class StylesheetBuilder:
    """Build reusable Qt stylesheet fragments."""

    def __init__(self, palette: Palette) -> None:
        self._palette = palette

    def button_primary(self) -> str:
        """Primary button stylesheet."""

        return f"""
        QPushButton {{
            background-color: {self._palette.brand_primary};
            color: {self._palette.text_primary};
            border: none;
            border-radius: {Radius.BUTTON}px;
            padding: {Spacing.MD}px {Spacing.LG}px;
        }}

        QPushButton:hover {{
            background-color: {self._palette.brand_hover};
        }}

        QPushButton:pressed {{
            background-color: {self._palette.brand_pressed};
        }}

        QPushButton:disabled {{
            background-color: {self._palette.surface_secondary};
            color: {self._palette.text_disabled};
        }}
        """.strip()

    def card(self) -> str:
        """Modern card stylesheet."""

        return f"""
        QWidget {{
            background-color: {self._palette.surface_primary};
            border: 1px solid {self._palette.border_default};
            border-radius: {Radius.CARD}px;
        }}
        """.strip()

    def line_edit(self) -> str:
        """Standard input stylesheet."""

        return f"""
        QLineEdit {{
            background-color: {self._palette.background_secondary};
            color: {self._palette.text_primary};
            border: 1px solid {self._palette.border_default};
            border-radius: {Radius.INPUT}px;
            padding: {Spacing.SM}px;
        }}

        QLineEdit:focus {{
            border: 1px solid {self._palette.border_focus};
        }}
        """.strip()