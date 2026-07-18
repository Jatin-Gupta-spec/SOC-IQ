"""
Reusable section header widget for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QLabel,
    QVBoxLayout,
    QWidget,
)


class SectionHeader(QWidget):
    """
    Displays a reusable title and optional description
    for sections within a page.
    """

    def __init__(
        self,
        title: str,
        description: str = "",
    ) -> None:
        super().__init__()

        self._title = QLabel(title)
        self._description = QLabel(description)

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        self._title.setObjectName("sectionHeaderTitle")
        self._description.setObjectName(
            "sectionHeaderDescription"
        )

        self._title.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._description.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        layout = QVBoxLayout()

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        layout.addWidget(self._title)

        if self._description.text():
            layout.addWidget(self._description)

        self.setLayout(layout)