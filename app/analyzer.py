"""
SOC-IQ analysis engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.database.models import Investigation
from app.database.repository import InvestigationRepository
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
    progress_callback: Callable[[int, str], None] | None = None,
) -> dict[str, Any]:
    """
    Analyze a malware report.

    Workflow:
    1. Read report
    2. Extract IOCs
    3. Check duplicate investigation
    4. Enrich using VirusTotal
    5. Calculate risk score
    6. Save investigation
    7. Return investigation
    """

    investigation_repository = (
        InvestigationRepository()
    )

    if progress_callback is not None:

        progress_callback(
            10,
            "Loading report...",
        )

    logger.info(
        "Reading malware report."
    )

    report_text = read_report(
        report_path,
    )

    if progress_callback is not None:

        progress_callback(
            25,
            "Extracting Indicators of Compromise...",
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

    if progress_callback is not None:

        progress_callback(
            40,
            "Checking previous investigations...",
        )

    logger.info(
        "Checking for duplicate investigation."
    )

    if investigation_repository.exists_by_report_name(
        report_path.name,
    ):

        logger.info(
            "Existing investigation found for '%s'.",
            report_path.name,
        )

        # `find_by_report_name` returns every matching
        # investigation ordered newest-first (see
        # `InvestigationRepository`), so the latest one is the
        # first element.
        existing_matches = (
            investigation_repository.find_by_report_name(
                report_path.name,
            )
        )

        if not existing_matches:

            raise RuntimeError(
                "Duplicate investigation detected "
                "but no investigation could be loaded."
            )

        return {
            "investigation": existing_matches[0],
            "existing": True,
        }

    # `status` records *why* `hashes` looks the way it does, so
    # downstream consumers (risk scoring, the Investigation
    # record, any future UI) can tell "checked and found nothing"
    # apart from "never actually checked" -- previously both
    # collapsed to the same empty `{"hashes": []}` shape, which is
    # actively misleading in a tool whose job is to report risk.
    threat_intelligence: dict[str, Any] = {
        "hashes": [],
        "status": "unavailable",
        "reason": "not_attempted",
    }

    try:

        with ThreatIntelService() as service:

            logger.info(
                "Starting threat intelligence enrichment."
            )

            if progress_callback is not None:

                progress_callback(
                    60,
                    "Running Threat Intelligence...",
                )

            threat_intelligence = (
                service.enrich_results(
                    extracted_iocs,
                )
            )

            logger.info(
                "Threat intelligence enrichment completed "
                "(status=%s).",
                threat_intelligence.get("status"),
            )

    except MissingAPIKeyError:

        logger.warning(
            "VirusTotal API key not configured. "
            "Skipping enrichment."
        )

        threat_intelligence = {
            "hashes": [],
            "status": "unavailable",
            "reason": "missing_api_key",
        }

    except Exception as error:

        logger.exception(
            "Threat intelligence failed: %s",
            error,
        )

        threat_intelligence = {
            "hashes": [],
            "status": "unavailable",
            "reason": "error",
        }

    if progress_callback is not None:

        progress_callback(
            80,
            "Calculating Risk Score...",
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
        confidence=risk.confidence,
        ioc_score=risk.ioc_score,
        threat_intel_score=risk.threat_intel_score,
        cve_score=risk.cve_score,
    )

    if progress_callback is not None:

        progress_callback(
            90,
            "Saving Investigation...",
        )

    logger.info(
        "Saving investigation."
    )

    investigation_id = (
        investigation_repository.save(
            investigation,
        )
    )

    logger.info(
        "Investigation stored with ID %d",
        investigation_id,
    )

    loaded = (
        investigation_repository.get_by_id(
            investigation_id,
        )
    )

    if loaded is None:

        raise RuntimeError(
            "Saved investigation could not be loaded."
        )

    if progress_callback is not None:

        progress_callback(
            100,
            "Investigation Complete",
        )

    return {
        "investigation": loaded,
        "existing": False,
    }