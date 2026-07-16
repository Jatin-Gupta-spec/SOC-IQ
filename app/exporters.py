import csv
import json

from app.config import (
    CSV_EXPORT_FILE,
    JSON_EXPORT_FILE,
)
from app.exceptions import ExportError


def export_to_json(
    results: dict,
) -> None:
    """
    Export complete analysis results
    to a JSON report.
    """

    try:

        with JSON_EXPORT_FILE.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                results,
                file,
                indent=4,
            )

    except (
        OSError,
        TypeError,
        ValueError,
    ) as error:

        raise ExportError(
            "Failed to export JSON report."
        ) from error


def export_to_csv(
    results: dict,
) -> None:
    """
    Export complete analysis results
    to a CSV report.
    """

    try:

        with CSV_EXPORT_FILE.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)

            # --------------------------------
            # IOC Section
            # --------------------------------

            iocs = results.get(
                "iocs",
                results,
            )

            writer.writerow(
                [
                    "IOC Type",
                    "IOC Value",
                ]
            )

            for ioc_type, values in iocs.items():

                if not values:
                    continue

                for value in values:

                    writer.writerow(
                        [
                            ioc_type,
                            value,
                        ]
                    )

            # --------------------------------
            # Threat Intelligence
            # --------------------------------

            threat_intelligence = results.get(
                "threat_intelligence",
                {},
            )

            hash_results = (
                threat_intelligence.get(
                    "hashes",
                    [],
                )
            )

            if hash_results:

                writer.writerow([])

                writer.writerow(
                    [
                        "Threat Intelligence",
                    ]
                )

                writer.writerow(
                    [
                        "SHA256",
                        "Malicious",
                        "Suspicious",
                        "Harmless",
                    ]
                )

                for result in hash_results:

                    writer.writerow(
                        [
                            result.get(
                                "sha256",
                                "-",
                            ),
                            result.get(
                                "malicious",
                                "-",
                            ),
                            result.get(
                                "suspicious",
                                "-",
                            ),
                            result.get(
                                "harmless",
                                "-",
                            ),
                        ]
                    )

            # --------------------------------
            # Risk Summary
            # --------------------------------

            risk = results.get(
                "risk",
            )

            if risk:

                writer.writerow([])

                writer.writerow(
                    [
                        "Risk Summary",
                    ]
                )

                writer.writerow(
                    [
                        "Metric",
                        "Value",
                    ]
                )

                writer.writerow(
                    [
                        "Risk Score",
                        risk.get(
                            "score",
                            "-",
                        ),
                    ]
                )

                writer.writerow(
                    [
                        "Severity",
                        risk.get(
                            "severity",
                            "-",
                        ),
                    ]
                )

                writer.writerow(
                    [
                        "Confidence",
                        risk.get(
                            "confidence",
                            "-",
                        ),
                    ]
                )

                writer.writerow(
                    [
                        "IOC Score",
                        risk.get(
                            "ioc_score",
                            "-",
                        ),
                    ]
                )

                writer.writerow(
                    [
                        "Threat Intelligence Score",
                        risk.get(
                            "threat_intel_score",
                            "-",
                        ),
                    ]
                )

                writer.writerow(
                    [
                        "CVE Score",
                        risk.get(
                            "cve_score",
                            "-",
                        ),
                    ]
                )

    except (
        OSError,
        csv.Error,
        TypeError,
        ValueError,
    ) as error:

        raise ExportError(
            "Failed to export CSV report."
        ) from error