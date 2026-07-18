"""
Reusable Threat Intelligence widget for the SOC-IQ desktop application.

This widget displays VirusTotal enrichment results
for a completed investigation.
"""

from __future__ import annotations

from pprint import pformat

from PySide6.QtWidgets import (
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation


class ThreatIntelligenceWidget(QWidget):
    """
    Displays Threat Intelligence information.
    """

    def __init__(self) -> None:
        super().__init__()

        self._content = QPlainTextEdit()

        self._content.setReadOnly(True)

        self._content.setPlainText(
            "Waiting for investigation..."
        )

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        layout = QVBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.addWidget(
            self._content,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display threat intelligence for an investigation.
        """

        self._content.setPlainText(
            pformat(
                investigation.threat_intelligence,
                indent=4,
                width=100,
            )
        )

    def reset(
        self,
    ) -> None:
        """
        Reset the widget.
        """

        self._content.setPlainText(
            "Waiting for investigation..."
        )