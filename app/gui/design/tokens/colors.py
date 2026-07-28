"""
SOC-IQ Design System
Color Design Tokens

This module defines the semantic color palette used throughout the
SOC-IQ desktop application.

These are design tokens—not widget styles.

Widgets should reference these tokens instead of hard-coded color values.

Example:
    Colors.Background.PRIMARY
    Colors.Text.SECONDARY
    Colors.Status.SUCCESS
"""

from __future__ import annotations


class Colors:
    """Root namespace for all design color tokens."""

    class Background:
        """Application background colors."""

        PRIMARY = "#0F1117"
        SECONDARY = "#151922"
        TERTIARY = "#1B2130"

    class Surface:
        """Cards, panels and elevated containers."""

        PRIMARY = "#171C26"
        SECONDARY = "#1E2431"
        ELEVATED = "#252C3B"

    class Border:
        """Border colors."""

        DEFAULT = "#313949"
        STRONG = "#495365"
        FOCUS = "#4F8CFF"

    class Text:
        """Text colors."""

        PRIMARY = "#F5F7FA"
        SECONDARY = "#C8D0DD"
        MUTED = "#98A2B3"
        DISABLED = "#667085"
        INVERSE = "#111827"

    class Brand:
        """Primary SOC-IQ brand colors."""

        PRIMARY = "#4F8CFF"
        HOVER = "#6BA3FF"
        PRESSED = "#3B74DB"

    class Status:
        """Generic application status colors."""

        SUCCESS = "#22C55E"
        WARNING = "#F59E0B"
        ERROR = "#EF4444"
        INFO = "#38BDF8"

    class Severity:
        """Cybersecurity severity scale."""

        LOW = "#22C55E"
        MEDIUM = "#FACC15"
        HIGH = "#F97316"
        CRITICAL = "#DC2626"

    class Chart:
        """Reserved colors for charts and data visualization."""

        BLUE = "#4F8CFF"
        CYAN = "#38BDF8"
        TEAL = "#14B8A6"
        GREEN = "#22C55E"
        LIME = "#84CC16"
        YELLOW = "#FACC15"
        ORANGE = "#F97316"
        RED = "#EF4444"
        PINK = "#EC4899"
        PURPLE = "#8B5CF6"

    class Interactive:
        """Interactive state colors."""

        HOVER = "#212938"
        PRESSED = "#2A3446"
        SELECTED = "#314A7F"

    class Overlay:
        """Overlay colors."""

        MODAL = "#00000099"
        SELECTION = "#4F8CFF33"