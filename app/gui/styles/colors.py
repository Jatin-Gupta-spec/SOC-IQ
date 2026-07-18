"""
SOC-IQ color palette.

Centralized color definitions for the application's design system.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ColorPalette:
    """
    Immutable application color palette.
    """

    # Base backgrounds
    WINDOW_BACKGROUND: str = "#1E1E1E"
    SURFACE: str = "#252526"
    SURFACE_HOVER: str = "#2D2D30"
    SURFACE_ACTIVE: str = "#3E3E42"

    # Borders
    BORDER: str = "#3C3C3C"

    # Primary accent
    PRIMARY: str = "#007ACC"
    PRIMARY_HOVER: str = "#2899F5"

    # Semantic colors
    SUCCESS: str = "#16A34A"
    WARNING: str = "#F59E0B"
    DANGER: str = "#DC2626"
    INFO: str = "#38BDF8"

    # Text
    TEXT_PRIMARY: str = "#F3F4F6"
    TEXT_SECONDARY: str = "#A1A1AA"
    TEXT_MUTED: str = "#737373"


COLORS = ColorPalette()