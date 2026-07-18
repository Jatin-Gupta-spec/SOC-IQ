"""
Reusable page container for the SOC-IQ desktop application.

Every page in the application should be wrapped inside a
PageContainer to ensure a consistent layout and appearance.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class PageContainer(QFrame):
    """
    Standard container used by all application pages.
    """

    def __init__(
        self,
        title: str = "",
        description: str = "",
    ) -> None:
        super().__init__()

        self._title_label = QLabel(title)
        self._description_label = QLabel(description)

        self._content_widget = QWidget()
        self._content_layout = QVBoxLayout()

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the page layout.
        """

        self.setObjectName("pageContainer")

        self._title_label.setObjectName("pageTitle")

        self._description_label.setObjectName(
            "pageDescription"
        )

        self._title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        self._description_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        self._content_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self._content_layout.setSpacing(16)

        self._content_widget.setLayout(
            self._content_layout
        )

        layout = QVBoxLayout()

        layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )

        layout.setSpacing(16)

        layout.addWidget(self._title_label)

        layout.addWidget(self._description_label)

        layout.addWidget(self._content_widget)

        self.setLayout(layout)

    def set_title(
        self,
        title: str,
    ) -> None:
        """
        Update the page title.
        """

        self._title_label.setText(title)

    def set_description(
        self,
        description: str,
    ) -> None:
        """
        Update the page description.
        """

        self._description_label.setText(
            description
        )

    def content_layout(self) -> QVBoxLayout:
        """
        Return the layout used for page content.
        """

        return self._content_layout