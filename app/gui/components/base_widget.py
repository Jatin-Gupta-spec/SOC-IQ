"""
SOC-IQ Design System
Base Widget

Base class for reusable SOC-IQ widgets.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget

from app.gui.design.theme.theme_manager import theme_manager


class BaseWidget(QWidget):
    """
    Base class for all custom SOC-IQ widgets.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._theme = theme_manager

    @property
    def theme(self):
        """Return the active theme manager."""
        return self._theme

    @property
    def palette(self):
        """Return the active application palette."""
        return self._theme.palette

    @property
    def fonts(self):
        """Return the application font factory."""
        return self._theme.fonts

    def refresh_theme(self) -> None:
        """
        Refresh the widget after a theme change.

        Subclasses may override this to reapply colors,
        fonts or styles when the active theme changes.
        """

        return