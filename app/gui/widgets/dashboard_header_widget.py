"""
Reusable dashboard header widget for the SOC-IQ desktop application.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class DashboardHeaderWidget(QWidget):
    """
    Displays the dashboard title together with
    application status information.
    """

    def __init__(self) -> None:
        super().__init__()

        self._title_label = QLabel(
            "SOC-IQ Security Operations Dashboard",
        )

        self._subtitle_label = QLabel(
            "Real-time overview of investigations and threat posture.",
        )

        self._refresh_label = QLabel(
            "Last Refresh: --",
        )

        self._database_label = QLabel(
            "Database: Waiting...",
        )

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Build the widget layout.
        """

        left_layout = QVBoxLayout()

        left_layout.setSpacing(
            4,
        )

        self._title_label.setObjectName(
            "dashboardHeaderTitle",
        )

        self._subtitle_label.setObjectName(
            "dashboardHeaderSubtitle",
        )

        left_layout.addWidget(
            self._title_label,
        )

        left_layout.addWidget(
            self._subtitle_label,
        )

        right_layout = QVBoxLayout()

        right_layout.setSpacing(
            4,
        )

        self._refresh_label.setObjectName(
            "dashboardHeaderInfo",
        )

        self._database_label.setObjectName(
            "dashboardHeaderInfo",
        )

        right_layout.addWidget(
            self._refresh_label,
        )

        right_layout.addWidget(
            self._database_label,
        )

        layout = QHBoxLayout()

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.addLayout(
            left_layout,
        )

        layout.addStretch()

        layout.addLayout(
            right_layout,
        )

        self.setLayout(
            layout,
        )

    def set_last_refresh(
        self,
        timestamp: str,
    ) -> None:
        """
        Update the last refresh timestamp.
        """

        self._refresh_label.setText(
            f"Last Refresh: {timestamp}",
        )

    def set_database_status(
        self,
        status: str,
    ) -> None:
        """
        Update the displayed database status.
        """

        self._database_label.setText(
            f"Database: {status}",
        )