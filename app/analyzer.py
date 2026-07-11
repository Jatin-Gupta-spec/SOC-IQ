from pathlib import Path

from app.extractor import (
    COMPILED_PATTERNS,
    read_report,
    extract_iocs,
)

from app.display import (
    display_summary,
    display_iocs,
)

from app.exporters import (
    export_to_json,
    export_to_csv,
)

from app.logger import logger


def analyze_report(report_path: Path) -> dict:
    """
    Analyze a malware report and
    generate all application outputs.
    """

    logger.info("Reading malware report...")
    report_text = read_report(
        report_path,
    )

    logger.info("Extracting IOCs...")
    extracted_iocs = extract_iocs(
        report_text,
        COMPILED_PATTERNS,
    )

    logger.info("Displaying results...")
    display_summary(
        extracted_iocs,
    )

    display_iocs(
        extracted_iocs,
    )

    logger.info("Exporting JSON report...")
    export_to_json(
        extracted_iocs,
    )

    logger.info(
        "JSON report exported successfully."
    )

    logger.info("Exporting CSV report...")
    export_to_csv(
        extracted_iocs,
    )

    logger.info(
        "CSV report exported successfully."
    )

    logger.info(
        "IOC extraction completed successfully."
    )

    return extracted_iocs