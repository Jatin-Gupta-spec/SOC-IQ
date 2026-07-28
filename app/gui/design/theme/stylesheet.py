"""
SOC-IQ Design System
Global Application Stylesheet

Builds the application's global Qt stylesheet using the
Design System and reusable stylesheet builder.
"""

from __future__ import annotations

from app.gui.design.theme.palette import DEFAULT_PALETTE
from app.gui.design.theme.stylesheet_builder import StylesheetBuilder


class Stylesheet:
    """
    Builds the global application stylesheet.
    """

    def __init__(self) -> None:
        self._builder = StylesheetBuilder(DEFAULT_PALETTE)

    def build(self) -> str:
        """
        Build the complete application stylesheet.
        """

        parts = [
            self._base(),
            self._builder.button_primary(),
            self._builder.line_edit(),
            self._builder.card(),
        ]

        return "\n\n".join(parts)

    def _base(self) -> str:
        """
        Base application styling shared across all widgets.
        """

        palette = DEFAULT_PALETTE

        return f"""
        QWidget {{
            background-color: {palette.background_primary};
            color: {palette.text_primary};
        }}

        QLabel {{
            color: {palette.text_primary};
            background: transparent;
        }}
        """.strip()


DEFAULT_STYLESHEET = Stylesheet()