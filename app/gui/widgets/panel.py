"""
Reusable panel widget for the SOC-IQ desktop application.

Panels provide a consistent visual container for sections
throughout the application.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QWidget,
)

from app.gui.design.tokens import Spacing


class Panel(QFrame):
    """
    Reusable container used throughout the GUI.
    """

    def __init__(self) -> None:
        super().__init__()

        self._content_layout = QVBoxLayout()

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the panel.
        """

        self.setObjectName("panel")

        layout = QVBoxLayout()

        layout.setContentsMargins(
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
            Spacing.LG,
        )

        layout.setSpacing(Spacing.MD)

        self._content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        # 10px has no exact match in the Spacing scale (SM=8,
        # MD=12) — left as a literal per the audit finding rather
        # than rounding to a token that doesn't represent it.
        self._content_layout.setSpacing(10)

        layout.addLayout(
            self._content_layout,
        )

        self.setLayout(
            layout,
        )

    def content_layout(self) -> QVBoxLayout:
        """
        Return the layout used to place widgets inside
        the panel.
        """

        return self._content_layout

    def add_widget(
        self,
        widget: QWidget,
    ) -> None:
        """
        Add a widget to the panel.
        """

        self._content_layout.addWidget(
            widget,
        )