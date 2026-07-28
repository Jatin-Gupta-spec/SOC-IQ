"""
SOC-IQ Design System
Spacing Design Tokens

Defines the standard spacing scale used throughout the application.

All margins, padding and layout spacing should reference these
tokens instead of hard-coded pixel values.
"""

from __future__ import annotations


class Spacing:
    """Semantic spacing tokens (values in pixels)."""

    # Micro spacing
    NONE = 0
    XXS = 2
    XS = 4

    # Standard spacing
    SM = 8
    MD = 12
    LG = 16

    # Large spacing
    XL = 24
    XXL = 32
    XXXL = 48

    # Page layout
    PAGE_MARGIN = 24
    SECTION_GAP = 24
    CARD_PADDING = 16
    PANEL_PADDING = 20

    # Dense data views
    TABLE_CELL_PADDING = 8
    ROW_HEIGHT = 32

    # Forms
    LABEL_GAP = 6
    FIELD_GAP = 12

    # Sidebar
    SIDEBAR_PADDING = 16
    SIDEBAR_ITEM_HEIGHT = 44
    SIDEBAR_ICON_GAP = 12

    # Toolbar
    TOOLBAR_HEIGHT = 52

    # Header
    HEADER_HEIGHT = 64

    # Status bar
    STATUSBAR_HEIGHT = 28