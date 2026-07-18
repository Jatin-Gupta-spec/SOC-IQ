"""
Reusable detail section widget for the SOC-IQ desktop application.

A DetailSection combines a section header with a reusable panel
that contains arbitrary widgets.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.gui.widgets.panel import Panel
from app.gui.widgets.section_header import SectionHeader


class DetailSection(QWidget):
    """
    Reusable titled section used throughout the application.
    """

    def __init__(
        self,
        title: str,
        description: str = "",
    ) -> None:
        super().__init__()

        self._header = SectionHeader(
            title,
            description,
        )

        self._panel = Panel()

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(10)

        layout.addWidget(
            self._header
        )

        layout.addWidget(
            self._panel
        )

        self.setLayout(layout)

    def content_layout(self):
        """
        Return the panel's content layout.
        """

        return self._panel.content_layout()

    def add_widget(
        self,
        widget: QWidget,
    ) -> None:
        """
        Add a widget to the section.
        """

        self._panel.add_widget(
            widget
        )