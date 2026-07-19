"""
CSV export utility for the SOC-IQ desktop application.
"""

from __future__ import annotations

import csv
from pathlib import Path

from app.database.models import Investigation


def export_investigations_to_csv(
    investigations: list[Investigation],
    file_path: str,
) -> None:
    """
    Export investigations to a CSV file.
    """

    path = Path(file_path)

    with path.open(
        mode="w",
        newline="",
        encoding="utf-8",
    ) as csv_file:

        writer = csv.writer(csv_file)

        writer.writerow(
            [
                "Investigation ID",
                "Report Name",
                "Severity",
                "Risk Score",
                "Status",
                "Analyzed At",
            ]
        )

        for investigation in investigations:

            writer.writerow(
                [
                    investigation.investigation_id,
                    investigation.report_name,
                    investigation.severity,
                    investigation.risk_score,
                    investigation.status,
                    investigation.analyzed_at.strftime(
                        "%Y-%m-%d %H:%M:%S UTC",
                    ),
                ]
            )