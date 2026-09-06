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
    compute_source_provenance,
    extract_iocs,
)
from app.logger import logger
from app.scoring.engine import RiskScoringEngine
from app.scoring.models import RiskScore
from app.threat_intel.exceptions import MissingAPIKeyError
from app.threat_intel.service import ThreatIntelService

#: The three pipeline-stage option keys understood by `analyze_report`'s
#: `options` argument, mirroring `app.application.dto.ANALYSIS_OPTION_FIELDS`
#: (Phase 4I Blocker B, Part 2A). Deliberately duplicated as a plain
#: dict/str contract here rather than importing `AnalysisOptions` --
#: app.analyzer is the domain layer and app.application is the layer
#: above it; the domain must not depend on the application layer (no
#: confirmed existing app.analyzer -> app.application import anywhere in
#: this codebase, and introducing one would invert that dependency).
#: `AnalyzeReportCommandHandler` is the seam that translates a real
#: `AnalysisOptions` into this plain dict via `.to_dict()`.
_DEFAULT_OPTIONS: dict[str, bool] = {
    "extract_iocs": True,
    "enrich_ti": True,
    "score_risk": True,
}


def _resolve_options(options: dict[str, bool] | None) -> dict[str, bool]:
    """
    Normalize the `options` argument to a complete `{extract_iocs,
    enrich_ti, score_risk}` dict of booleans.

    `None` (the default -- every existing caller before Part 2B, and
    every report_path-only `analyze_report` command payload) means "no
    options were specified", which resolves to all three `True` -- the
    exact pipeline that ran unconditionally before this option existed.
    Per-key: a dict that omits a key defaults that key to `True` too, so
    a caller can disable just one stage without needing to spell out the
    other two.
    """

    if options is None:
        return dict(_DEFAULT_OPTIONS)

    return {
        key: bool(options.get(key, True))
        for key in _DEFAULT_OPTIONS
    }


def analyze_report(
    report_path: Path,
    progress_callback: Callable[[int, str], None] | None = None,
    options: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """
    Analyze a malware report.

    Workflow:
    1. Read report
    2. Extract IOCs (if options["extract_iocs"])
    3. Check duplicate investigation
    4. Enrich using VirusTotal (if options["enrich_ti"])
    5. Calculate risk score (if options["score_risk"])
    6. Save investigation
    7. Return investigation

    Per Phase 4I Blocker B, Part 2B: each of the three optional stages
    is genuinely skipped -- not run-and-discarded -- when its flag is
    `False`. `options=None` (or an omitted key) preserves the exact
    pre-existing behavior: that stage runs.
    """

    resolved_options = _resolve_options(options)
    extract_iocs_enabled = resolved_options["extract_iocs"]
    enrich_ti_enabled = resolved_options["enrich_ti"]
    score_risk_enabled = resolved_options["score_risk"]

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

    source = compute_source_provenance(
        report_path,
    )

    report_text = source.text

    if extract_iocs_enabled:

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

    else:

        if progress_callback is not None:

            progress_callback(
                25,
                "Skipping IOC extraction (disabled for this analysis)...",
            )

        logger.info(
            "IOC extraction disabled (extract_iocs=False). Skipping."
        )

        # Same shape a real extraction returns (every pattern key present,
        # each mapped to an empty list) -- not a fabricated result, an
        # honest "nothing was extracted because extraction did not run"
        # that downstream TI enrichment / risk scoring can consume
        # exactly like a real (empty) extraction would.
        extracted_iocs = {
            ioc_type: []
            for ioc_type in COMPILED_PATTERNS
        }

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

    if enrich_ti_enabled:

        # `status` records *why* `hashes` looks the way it does, so
        # downstream consumers (risk scoring, the Investigation
        # record, any future UI) can tell "checked and found nothing"
        # apart from "never actually checked" -- previously both
        # collapsed to the same empty `{"hashes": []}` shape, which is
        # actively misleading in a tool whose job is to report risk.
        threat_intelligence: dict[str, Any] = {
            "hashes": [],
            "ips": [],
            "domains": [],
            "urls": [],
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
                "ips": [],
                "domains": [],
                "urls": [],
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
                "ips": [],
                "domains": [],
                "urls": [],
                "status": "unavailable",
                "reason": "error",
            }

    else:

        if progress_callback is not None:

            progress_callback(
                60,
                "Skipping Threat Intelligence (disabled for this analysis)...",
            )

        logger.info(
            "Threat intelligence enrichment disabled (enrich_ti=False). "
            "Skipping -- ThreatIntelService is not instantiated and no "
            "provider call is made."
        )

        # Same `{hashes/ips/domains/urls, status, reason}` shape the
        # missing-API-key/error branches above already use -- "disabled"
        # is a new, honest `reason` value alongside the existing
        # `not_attempted` / `missing_api_key` / `error`, not a new shape.
        threat_intelligence = {
            "hashes": [],
            "ips": [],
            "domains": [],
            "urls": [],
            "status": "unavailable",
            "reason": "disabled",
        }

    if score_risk_enabled:

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

    else:

        if progress_callback is not None:

            progress_callback(
                80,
                "Skipping Risk Scoring (disabled for this analysis)...",
            )

        logger.info(
            "Risk scoring disabled (score_risk=False). Skipping -- "
            "RiskScoringEngine is not invoked."
        )

        # An honest "not scored" sentinel, not a fabricated score: 0
        # everywhere a real calculation would put a number, and a
        # `severity` value ("NOT_SCORED") that cannot be confused with
        # any real LOW/MEDIUM/HIGH/CRITICAL classification
        # (`RiskScoringEngine._determine_severity` only ever returns
        # one of those four -- "NOT_SCORED" is not among them).
        risk = RiskScore(
            score=0,
            severity="NOT_SCORED",
            confidence=0.0,
            ioc_score=0,
            threat_intel_score=0,
            cve_score=0,
            reasons=[
                "Risk scoring was disabled for this analysis "
                "(score_risk=False).",
            ],
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
        source_sha256=source.sha256,
        source_size_bytes=source.size_bytes,
    )

    if progress_callback is not None:

        progress_callback(
            90,
            "Saving Investigation...",
        )

    logger.info(
        "Saving investigation."
    )

    # F2 (MAX-21A forensic audit) hardening: the exists_by_report_name()
    # check above and this save() are not atomic, so a concurrent
    # analyze_report() call for the same report_path can reach this
    # point having *also* observed no existing investigation. Rather
    # than the plain save() (which would only surface the resulting
    # database-level conflict as a resolved-but-anonymous ID),
    # save_resolving_conflict() reports whether *this* call actually
    # created the row or lost the race and was resolved to whichever
    # investigation the database committed first -- so the loser can
    # be reported back to its caller with the same
    # `"existing": True` semantics as the pre-existing
    # exists_by_report_name()-detected duplicate path above, instead
    # of a misleading `"existing": False` for a row it did not
    # actually create.
    investigation_id, created = (
        investigation_repository.save_resolving_conflict(
            investigation,
        )
    )

    logger.info(
        "Investigation stored with ID %d (created=%s)",
        investigation_id,
        created,
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
        "existing": not created,
    }
