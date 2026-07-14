from pathlib import Path
from typing import Any

from app.extractor import (
    COMPILED_PATTERNS,
    extract_iocs,
    read_report,
)
from app.logger import logger
from app.threat_intel.exceptions import MissingAPIKeyError
from app.threat_intel.service import ThreatIntelService


def analyze_report(
    report_path: Path,
) -> dict[str, Any]:
    """
    Analyze a malware report, extract IOCs,
    and enrich extracted indicators using
    threat intelligence providers.
    """

    logger.info(
        "Reading malware report..."
    )

    report_text = read_report(
        report_path,
    )

    logger.info(
        "Extracting IOCs..."
    )

    extracted_iocs = extract_iocs(
        report_text,
        COMPILED_PATTERNS,
    )

    logger.info(
        "IOC extraction completed successfully."
    )

    threat_intelligence: dict[str, Any] = {
        "hashes": []
    }

    try:

        with ThreatIntelService() as threat_service:

            logger.info(
                "Starting threat intelligence enrichment."
            )

            threat_intelligence = (
                threat_service.enrich_results(
                    extracted_iocs
                )
            )

            logger.info(
                "Threat intelligence enrichment completed."
            )

    except MissingAPIKeyError:

        logger.warning(
            "VirusTotal API key not configured. "
            "Threat intelligence enrichment skipped."
        )

    except Exception as error:

        logger.exception(
            "Threat intelligence enrichment failed: %s",
            error,
        )

    return {
        "iocs": extracted_iocs,
        "threat_intelligence": threat_intelligence,
    }