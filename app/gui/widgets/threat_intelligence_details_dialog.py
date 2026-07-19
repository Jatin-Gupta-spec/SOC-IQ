"""
Threat Intelligence Details dialog.

Displays the complete threat intelligence
information for a selected hash.
"""

from __future__ import annotations

from pprint import pformat

from PySide6.QtWidgets import (
    QDialog,
    QPlainTextEdit,
    QVBoxLayout,
)


class ThreatIntelligenceDetailsDialog(QDialog):
    """
    Displays complete threat intelligence
    information.
    """

    def __init__(
        self,
        title: str,
        data: dict,
    ) -> None:
        super().__init__()

        self.setWindowTitle(title)

        self.resize(
            800,
            600,
        )

        self._content = QPlainTextEdit()

        self._content.setReadOnly(True)

        self._content.setPlainText(
            pformat(
                data,
                indent=4,
                width=120,
            )
        )

        layout = QVBoxLayout()

        layout.addWidget(
            self._content,
        )

        self.setLayout(
            layout,
        )