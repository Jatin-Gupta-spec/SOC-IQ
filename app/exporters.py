import csv
import json

from app.config import (
    JSON_EXPORT_FILE,
    CSV_EXPORT_FILE,
)

from app.exceptions import ExportError


def export_to_json(results: dict) -> None:
    """
    Export extracted IOCs to a JSON report.
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

    except (OSError, TypeError, ValueError) as error:

        raise ExportError(
            "Failed to export JSON report."
        ) from error


def export_to_csv(results: dict) -> None:
    """
    Export extracted IOCs to a CSV report.
    """

    try:

        with CSV_EXPORT_FILE.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.writer(file)

            writer.writerow(
                [
                    "IOC Type",
                    "IOC Value",
                ]
            )

            for ioc_type, values in results.items():

                if not values:
                    continue

                for value in values:

                    writer.writerow(
                        [
                            ioc_type,
                            value,
                        ]
                    )

    except (OSError, csv.Error, TypeError, ValueError) as error:

        raise ExportError(
            "Failed to export CSV report."
        ) from error