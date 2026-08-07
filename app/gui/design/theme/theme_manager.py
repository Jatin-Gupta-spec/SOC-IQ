"""
SOC-IQ Design System
Theme Manager

Central access point for the SOC-IQ design system.

The ThemeManager coordinates palettes, typography,
stylesheets and future theme switching.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from app.gui.design.theme.palette import DEFAULT_PALETTE, Palette
from app.gui.design.theme.font_factory import FontFactory


class ThemeManager(QObject):
    """Central manager for application themes."""

    # Emitted whenever the active palette changes. Widgets that
    # cache palette-derived stylesheets (ModernCard and subclasses)
    # should connect to this and call their own refresh_theme() so
    # runtime theme switching doesn't leave already-built widgets
    # showing stale colors.
    palette_changed = Signal()

    def __init__(self) -> None:
        super().__init__()

        self._palette: Palette = DEFAULT_PALETTE
        self._fonts = FontFactory

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

        if palette is self._palette:
            return

        self._palette = palette
        self.palette_changed.emit()

    @property
    def fonts(self) -> FontFactory:
        """Return the application font factory."""
        return self._fonts


theme_manager = ThemeManager()