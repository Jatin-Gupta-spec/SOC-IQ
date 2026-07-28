"""
SOC-IQ Design System
Typography Design Tokens
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TextStyle:
    """Immutable typography style."""

    family: str
    size: int
    weight: int


class FontFamily:
    PRIMARY = "Segoe UI"
    MONOSPACE = "JetBrains Mono"


class FontWeight:
    LIGHT = 300
    REGULAR = 400
    MEDIUM = 500
    SEMIBOLD = 600
    BOLD = 700


class FontSize:
    DISPLAY = 28
    HEADING = 22
    TITLE = 18
    SUBTITLE = 16
    BODY = 11
    BODY_SMALL = 10
    LABEL = 10
    CAPTION = 9
    CODE = 10


class LineHeight:
    TIGHT = 1.1
    NORMAL = 1.3
    RELAXED = 1.5


class Typography:
    """Semantic typography tokens."""

    DISPLAY = TextStyle(
        FontFamily.PRIMARY,
        FontSize.DISPLAY,
        FontWeight.BOLD,
    )

    HEADING = TextStyle(
        FontFamily.PRIMARY,
        FontSize.HEADING,
        FontWeight.SEMIBOLD,
    )

    TITLE = TextStyle(
        FontFamily.PRIMARY,
        FontSize.TITLE,
        FontWeight.SEMIBOLD,
    )

    SUBTITLE = TextStyle(
        FontFamily.PRIMARY,
        FontSize.SUBTITLE,
        FontWeight.MEDIUM,
    )

    BODY = TextStyle(
        FontFamily.PRIMARY,
        FontSize.BODY,
        FontWeight.REGULAR,
    )

    BODY_SMALL = TextStyle(
        FontFamily.PRIMARY,
        FontSize.BODY_SMALL,
        FontWeight.REGULAR,
    )

    LABEL = TextStyle(
        FontFamily.PRIMARY,
        FontSize.LABEL,
        FontWeight.MEDIUM,
    )

    CAPTION = TextStyle(
        FontFamily.PRIMARY,
        FontSize.CAPTION,
        FontWeight.REGULAR,
    )

    CODE = TextStyle(
        FontFamily.MONOSPACE,
        FontSize.CODE,
        FontWeight.REGULAR,
    )