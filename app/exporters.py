import csv
import json

from app.config import (
    JSON_EXPORT_FILE,
    CSV_EXPORT_FILE,
)


def export_to_json(results):
    """
    Export extracted IOCs to a JSON report.
    """

    with JSON_EXPORT_FILE.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            results,
            file,
            indent=4,
        )


def export_to_csv(results):
    """
    Export extracted IOCs to a CSV report.
    """

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

            for value in values:

                writer.writerow(
                    [
                        ioc_type,
                        value,
                    ]
                )