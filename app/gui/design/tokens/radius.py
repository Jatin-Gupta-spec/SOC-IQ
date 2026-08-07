"""
SOC-IQ Design System
Radius Design Tokens

Defines the standard corner radius values used throughout the
SOC-IQ desktop application.

All widgets should reference these tokens instead of hard-coded
border-radius values.
"""

from __future__ import annotations


class Radius:
    """Semantic corner radius tokens (values in pixels)."""

    # No rounding
    NONE = 0

    # Small UI elements
    XS = 2
    SM = 4

    # Standard controls
    MD = 6

    # Cards and panels
    LG = 8

    # Dialogs and floating containers
    XL = 12

    # Large decorative surfaces (use sparingly)
    XXL = 16

    # Circular elements
    CIRCLE = 999

    # Semantic aliases
    BUTTON = MD
    INPUT = MD
    BADGE = SM
    CHIP = XL
    CARD = LG
    PANEL = LG
    DIALOG = XL
    TOOLTIP = SM