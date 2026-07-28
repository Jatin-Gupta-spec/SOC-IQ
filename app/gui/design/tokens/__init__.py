"""
SOC-IQ Design System

Public API for all design tokens.

This package provides the single import location for the
SOC-IQ design language.
"""

from .colors import Colors
from .typography import (
    Typography,
    FontFamily,
    FontWeight,
    FontSize,
    LineHeight,
    TextStyle,
)
from .spacing import Spacing
from .radius import Radius
from .elevation import Elevation, ZIndex
from .opacity import Opacity
from .duration import Duration
from .easing import Easing

__all__ = [
    "Colors",
    "Typography",
    "FontFamily",
    "FontWeight",
    "FontSize",
    "LineHeight",
    "TextStyle",
    "Spacing",
    "Radius",
    "Elevation",
    "ZIndex",
    "Opacity",
    "Duration",
    "Easing",
]