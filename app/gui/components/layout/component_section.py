"""
SOC-IQ Design System

Component Section

Reusable section container for the Design System showcase.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.gui.components.base_widget import BaseWidget
from app.gui.components.layout.section_header import SectionHeader
from app.gui.design.tokens import Spacing


class ComponentSection(BaseWidget):
    """
    Reusable section inside the Design System gallery.

    Example:

        Cards
        ----------------

        [ Card ]
        [ Card ]

        Buttons
        ----------------

        [ Button ]
        [ Button ]
    """

    def __init__(
        self,
        title: str,
        description: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._header = SectionHeader(
            title,
            description,
        )

        self._layout = QVBoxLayout(self)

        self._layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._layout.setSpacing(
            Spacing.LG,
        )

        self._layout.addWidget(
            self._header,
        )

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def add_widget(
        self,
        widget: QWidget,
    ) -> None:
        self._layout.addWidget(widget)

    def add_layout(
        self,
        layout,
    ) -> None:
        self._layout.addLayout(layout)