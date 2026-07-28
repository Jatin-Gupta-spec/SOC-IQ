"""
SOC-IQ Design System
Elevation Design Tokens

Defines semantic elevation levels for the application.

Elevation describes visual hierarchy rather than specific shadow
implementations. The actual shadow effects will be created later
by the design effects layer.
"""

from __future__ import annotations


class Elevation:
    """Semantic elevation levels."""

    # Flat surfaces
    NONE = 0

    # Cards placed on the page
    LOW = 1

    # Elevated panels and hover states
    MEDIUM = 2

    # Floating widgets
    HIGH = 3

    # Dialogs
    DIALOG = 4

    # Notifications / popups / tooltips
    OVERLAY = 5


class ZIndex:
    """Logical stacking order."""

    BACKGROUND = 0
    CONTENT = 100
    SIDEBAR = 200
    HEADER = 300
    DROPDOWN = 500
    TOOLTIP = 700
    DIALOG = 900
    NOTIFICATION = 1000