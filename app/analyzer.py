from pathlib import Path

from app.extractor import (
    COMPILED_PATTERNS,
    read_report,
    extract_iocs,
)

from app.logger import logger


def analyze_report(report_path: Path) -> dict:
    """
    Analyze a malware report and return
    the extracted IOCs.
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

    logger.info(
        "IOC extraction completed successfully."
    )

    return extracted_iocs