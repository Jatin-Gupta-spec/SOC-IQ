"""
Export controller for the SOC-IQ desktop application.

This controller coordinates exporting investigations
from the GUI.
"""

from __future__ import annotations

from pathlib import Path

from app.database.models import Investigation

from PySide6.QtWidgets import (
    QFileDialog,
    QMessageBox,
)

from app.exporters import (
    export_to_csv,
    export_to_json,
)

from app.exceptions import ExportError


class ExportController:
    """
    Coordinates investigation export operations.
    """

    def __init__(
        self,
    ) -> None:
        """
        Initialize the export controller.
        """

    def export_investigation(
        self,
        investigation: Investigation,
    ) -> None:
        """
        Export an investigation.

        This method will later display the export
        dialog and coordinate the export process.
        """

        file_path, selected_filter = QFileDialog.getSaveFileName(
            None,
            "Export Investigation",
            f"{investigation.report_name}.json",
            (
                "JSON Report (*.json);;"
                "CSV Report (*.csv);;"
                "HTML Report (*.html)"
            ),
        )

        if not file_path:
            return

        results = {
            "iocs": investigation.iocs,
            "threat_intelligence": investigation.threat_intelligence,
            "risk": {
                "score": investigation.risk_score,
                "severity": investigation.severity,
                "confidence": investigation.confidence,
                "ioc_score": investigation.ioc_score,
                "threat_intel_score": (
                    investigation.threat_intel_score
                ),
                "cve_score": investigation.cve_score,
            },
        }

        destination = Path(
            file_path,
        )

        try:

            if selected_filter.startswith(
                "JSON",
            ):

                export_to_json(
                    results,
                    destination,
                )

            elif selected_filter.startswith(
                "CSV",
            ):

                export_to_csv(
                    results,
                    destination,
                )

            else:

                QMessageBox.information(
                    None,
                    "Coming Soon",
                    (
                        "HTML export will be "
                        "implemented in a later sprint."
                    ),
                )

                return

        except ExportError as error:

            QMessageBox.critical(
                None,
                "Export Failed",
                str(error),
            )

            return

        QMessageBox.information(
            None,
            "Export Successful",
            (
                "The investigation was exported "
                "successfully."
            ),
        )