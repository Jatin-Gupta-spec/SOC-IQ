"""
SOC-IQ Design System
Theme Palette

Maps semantic design tokens into a reusable application palette.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.gui.design.tokens import Colors


@dataclass(frozen=True)
class Palette:
    """Semantic application color palette."""

    # --------------------------------------------------
    # Backgrounds
    # --------------------------------------------------

    background_primary: str = Colors.Background.PRIMARY
    background_secondary: str = Colors.Background.SECONDARY
    background_tertiary: str = Colors.Background.TERTIARY

    # --------------------------------------------------
    # Surfaces
    # --------------------------------------------------

    surface_primary: str = Colors.Surface.PRIMARY
    surface_secondary: str = Colors.Surface.SECONDARY
    surface_elevated: str = Colors.Surface.ELEVATED

    # --------------------------------------------------
    # Borders
    # --------------------------------------------------

    border_subtle: str = Colors.Border.SUBTLE
    border_default: str = Colors.Border.DEFAULT
    border_strong: str = Colors.Border.STRONG
    border_focus: str = Colors.Border.FOCUS

    # --------------------------------------------------
    # Text
    # --------------------------------------------------

    text_primary: str = Colors.Text.PRIMARY
    text_secondary: str = Colors.Text.SECONDARY
    text_muted: str = Colors.Text.MUTED
    text_disabled: str = Colors.Text.DISABLED

    # --------------------------------------------------
    # Brand
    # --------------------------------------------------

    brand_primary: str = Colors.Brand.PRIMARY
    brand_hover: str = Colors.Brand.HOVER
    brand_pressed: str = Colors.Brand.PRESSED

    # --------------------------------------------------
    # Accent
    # (Alias for dashboard and future UI components)
    # --------------------------------------------------

    accent: str = Colors.Brand.PRIMARY
    accent_hover: str = Colors.Brand.HOVER
    accent_pressed: str = Colors.Brand.PRESSED

    # --------------------------------------------------
    # Status
    # --------------------------------------------------

    success: str = Colors.Status.SUCCESS
    warning: str = Colors.Status.WARNING
    error: str = Colors.Status.ERROR
    info: str = Colors.Status.INFO

    # --------------------------------------------------
    # Severity
    # --------------------------------------------------

    severity_low: str = Colors.Severity.LOW
    severity_medium: str = Colors.Severity.MEDIUM
    severity_high: str = Colors.Severity.HIGH
    severity_critical: str = Colors.Severity.CRITICAL


DEFAULT_PALETTE = Palette()