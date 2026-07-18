"""
Reusable key/value row widget for the SOC-IQ desktop application.

Displays a descriptive label on the left and a value on the
right. Used throughout the application to present investigation
metadata and system information.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QWidget,
)


class KeyValueRow(QWidget):
    """
    Displays a single key/value pair.
    """

    def __init__(
        self,
        key: str = "",
        value: str = "",
    ) -> None:
        super().__init__()

        self._key_label = QLabel(key)
        self._value_label = QLabel(value)

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        self._key_label.setObjectName(
            "keyValueKey"
        )

        self._value_label.setObjectName(
            "keyValueValue"
        )

        self._key_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft
            | Qt.AlignmentFlag.AlignVCenter
        )

        self._value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
            | Qt.AlignmentFlag.AlignVCenter
        )

        layout = QHBoxLayout()

        layout.setContentsMargins(
            0,
            4,
            0,
            4,
        )

        layout.setSpacing(16)

        layout.addWidget(
            self._key_label
        )

        layout.addStretch()

        layout.addWidget(
            self._value_label
        )

        self.setLayout(layout)

    def set_key(
        self,
        key: str,
    ) -> None:
        """
        Update the key label.
        """

        self._key_label.setText(key)

    def set_value(
        self,
        value: str,
    ) -> None:
        """
        Update the value label.
        """

        self._value_label.setText(value)