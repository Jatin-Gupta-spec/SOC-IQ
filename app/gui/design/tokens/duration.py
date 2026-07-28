"""
SOC-IQ Design System
Duration Design Tokens

Defines standard animation durations used throughout
the SOC-IQ desktop application.

All animations should reference these tokens instead of
hard-coded millisecond values.
"""

from __future__ import annotations


class Duration:
    """Animation durations in milliseconds."""

    # Instant state changes
    INSTANT = 0

    # Micro interactions
    FASTEST = 100
    FASTER = 150

    # Standard UI animations
    FAST = 200
    NORMAL = 250
    SLOW = 350

    # Large transitions
    SLOWER = 500
    SLOWEST = 750

    # Semantic aliases

    HOVER = FAST
    BUTTON_PRESS = FASTER
    TOOLTIP = FAST
    SIDEBAR = NORMAL
    CARD_LIFT = NORMAL
    PAGE_TRANSITION = SLOW
    DIALOG = SLOW
    TOAST = SLOWER
    LOADING = SLOWEST