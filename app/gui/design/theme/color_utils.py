"""
SOC-IQ Design System
Color Utilities

Utility functions for working with colors throughout the
SOC-IQ Theme Engine.
"""

from __future__ import annotations

from PySide6.QtGui import QColor


class ColorUtils:
    """Utility methods for QColor operations."""

    @staticmethod
    def from_hex(value: str) -> QColor:
        """Create a QColor from a hex string."""
        return QColor(value)

    @staticmethod
    def to_hex(color: QColor) -> str:
        """Convert a QColor to a hex string."""
        return color.name()

    @staticmethod
    def with_alpha(color: QColor, alpha: int) -> QColor:
        """
        Return a copy of the color with the specified alpha.
        Alpha must be between 0 and 255.
        """
        alpha = max(0, min(255, alpha))
        new_color = QColor(color)
        new_color.setAlpha(alpha)
        return new_color

    @staticmethod
    def lighter(color: QColor, factor: int = 110) -> QColor:
        """
        Return a lighter version of the color.
        100 = unchanged.
        """
        return color.lighter(factor)

    @staticmethod
    def darker(color: QColor, factor: int = 110) -> QColor:
        """
        Return a darker version of the color.
        100 = unchanged.
        """
        return color.darker(factor)

    @staticmethod
    def is_valid(value: str) -> bool:
        """Return True if the string is a valid color."""
        return QColor(value).isValid()