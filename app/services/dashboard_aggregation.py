"""
SOC-IQ
Dashboard Aggregation

Pure, framework-independent aggregation functions over a list of
persisted `Investigation` domain objects.

Phase 4H Part 1 extracts these out of the existing dashboard services
(`DashboardStatisticsService.get_summary`,
`DashboardIOCDistributionService.get_distribution`) so the same
calculation has exactly one implementation, reused by:

  - the existing GUI-facing dashboard services (unchanged public
    return shape -- see those modules' own docstrings), and
  - the new `get_dashboard_summary` application command
    (`app/application/handlers.py`), which needs typed (not
    stringly-typed) values and a couple of additional breakdowns the
    GUI services never needed.

No I/O of any kind happens here: every function takes an already-loaded
`list[Investigation]` and returns a plain, JSON-safe `dict`/`float`/
`int`. Nothing here talks to a database, a Qt widget, or a domain
service -- callers own fetching the investigations exactly once.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from app.database.models import Investigation

# Severities/statuses considered "high risk" for the KPI row, mirroring
# `DashboardStatisticsService.get_summary`'s existing (pre-Phase-4H)
# definition exactly -- HIGH and CRITICAL, case-insensitively.
_HIGH_RISK_SEVERITIES = {"HIGH", "CRITICAL"}


def compute_ioc_distribution(
    investigations: list[Investigation],
) -> dict[str, int]:
    """
    Return IOC counts grouped by `ioc_type`, summed across every
    investigation given.

    Byte-for-byte the same calculation
    `DashboardIOCDistributionService.get_distribution` already
    performed inline; extracted here so that service and the new
    `get_dashboard_summary` command share one implementation rather
    than two independently-maintained copies of the same loop.
    """

    counter: Counter[str] = Counter()

    for investigation in investigations:
        for ioc_type, values in (investigation.iocs or {}).items():
            counter[ioc_type] += len(values)

    return dict(counter)


def compute_severity_distribution(
    investigations: list[Investigation],
) -> dict[str, int]:
    """
    Return investigation counts grouped by `severity`.

    Unlike `compute_dashboard_metrics`'s `high_risk` figure (which
    collapses HIGH/CRITICAL into one count for the KPI row), this
    keeps every distinct persisted severity value as its own bucket,
    which is what a risk/severity distribution widget needs to draw
    e.g. a per-severity bar chart. `severity` is normalized to
    uppercase (matching `DashboardThreatService`'s own
    case-insensitive comparison) so `"High"` and `"HIGH"` are not
    silently split into two buckets. A missing/blank severity is
    grouped under `"UNKNOWN"` rather than dropped -- every persisted
    investigation is accounted for in exactly one bucket.
    """

    counter: Counter[str] = Counter()

    for investigation in investigations:
        severity = (investigation.severity or "").strip().upper()
        counter[severity or "UNKNOWN"] += 1

    return dict(counter)


def compute_status_counts(
    investigations: list[Investigation],
) -> dict[str, int]:
    """
    Return investigation counts grouped by the real, persisted
    `Investigation.status` field.

    This is deliberately NOT the `open` / `in_progress` / `closed`
    SOC-workflow vocabulary `frontend/src/mock/investigations.ts` and
    `dashboardViewModel.ts::summarizeInvestigationWorkload` use --
    that vocabulary describes a workflow concept that does not exist
    anywhere in the persisted `Investigation` model or in
    `app.analyzer`/`app.database.repository` (confirmed by source
    inspection: `status` is set once, to the literal `"COMPLETED"`,
    by `Investigation`'s own dataclass default, and is never
    reassigned anywhere in this codebase today). Inventing a
    three-bucket workflow-status breakdown to match that mock would be
    exactly the kind of fabricated value this phase's brief prohibits.
    Grouping by whatever status strings are *actually* persisted is
    the honest analogue -- today that will genuinely be a single
    `{"COMPLETED": N}` bucket, and the shape is ready to show more
    buckets the day a real workflow-status concept is introduced,
    without a contract change.
    """

    counter: Counter[str] = Counter()

    for investigation in investigations:
        status = (investigation.status or "").strip() or "UNKNOWN"
        counter[status] += 1

    return dict(counter)


def compute_dashboard_metrics(
    investigations: list[Investigation],
) -> dict[str, int]:
    """
    Return the typed (never stringly-typed) KPI figures: total report
    count, total IOC count (summed across every category), and the
    HIGH/CRITICAL "high risk" count.

    Same calculation `DashboardStatisticsService.get_summary` already
    performed inline (down to the same HIGH/CRITICAL definition,
    `_HIGH_RISK_SEVERITIES`) -- extracted here so that service (which
    must keep returning `dict[str, str]` for its existing GUI caller,
    `app.gui.controllers.dashboard_controller.DashboardController`)
    and the new `get_dashboard_summary` command (which wants real
    `int`s, per this phase's "Qt/GUI-shaped values must not leak into
    the API layer" requirement) share one implementation instead of
    two copies that could silently drift apart.
    """

    report_count = len(investigations)

    total_iocs = sum(
        sum(len(values) for values in (investigation.iocs or {}).values())
        for investigation in investigations
    )

    high_risk = sum(
        1
        for investigation in investigations
        if (investigation.severity or "").upper() in _HIGH_RISK_SEVERITIES
    )

    return {
        "report_count": report_count,
        "total_iocs": total_iocs,
        "high_risk": high_risk,
    }


def compute_threat_intel_coverage_percent(
    investigations: list[Investigation],
) -> float | None:
    """
    Return the percentage of requested threat-intelligence lookups
    that succeeded, aggregated across every investigation given, or
    `None` if this cannot be honestly computed from persisted data.

    Per the Phase 4H brief: "Threat Intel Coverage % is currently not
    provided by any existing service... do NOT silently invent a
    calculation... if it cannot be derived confidently, do NOT
    fabricate it." Source inspection
    (`app.services.threat_intel_state.build_investigation_threat_intel_overview`,
    already reused elsewhere in the application layer via
    `build_investigation_indicator_states`) confirms every
    investigation that ever underwent enrichment persists a
    `threat_intelligence["coverage"]` dict with `"requested"` /
    `"succeeded"` integer counts -- exactly the numbers
    `ThreatIntelService.enrich_results()` itself produced and already
    persisted, not a new metric invented at the API layer. This
    function only *sums* those already-persisted counts across
    investigations and divides; it introduces no new semantics.

    Returns `None` (never `0.0`, which would misleadingly read as "0%
    coverage") when zero lookups were ever requested across every
    investigation -- e.g. an empty database, or a database where no
    investigation has any enrichable indicators / TI was never run.
    `0.0` is reserved for the genuine case: enrichment was requested
    at least once, and every single request failed.
    """

    total_requested = 0
    total_succeeded = 0

    for investigation in investigations:
        threat_intelligence = investigation.threat_intelligence or {}
        coverage = threat_intelligence.get("coverage", {}) or {}

        requested = coverage.get("requested", 0)
        succeeded = coverage.get("succeeded", 0)

        if not isinstance(requested, int) or not isinstance(succeeded, int):
            # Persisted data too malformed to trust -- never guess at a
            # numeric coverage figure from something that isn't one.
            continue

        total_requested += requested
        total_succeeded += succeeded

    if total_requested <= 0:
        return None

    return round((total_succeeded / total_requested) * 100.0, 1)


def compute_investigation_activity_by_date(
    investigations: list[Investigation],
) -> dict[str, int]:
    """
    Return investigation counts grouped by the calendar date (`YYYY-MM-DD`,
    UTC-naive string form) portion of each investigation's `analyzed_at`.

    Added for PD-04 (cross-investigation aggregate backend commands,
    docs/phase4/PD04_CROSS_INVESTIGATION_AGGREGATE_COMMANDS.md) --
    distinct from, and not a substitute for, the Dashboard's own
    Timeline widget, which remains a separate, still-unresolved product
    decision (see `DashboardSummaryDTO`'s own docstring and
    docs/phase4/PHASE4H_PART1_BACKEND_API_CONTRACT.md S "Timeline
    data"). This function returns a flat day-bucketed count derived
    honestly from already-persisted `analyzed_at` values -- it does not
    attempt to reconstruct `DashboardTimelineService`'s emoji-bearing
    `TimelineEvent` presentation shape or answer that separate product
    question.

    Mirrors `InvestigationSummaryDTO.from_domain`'s own defensive
    handling of `analyzed_at` (normally a `datetime` per
    `Investigation`'s dataclass field and always re-parsed as one by
    `InvestigationRepository`, but accepted here as a bare string too
    rather than assumed). An `analyzed_at` that is neither a `datetime`
    nor a parseable ISO string is skipped rather than guessed at or
    allowed to raise -- the same "fail safely, never fabricate" rule
    `compute_threat_intel_coverage_percent` above already follows for
    malformed persisted data.
    """

    counter: Counter[str] = Counter()

    for investigation in investigations:
        analyzed_at = investigation.analyzed_at

        if isinstance(analyzed_at, datetime):
            date_key = analyzed_at.date().isoformat()
        elif isinstance(analyzed_at, str):
            try:
                date_key = datetime.fromisoformat(analyzed_at).date().isoformat()
            except ValueError:
                continue
        else:
            continue

        counter[date_key] += 1

    return dict(counter)
