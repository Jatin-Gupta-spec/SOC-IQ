"""
Reusable badge widget for the SOC-IQ desktop application.

Badges provide a consistent way to display
status, severity, and other short values.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class Badge(QLabel):
    """
    Reusable badge widget.
    """

    def __init__(
        self,
        text: str = "",
    ) -> None:
        super().__init__(text)

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Configure the widget.
        """

        self.setObjectName("badge")

        self.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.setMinimumHeight(28)

        self.setMinimumWidth(80)

    def set_text(
        self,
        text: str,
    ) -> None:
        """
        Update badge text.
        """

        self.setText(text)