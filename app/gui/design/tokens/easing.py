"""
SOC-IQ Design System
Easing Design Tokens

Defines the standard easing curves used by all animations
throughout the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import QEasingCurve


class Easing:
    """Semantic animation easing tokens."""

    # Generic
    LINEAR = QEasingCurve.Type.Linear

    # Natural motion
    IN = QEasingCurve.Type.InOutQuad
    OUT = QEasingCurve.Type.OutQuad
    IN_OUT = QEasingCurve.Type.InOutCubic

    # Semantic aliases
    HOVER = OUT
    BUTTON = OUT
    SIDEBAR = IN_OUT
    PAGE_TRANSITION = IN_OUT
    DIALOG = OUT
    TOOLTIP = OUT
    TOAST = OUT
    CARD_LIFT = OUT
    LOADING = LINEAR