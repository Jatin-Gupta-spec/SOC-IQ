"""
SOC-IQ Design System
Theme Manager

Central access point for the SOC-IQ design system.

The ThemeManager coordinates palettes, typography,
stylesheets and future theme switching.
"""

from __future__ import annotations

from app.gui.design.theme.palette import DEFAULT_PALETTE, Palette
from app.gui.design.theme.font_factory import FontFactory


class ThemeManager:
    """Central manager for application themes."""

    def __init__(self) -> None:
        self._palette: Palette = DEFAULT_PALETTE

    @property
    def palette(self) -> Palette:
        """Return the active application palette."""
        return self._palette

    def set_palette(self, palette: Palette) -> None:
        """
        Replace the active palette.

        This prepares the design system for future
        light themes, accessibility themes and
        user-defined themes.
        """
        self._palette = palette

    @property
    def fonts(self) -> FontFactory:
        """Return the application font factory."""
        return FontFactory


theme_manager = ThemeManager()