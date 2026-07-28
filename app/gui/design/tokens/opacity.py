"""
SOC-IQ Design System
Opacity Design Tokens

Defines standard opacity values used throughout the application.

These tokens provide consistent transparency for interactive
states, overlays and visual effects.
"""

from __future__ import annotations


class Opacity:
    """Semantic opacity tokens."""

    # Fully transparent
    TRANSPARENT = 0.0

    # Barely visible
    SUBTLE = 0.10

    # Hover overlays
    HOVER = 0.15

    # Selection overlays
    SELECTED = 0.20

    # Disabled widgets
    DISABLED = 0.40

    # Secondary emphasis
    MUTED = 0.60

    # Strong overlays
    OVERLAY = 0.75

    # Fully opaque
    OPAQUE = 1.0