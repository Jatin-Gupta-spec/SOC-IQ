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
            border: 1px solid transparent;
            border-radius: {Radius.BUTTON}px;
            padding: {Spacing.MD}px {Spacing.LG}px;
        }}

        QPushButton:hover {{
            background-color: {self._palette.brand_hover};
            border: 1px solid {self._palette.border_default};
        }}

        QPushButton:pressed {{
            background-color: {self._palette.brand_pressed};
        }}

        QPushButton:disabled {{
            background-color: {self._palette.surface_secondary};
            color: {self._palette.text_disabled};
            border: 1px solid transparent;
        }}
        """.strip()

    def card(self) -> str:
        """
        Legacy card stylesheet fragment.

        Scoped to QFrame#legacyCard rather than a bare QWidget
        selector. The previous unscoped `QWidget { ... }` rule
        applied a card border/background to every widget in the
        application when included in the global stylesheet —
        fighting ModernCard's own QFrame#modernCard styling.
        ModernCard now owns its own styling directly, so this
        fragment is kept only for any legacy direct consumer
        that opts in via the "legacyCard" object name.
        """

        return f"""
        QFrame#legacyCard {{
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

        QLineEdit:hover {{
            border: 1px solid {self._palette.border_strong};
        }}

        QLineEdit:focus {{
            border: 1px solid {self._palette.border_focus};
        }}
        """.strip()