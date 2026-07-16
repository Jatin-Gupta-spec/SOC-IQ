"""
SOC-IQ analysis engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database.models import Investigation
from app.database.service import InvestigationService
from app.extractor import (
    COMPILED_PATTERNS,
    extract_iocs,
    read_report,
)
from app.logger import logger
from app.scoring.engine import RiskScoringEngine
from app.threat_intel.exceptions import MissingAPIKeyError
from app.threat_intel.service import ThreatIntelService


def analyze_report(
    report_path: Path,
) -> dict[str, Any]:
    """
    Analyze a malware report.

    Workflow:
    1. Read report
    2. Extract IOCs
    3. Enrich using VirusTotal
    4. Calculate risk score
    5. Save investigation
    6. Return complete analysis
    """

    logger.info(
        "Reading malware report."
    )

    report_text = read_report(
        report_path,
    )

    logger.info(
        "Extracting IOCs."
    )

    extracted_iocs = extract_iocs(
        report_text,
        COMPILED_PATTERNS,
    )

    logger.info(
        "IOC extraction completed."
    )

    threat_intelligence: dict[str, Any] = {
        "hashes": [],
    }

    try:

        with ThreatIntelService() as service:

            logger.info(
                "Starting threat intelligence enrichment."
            )

            threat_intelligence = (
                service.enrich_results(
                    extracted_iocs,
                )
            )

            logger.info(
                "Threat intelligence enrichment completed."
            )

    except MissingAPIKeyError:

        logger.warning(
            "VirusTotal API key not configured. "
            "Skipping enrichment."
        )

    except Exception as error:

        logger.exception(
            "Threat intelligence failed: %s",
            error,
        )

    logger.info(
        "Calculating investigation risk."
    )

    scoring_engine = RiskScoringEngine()

    risk = scoring_engine.calculate(
        extracted_iocs,
        threat_intelligence,
    )

    logger.info(
        "Risk Score: %d (%s)",
        risk.score,
        risk.severity,
    )

    investigation = Investigation(
        report_name=report_path.name,
        iocs=extracted_iocs,
        threat_intelligence=threat_intelligence,
        risk_score=risk.score,
        severity=risk.severity,
    )

    logger.info(
        "Saving investigation."
    )

    investigation_service = (
        InvestigationService()
    )

    investigation_id = (
        investigation_service.save(
            investigation,
        )
    )

    logger.info(
        "Investigation stored with ID %d",
        investigation_id,
    )

    return {
        "investigation_id": investigation_id,
        "iocs": extracted_iocs,
        "threat_intelligence": (
            threat_intelligence
        ),
        "risk": scoring_engine.summarize(
            risk,
        ),
    }