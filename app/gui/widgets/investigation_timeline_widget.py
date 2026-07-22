"""
Timeline widget for SOC-IQ investigations.
"""

from __future__ import annotations

from datetime import UTC, datetime

from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.database.models import Investigation
from app.gui.widgets.key_value_row import KeyValueRow


class InvestigationTimelineWidget(QWidget):
    """
    Displays timeline information for
    an investigation.
    """

    def __init__(self) -> None:
        super().__init__()

        self._analyzed_at_row = KeyValueRow(
            "Analyzed At",
            "Waiting...",
        )

        self._age_row = KeyValueRow(
            "Age",
            "Waiting...",
        )

        self._status_row = KeyValueRow(
            "Status",
            "Waiting...",
        )

        layout = QVBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.addWidget(
            self._analyzed_at_row,
        )

        layout.addWidget(
            self._age_row,
        )

        layout.addWidget(
            self._status_row,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Load timeline information.
        """

        analyzed = investigation.analyzed_at

        self._analyzed_at_row.set_value(
            analyzed.strftime(
                "%Y-%m-%d %H:%M:%S UTC",
            ),
        )

        delta = (
            datetime.now(UTC)
            - analyzed
        )

        minutes = int(
            delta.total_seconds() // 60
        )

        if minutes < 1:
            age = "Just now"
        elif minutes == 1:
            age = "1 minute ago"
        elif minutes < 60:
            age = f"{minutes} minutes ago"
        else:
            hours = minutes // 60
            age = (
                f"{hours} hour ago"
                if hours == 1
                else f"{hours} hours ago"
            )

        self._age_row.set_value(
            age,
        )

        self._status_row.set_value(
            investigation.status,
        )

    def reset(
        self,
    ) -> None:
        """
        Reset the widget.
        """

        self._analyzed_at_row.set_value(
            "Waiting...",
        )

        self._age_row.set_value(
            "Waiting...",
        )

        self._status_row.set_value(
            "Waiting...",
        )