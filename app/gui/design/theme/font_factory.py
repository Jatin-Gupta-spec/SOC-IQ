"""
SOC-IQ Design System
Font Factory

Centralized creation and caching of QFont instances.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtGui import QFont

from app.gui.design.tokens import Typography, TextStyle


class FontFactory:
    """
    Factory responsible for creating QFont objects
    from typography design tokens.
    """

    @staticmethod
    @lru_cache(maxsize=None)
    def create(style: TextStyle) -> QFont:
        """
        Create and cache a QFont from a TextStyle.
        """

        font = QFont(style.family)
        font.setPointSize(style.size)
        font.setWeight(QFont.Weight(style.weight))

        # Future typography options
        # font.setKerning(True)
        # font.setHintingPreference(...)

        return font

    @classmethod
    def display(cls) -> QFont:
        return cls.create(Typography.DISPLAY)

    @classmethod
    def heading(cls) -> QFont:
        return cls.create(Typography.HEADING)

    @classmethod
    def title(cls) -> QFont:
        return cls.create(Typography.TITLE)

    @classmethod
    def subtitle(cls) -> QFont:
        return cls.create(Typography.SUBTITLE)

    @classmethod
    def body(cls) -> QFont:
        return cls.create(Typography.BODY)

    @classmethod
    def body_small(cls) -> QFont:
        return cls.create(Typography.BODY_SMALL)

    @classmethod
    def label(cls) -> QFont:
        return cls.create(Typography.LABEL)

    @classmethod
    def caption(cls) -> QFont:
        return cls.create(Typography.CAPTION)

    @classmethod
    def code(cls) -> QFont:
        return cls.create(Typography.CODE)