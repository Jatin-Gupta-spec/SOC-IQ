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

        self.set_text(
            self.text(),
        )

    def set_text(
        self,
        text: str,
    ) -> None:
        """
        Update badge text and appearance.
        """

        self.setText(
            text.upper(),
        )

        severity = text.upper()

        if severity == "CRITICAL":

            background = "#DC2626"
            foreground = "#FFFFFF"

        elif severity == "HIGH":

            background = "#EA580C"
            foreground = "#FFFFFF"

        elif severity == "MEDIUM":

            background = "#CA8A04"
            foreground = "#FFFFFF"

        elif severity == "LOW":

            background = "#16A34A"
            foreground = "#FFFFFF"

        else:

            background = "#4B5563"
            foreground = "#FFFFFF"

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {background};
                color: {foreground};
                border-radius: 12px;
                padding: 4px 12px;
                font-weight: 700;
            }}
            """
        )