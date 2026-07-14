import csv
import json

from app.config import (
    JSON_EXPORT_FILE,
    CSV_EXPORT_FILE,
)

from app.exceptions import ExportError


def export_to_json(results: dict) -> None:
    """
    Export analysis results to a JSON report.

    Supports:
    - IOC extraction results
    - Threat intelligence enrichment results
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


def export_to_csv(results: dict) -> None:
    """
    Export IOC and threat intelligence results
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
            # IOC Export Section
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
            # Threat Intelligence Section
            # --------------------------------

            threat_intelligence = results.get(
                "threat_intelligence",
                {},
            )

            hash_results = threat_intelligence.get(
                "hashes",
                [],
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

    except (
        OSError,
        csv.Error,
        TypeError,
        ValueError,
    ) as error:

        raise ExportError(
            "Failed to export CSV report."
        ) from error