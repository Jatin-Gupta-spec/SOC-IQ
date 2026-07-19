"""
Reusable Threat Intelligence widget for the SOC-IQ desktop application.

This widget displays VirusTotal enrichment results
for a completed investigation.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
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

        self._table = QTableWidget()

        self._table.setColumnCount(3)

        self._table.setHorizontalHeaderLabels(
            [
                "SHA256 Hash",
                "Verdict",
                "Detection Ratio",
            ]
        )

        self._table.verticalHeader().setVisible(
            False,
        )

        self._table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers,
        )

        self._table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows,
        )

        self._table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection,
        )

        self._table.horizontalHeader().setStretchLastSection(
            True,
        )

        self._table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
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
            self._table,
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

        hashes = investigation.threat_intelligence.get(
            "hashes",
            [],
        )

        self._table.setRowCount(
            len(hashes),
        )

        for row, result in enumerate(hashes):

            sha256 = result.get(
                "sha256",
                "Unknown",
            )

            verdict = result.get(
                "verdict",
                "Unknown",
            )

            detection_ratio = result.get(
                "detection_ratio",
                "N/A",
            )

            self._table.setItem(
                row,
                0,
                QTableWidgetItem(
                    str(sha256),
                ),
            )

            self._table.setItem(
                row,
                1,
                QTableWidgetItem(
                    str(verdict),
                ),
            )

            self._table.setItem(
                row,
                2,
                QTableWidgetItem(
                    str(detection_ratio),
                ),
            )

        self._table.resizeColumnsToContents()

    def reset(
        self,
    ) -> None:
        """
        Reset the widget.
        """

        self._table.setRowCount(
            0,
        )