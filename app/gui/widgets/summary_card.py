"""
Reusable summary card widget for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QVBoxLayout,
)


class SummaryCard(QFrame):
    """
    Professional dashboard statistic card.

    Designed to support future extensions such as:
    - icons
    - trends
    - status colors
    - animations
    - sparklines
    """

    def __init__(
        self,
        title: str = "",
        value: str = "",
        subtitle: str = "",
        footer: str = "",
    ) -> None:
        super().__init__()

        self._title_label = QLabel(title)
        self._value_label = QLabel(value)
        self._subtitle_label = QLabel(subtitle)
        self._footer_label = QLabel(footer)

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget.
        """

        self.setObjectName("summaryCard")

        self.setMinimumHeight(180)

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            20,
            20,
            20,
            20,
        )

        layout.setSpacing(10)

        self._title_label.setObjectName(
            "summaryCardTitle"
        )

        self._value_label.setObjectName(
            "summaryCardValue"
        )

        self._subtitle_label.setObjectName(
            "summaryCardSubtitle"
        )

        self._footer_label.setObjectName(
            "summaryCardFooter"
        )

        self._title_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._subtitle_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self._footer_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        layout.addWidget(
            self._title_label
        )

        layout.addStretch()

        layout.addWidget(
            self._value_label
        )

        layout.addWidget(
            self._subtitle_label
        )

        layout.addStretch()

        layout.addWidget(
            self._footer_label
        )

    def set_title(
        self,
        title: str,
    ) -> None:
        self._title_label.setText(title)

    def set_value(
        self,
        value: str,
    ) -> None:
        self._value_label.setText(value)

    def set_subtitle(
        self,
        subtitle: str,
    ) -> None:
        self._subtitle_label.setText(subtitle)

    def set_footer(
        self,
        footer: str,
    ) -> None:
        self._footer_label.setText(footer)

    def update_card(
        self,
        *,
        title: str | None = None,
        value: str | None = None,
        subtitle: str | None = None,
        footer: str | None = None,
    ) -> None:
        """
        Update multiple fields in one call.
        """

        if title is not None:
            self.set_title(title)

        if value is not None:
            self.set_value(value)

        if subtitle is not None:
            self.set_subtitle(subtitle)

        if footer is not None:
            self.set_footer(footer)