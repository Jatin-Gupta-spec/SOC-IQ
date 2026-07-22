"""
Reusable Risk Summary widget for the SOC-IQ desktop application.

This widget displays the calculated risk score
for a completed investigation.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from app.database.models import Investigation
from app.gui.widgets.key_value_row import KeyValueRow


class RiskSummaryWidget(QWidget):
    """
    Displays the investigation risk summary.
    """

    def __init__(self) -> None:
        super().__init__()

        self._risk_score_row = KeyValueRow(
            "Risk Score",
            "Waiting...",
        )

        self._severity_row = KeyValueRow(
            "Severity",
            "Waiting...",
        )

        self._confidence_row = KeyValueRow(
            "Confidence",
            "Waiting...",
        )

        self._ioc_score_row = KeyValueRow(
            "IOC Score",
            "Waiting...",
        )

        self._threat_score_row = KeyValueRow(
            "Threat Intelligence",
            "Waiting...",
        )

        self._cve_score_row = KeyValueRow(
            "CVE Score",
            "Waiting...",
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
            self._risk_score_row,
        )

        layout.addWidget(
            self._severity_row,
        )

        layout.addWidget(
            self._confidence_row,
        )

        layout.addWidget(
            self._ioc_score_row,
        )

        layout.addWidget(
            self._threat_score_row,
        )

        layout.addWidget(
            self._cve_score_row,
        )

        self.setLayout(
            layout,
        )

    def load_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Display the investigation risk summary.
        """

        self._risk_score_row.set_value(
            str(
                investigation.risk_score,
            )
        )

        self._severity_row.set_value(
            investigation.severity,
        )

        self._confidence_row.set_value(
            f"{investigation.confidence * 100:.0f}%",
        )

        self._ioc_score_row.set_value(
            str(
                investigation.ioc_score,
            ),
        )

        self._threat_score_row.set_value(
            str(
                investigation.threat_intel_score,
            ),
        )

        self._cve_score_row.set_value(
            str(
                investigation.cve_score,
            ),
        )

    def reset(self) -> None:
        """
        Reset the widget.
        """

        self._risk_score_row.set_value(
            "Waiting...",
        )

        self._severity_row.set_value(
            "Waiting...",
        )

        self._confidence_row.set_value(
            "Waiting...",
        )

        self._ioc_score_row.set_value(
            "Waiting...",
        )

        self._threat_score_row.set_value(
            "Waiting...",
        )

        self._cve_score_row.set_value(
            "Waiting...",
        )