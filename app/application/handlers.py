"""
Command handlers, per docs/contracts/command-model.md.

Each handler is a thin translation: validated request DTO in, existing
domain/application call, response envelope (docs/contracts/response-model.md)
out. No business logic lives here -- see
docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S3/S5.1 for why
app.analyzer.analyze_report and app.database.service.InvestigationService
are called unmodified rather than reimplemented.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from app.analyzer import analyze_report as domain_analyze_report
from app.application.dto import (
    AnalyzeReportRequest,
    CommandValidationError,
    DashboardMetricsDTO,
    DashboardSummaryDTO,
    DeleteInvestigationRequest,
    EnrichIocRequest,
    ExportInvestigationsCsvRequest,
    ExportReportRequest,
    GetDashboardSummaryRequest,
    GetInvestigationAggregateSummaryRequest,
    GetInvestigationIntegrityRequest,
    GetInvestigationProvenanceRequest,
    GetInvestigationRequest,
    GetInvestigationRiskExplanationRequest,
    GetIocsRequest,
    GetSettingsRequest,
    GetThreatIntelligenceRequest,
    GetTimelineRequest,
    InvestigationAggregateSummaryDTO,
    InvestigationCorrelationDTO,
    InvestigationSummaryDTO,
    IOCProvenanceDTO,
    ListInvestigationsRequest,
    RiskExplanationDTO,
    SaveSettingsRequest,
    SearchInvestigationsRequest,
    SourceIntegrityDTO,
    TimelineEventDTO,
)
from app.application.broker import EventBroker, get_application_broker
from app.application.errors import INVESTIGATION_NOT_FOUND, code_for_exception
from app.application.events import Event, EventCollector, new_correlation_id
from app.application.execution import run_blocking
from app.application.responses import fail, ok
from app.database.service import InvestigationService
from app.reporting.service import ReportingService
from app.services.correlation_service import CorrelationService
from app.timeline.domain import TimelineEvent, TimelineEventType
from app.timeline.repository import TimelineRepository
from app.services.dashboard_aggregation import (
    compute_dashboard_metrics,
    compute_investigation_activity_by_date,
    compute_ioc_distribution,
    compute_severity_distribution,
    compute_status_counts,
    compute_threat_intel_coverage_percent,
)
from app.services.dashboard_investigation_service import DashboardInvestigationService
from app.services.evidence_provenance import build_evidence_provenance_summary
from app.services.investigation_csv_export import (
    export_investigations_history_csv,
    filter_investigations_by_search_text,
)
from app.services.investigation_integrity import build_integrity_summary
from app.services.ioc_provenance import build_ioc_provenance
from app.services.ioc_significance import ioc_type_significance, ioc_type_weight
from app.services.risk_explanation_service import RiskExplanationService
from app.services.threat_intel_state import build_investigation_indicator_states
from app.settings.service import SettingsService
from app.threat_intel.service import ThreatIntelService
from app.threat_intel.verdict_from_persisted import build_investigation_typed_verdicts
from app.timeline.repository import TimelineRepository

logger = logging.getLogger(__name__)


def _report_path_is_valid(report_path: str) -> bool:
    path = Path(report_path)
    return path.exists() and path.is_file()


class GetInvestigationCommandHandler:
    """Wraps InvestigationService.get_by_id -- see command-model.md.

    Phase 4J-6 additionally exposes a `correlations` field alongside
    the existing `InvestigationSummaryDTO` fields: the deterministic,
    explicit-only relationships
    `app.services.correlation_service.CorrelationService` derives from
    this same already-loaded `Investigation`'s `iocs` and
    `threat_intelligence` (see that service's own docstring for the
    determinism/no-network/no-inference guarantees). `CorrelationService`
    is called unmodified, exactly as `GetThreatIntelligenceCommandHandler`
    above calls `build_investigation_indicator_states` unmodified.

    This field is added to the *response dict*, not to
    `InvestigationSummaryDTO` itself -- that DTO is reused unchanged
    by `list_investigations`, `search_investigations`, and the
    Dashboard's `recent_investigations` (see `InvestigationSummaryDTO`'s
    own docstring and `InvestigationCorrelationDTO`'s), so adding a
    field there would compute a correlation report for every
    investigation in every list/dashboard response, not just the one
    being viewed here, and would touch a frozen Dashboard response
    shape. `correlations` is therefore scoped to `get_investigation`
    alone.
    """

    def __init__(
        self,
        service: InvestigationService | None = None,
        correlation_service: CorrelationService | None = None,
    ) -> None:
        self._service = service if service is not None else InvestigationService()
        self._correlation_service = (
            correlation_service if correlation_service is not None else CorrelationService()
        )

    def handle(self, request: GetInvestigationRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        data = InvestigationSummaryDTO.from_domain(investigation).to_dict()

        correlation_report = self._correlation_service.correlate(investigation)
        data["correlations"] = [
            InvestigationCorrelationDTO.from_domain(result).to_dict()
            for result in correlation_report.results
        ]

        return ok(data)


class GetIocsCommandHandler:
    """Wraps InvestigationService.get_by_id -- see command-model.md
    `get_iocs` and docs/contracts/PHASE4B_QUERY_INVENTORY.md.

    Reuses the exact same lookup as GetInvestigationCommandHandler
    (same DB round trip, same INVESTIGATION_NOT_FOUND semantics) rather
    than inventing a second query path -- `Investigation.iocs` is already
    loaded on the domain object returned by `get_by_id`; this handler
    just exposes the field the summary DTO deliberately omits, per
    `InvestigationSummaryDTO`'s own docstring.

    PD-08-P3 adds `significance`: for each IOC category actually present
    on this investigation (i.e. each key of `investigation.iocs`, same
    set `RiskExplanationService` already iterates for
    `IocCategoryContribution` -- PD-08-P1), the same scoring-engine
    weight and presentation label `RiskExplanationService` and the
    legacy `IOCSummaryWidget`/`IOCDetailDialog` already derive via
    `app.services.ioc_significance.ioc_type_weight()` /
    `ioc_type_significance()`. Both are pure functions of the IOC
    *category* only (`RiskScoringEngine.IOC_WEIGHTS`, keyed by type, not
    by individual IOC value) -- see that module's own docstring -- so
    there is exactly one entry per category present, never one per
    individual indicator value, and never an entry for a category this
    investigation has no IOCs of. `ioc_type_significance()` never
    returns `None`: an (in practice unreachable, since all ten real
    persisted categories already have an explicit weight) category
    outside `IOC_WEIGHTS` still receives the same defensive
    `"Informational"` fallback (weight `0`) the module has always used
    -- this handler does not invent a second fallback.

    No new service layer, no second weight table, no DB/schema change,
    and no `app.gui` import: `app.services.ioc_significance` is already
    framework-independent (PHASE4B_QUERY_INVENTORY.md's own "currently
    mis-located under app/gui/utils/" note is now stale -- as of this
    checkpoint the module already lives under `app/services/` and is
    already consumed by `RiskExplanationService`, a backend-only
    module).
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: GetIocsRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        return ok(
            {
                "investigation_id": investigation.investigation_id,
                "iocs": investigation.iocs,
                "significance": {
                    ioc_type: {
                        "weight": ioc_type_weight(ioc_type),
                        "significance": ioc_type_significance(ioc_type),
                    }
                    for ioc_type in investigation.iocs
                },
            }
        )


class GetThreatIntelligenceCommandHandler:
    """Wraps InvestigationService.get_by_id -- see command-model.md
    `get_threat_intelligence` and `InvestigationSummaryDTO`'s own
    docstring.

    Reuses the exact same lookup as GetInvestigationCommandHandler /
    GetIocsCommandHandler (same DB round trip, same
    INVESTIGATION_NOT_FOUND semantics) rather than inventing a second
    query path -- `Investigation.threat_intelligence` is already
    loaded on the domain object returned by `get_by_id`; this handler
    just exposes the field the summary DTO deliberately omits.

    Deliberately does NOT call
    `app.services.ioc_detail_context.build_investigation_threat_intel_overview`:
    that function is real and Qt-free, but it lives under `app.gui`,
    and `app.application` never imports `app.gui` anywhere in this
    file (see SearchInvestigationsCommandHandler's docstring) -- this
    handler holds that line rather than making an exception for
    itself. The raw, already-persisted dict is exposed as-is,
    unchanged, for full backward compatibility.

    Phase 4J-2 additionally exposes a deterministic `states` projection
    (per-indicator TI_STATE_* classification, grouped by `ioc_type` to
    match `Investigation.iocs`'s own shape) alongside the raw payload,
    via `app.services.threat_intel_state.build_investigation_indicator_states`
    -- the framework-independent module Phase 4J-1 already established
    specifically so `app.application` could reuse this classification
    without importing `app.gui` or reimplementing it here.

    Phase 4K-1 additionally exposes a `typed_verdicts` projection
    (per-indicator typed `Verdict` classification -- `"clean"` /
    `"not_found"` / `"malicious"` / `"suspicious"`, or `None` where
    persisted data is insufficient to classify honestly -- grouped by
    `ioc_type` the same way `states` is), via
    `app.threat_intel.verdict_from_persisted.build_investigation_typed_verdicts`.
    This is derived entirely from the already-persisted raw
    `threat_intelligence` payload -- no provider is called, and the
    legacy `verdict` display string embedded in that payload is never
    parsed. `threat_intelligence` and `states` remain unchanged.
    """

    def __init__(
        self,
        service: InvestigationService | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        self._service = service if service is not None else InvestigationService()
        self._settings_service = (
            settings_service if settings_service is not None else SettingsService()
        )

    def handle(self, request: GetThreatIntelligenceRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        settings = self._settings_service.load_settings()

        states = build_investigation_indicator_states(
            investigation,
            api_key_configured=bool(settings.virustotal_api_key),
        )

        typed_verdicts = build_investigation_typed_verdicts(investigation)

        return ok(
            {
                "investigation_id": investigation.investigation_id,
                "threat_intelligence": investigation.threat_intelligence,
                "states": states,
                "typed_verdicts": typed_verdicts,
            }
        )


class GetInvestigationIntegrityCommandHandler:
    """Wraps InvestigationService.get_by_id -- see command-model.md
    (proposed) `get_investigation_integrity` and
    docs/architecture/PROVENANCE.md.

    Reuses the exact same lookup as GetInvestigationCommandHandler /
    GetIocsCommandHandler / GetThreatIntelligenceCommandHandler (same
    DB round trip, same INVESTIGATION_NOT_FOUND semantics) rather than
    inventing a second query path. Returns two derived, framework-
    independent views computed purely from the already-loaded
    `Investigation` -- no provider call, no additional DB access:

    - `integrity`: `InvestigationIntegritySummary`
      (`app.services.investigation_integrity`) -- the
      "what did SOC-IQ actually do for this investigation" checklist.
    - `evidence`: `EvidenceProvenanceSummary`
      (`app.services.evidence_provenance`) -- the OBSERVED / ENRICHED
      / DERIVED breakdown A4-P1's evidence model defines.

    Also echoes the source-identity fields (`report_name`,
    `source_sha256`, `source_size_bytes`) already present on
    `InvestigationSummaryDTO`, so a caller that only needs integrity
    information does not have to make a second `get_investigation`
    round trip just to learn which report this is about.
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: GetInvestigationIntegrityRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        return ok(
            {
                "investigation_id": investigation.investigation_id,
                "report_name": investigation.report_name,
                "source_sha256": investigation.source_sha256,
                "source_size_bytes": investigation.source_size_bytes,
                "integrity": build_integrity_summary(investigation).to_dict(),
                "evidence": build_evidence_provenance_summary(investigation).to_dict(),
            }
        )


class GetInvestigationProvenanceCommandHandler:
    """Wraps `InvestigationService.get_by_id` -- see command-model.md
    (proposed) `get_investigation_provenance`, A4-P2 Part 2, and
    docs/architecture/PROVENANCE.md.

    Reuses the exact same lookup as
    `GetInvestigationIntegrityCommandHandler` (same DB round trip,
    same `INVESTIGATION_NOT_FOUND` semantics, same
    investigation-scoped isolation: a request for investigation A can
    only ever see the row `InvestigationService.get_by_id` loads for
    A's own id -- there is no code path here that can pull in another
    investigation's rows). Builds two views, both purely from the
    already-loaded `Investigation` -- no additional DB access, no
    provider call, no N+1 per-IOC query:

    - `source_integrity`: `SourceIntegrityDTO` -- the A4-P1 source
      hash/size fields, plus an explicit AVAILABLE/UNAVAILABLE status
      so a legacy investigation's missing hash is never confused with
      a query failure.
    - `ioc_provenance`: a list of `IOCProvenanceDTO`, one per record
      `app.services.ioc_provenance.build_ioc_provenance` (A4-P2.1)
      derives for this investigation -- every entry OBSERVED, per
      that module's own scope. An investigation with no extracted
      IOCs yields an empty list here (a genuine EMPTY state), which
      is not the same response shape as the `INVESTIGATION_NOT_FOUND`
      failure envelope returned when the investigation itself does
      not exist -- callers can tell "no provenance to show" apart
      from "no such investigation" from the envelope alone.

    Deliberately does NOT duplicate `GetInvestigationIntegrityCommandHandler`'s
    `integrity`/`evidence` aggregate summaries -- that remains the one
    place those are computed; this command is scoped to the read
    model A4-P2.1 actually added (per-IOC provenance) plus the source
    identity a provenance consumer needs to make sense of it, so a
    caller does not have to also learn `investigation_id` from a
    second `get_investigation` round trip.
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: GetInvestigationProvenanceRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        ioc_provenance_records = build_ioc_provenance(investigation)

        return ok(
            {
                "investigation_id": investigation.investigation_id,
                "report_name": investigation.report_name,
                "source_integrity": SourceIntegrityDTO.from_domain(investigation).to_dict(),
                "ioc_provenance": [
                    IOCProvenanceDTO.from_domain(record).to_dict()
                    for record in ioc_provenance_records
                ],
            }
        )


class GetInvestigationRiskExplanationCommandHandler:
    """Wraps `InvestigationService.get_by_id` -- see command-model.md
    (proposed) `get_investigation_risk_explanation`, PD-08-P1
    (docs/phase4/PD08_P1_RISK_EXPLANATION_BACKEND.md).

    Adapts the existing, already-tested (PHASE3C-1, ~24 tests)
    `app.services.risk_explanation_service.RiskExplanationService`
    onto the modern command boundary. This handler reuses that
    service unchanged -- it does not recalculate risk, does not
    duplicate IOC weight/scoring logic, and does not reinterpret the
    engine's own output; the same rule
    `GetInvestigationCommandHandler`'s docstring states for
    `CorrelationService` applies here for `RiskExplanationService`.

    Reuses the exact same lookup as `GetInvestigationCommandHandler`/
    `GetInvestigationIntegrityCommandHandler`/
    `GetInvestigationProvenanceCommandHandler` (same DB round trip,
    same `INVESTIGATION_NOT_FOUND` semantics) rather than inventing a
    second query path.

    Also reuses `GetInvestigationCommandHandler`'s own
    `CorrelationService` (correlation context is optional supporting
    evidence in the narrative, per `RiskExplanationService.explain()`'s
    `correlation_report` parameter) and
    `GetThreatIntelligenceCommandHandler`'s own `SettingsService` ->
    `api_key_configured` wiring (so the explanation's
    threat-intelligence coverage state reads the same honest "was a
    key even configured" signal the Threat Intelligence tab already
    does) -- both computed fresh per request, exactly like the legacy
    `InvestigationWorkspace` GUI page already does
    (app/gui/pages/investigation_workspace.py) before calling this
    same service.

    Kept as its own command, exactly like `get_investigation_integrity`
    and `get_investigation_provenance` (whose docstrings give the same
    reasoning): computing a risk explanation is never unavoidable
    overhead on `list_investigations` / `search_investigations` / the
    Dashboard's `recent_investigations`, all of which reuse
    `InvestigationSummaryDTO` unchanged.
    """

    def __init__(
        self,
        service: InvestigationService | None = None,
        correlation_service: CorrelationService | None = None,
        settings_service: SettingsService | None = None,
        risk_explanation_service: RiskExplanationService | None = None,
    ) -> None:
        self._service = service if service is not None else InvestigationService()
        self._correlation_service = (
            correlation_service
            if correlation_service is not None
            else CorrelationService()
        )
        self._settings_service = (
            settings_service if settings_service is not None else SettingsService()
        )
        self._risk_explanation_service = (
            risk_explanation_service
            if risk_explanation_service is not None
            else RiskExplanationService()
        )

    def handle(
        self, request: GetInvestigationRiskExplanationRequest
    ) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        correlation_report = self._correlation_service.correlate(investigation)
        settings = self._settings_service.load_settings()

        explanation = self._risk_explanation_service.explain(
            investigation,
            correlation_report=correlation_report,
            api_key_configured=bool(settings.virustotal_api_key),
        )

        return ok(RiskExplanationDTO.from_domain(explanation).to_dict())


class GetTimelineCommandHandler:
    """A4-P2-P3 Part 3: wraps
    `app.timeline.repository.TimelineRepository.list_for_investigation`
    -- the application/API integration for the Investigation Timeline
    Part 1 (domain) and Part 2 (persistence) already established.

    Reuses the exact same existence check as every other
    `investigation_id`-keyed handler in this file
    (`InvestigationService.get_by_id(...) is None` ->
    `INVESTIGATION_NOT_FOUND`) before ever touching
    `TimelineRepository`, so:

    - an id for an investigation that does not exist gets the same
      `INVESTIGATION_NOT_FOUND` envelope `get_investigation`/`get_iocs`/
      `get_investigation_provenance` already return, rather than a
      silently-empty timeline that could be confused with a real
      investigation that simply has no recorded events yet;
    - the investigation identity is always passed explicitly through
      the application boundary (the request DTO's `investigation_id`),
      and `TimelineRepository.list_for_investigation` is only ever
      called already scoped to that one id -- there is no code path
      here that fetches a global/unscoped timeline and filters
      afterward, and no code path that could return one
      investigation's events for a request naming a different one.

    `TimelineRepository.list_for_investigation` already returns
    events oldest -> newest, deterministically (see that method's own
    docstring) -- this handler does not re-sort or otherwise alter
    that ordering.

    A malformed persisted event (Part 2's `_row_to_event` re-raising
    `ValueError`/`TypeError` on a corrupt/undecodable row) is
    deliberately NOT caught here: it propagates up to `dispatch()`'s
    existing generic exception boundary, which translates it into a
    safe, generic error envelope (`code_for_exception` falls through
    to `INTERNAL_ERROR` for an exception type with no specific
    mapping) -- consistent with Part 2's own "do not convert corrupt
    data into plausible data" principle, extended here rather than
    re-implemented.
    """

    def __init__(
        self,
        service: InvestigationService | None = None,
        timeline_repository: TimelineRepository | None = None,
    ) -> None:
        self._service = service if service is not None else InvestigationService()
        self._timeline_repository = (
            timeline_repository if timeline_repository is not None else TimelineRepository()
        )

    def handle(self, request: GetTimelineRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        events = self._timeline_repository.list_for_investigation(
            request.investigation_id
        )

        return ok(
            {
                "investigation_id": request.investigation_id,
                "events": [
                    TimelineEventDTO.from_domain(event).to_dict() for event in events
                ],
            }
        )


class ListInvestigationsCommandHandler:
    """Wraps InvestigationService.list_all -- see command-model.md."""

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: ListInvestigationsRequest) -> dict[str, Any]:
        investigations = self._service.list_all()
        return ok(
            [
                InvestigationSummaryDTO.from_domain(investigation).to_dict()
                for investigation in investigations
            ]
        )


#: How many recent investigations `get_dashboard_summary` returns, per
#: `docs/phase4/PHASE4H_PART1_BACKEND_API_CONTRACT.md`. Matches
#: `DashboardInvestigationService.get_recent`'s own default so the API
#: contract's default behavior is identical to the GUI's existing
#: dashboard behavior, not an independently-chosen number.
DASHBOARD_RECENT_INVESTIGATIONS_LIMIT = 5


class GetDashboardSummaryCommandHandler:
    """Wraps a single `InvestigationService.list_all()` call (plus one
    `find_recent()` call for `recent_investigations`) -- see
    command-model.md `get_dashboard_summary` and
    `docs/phase4/PHASE4H_PART1_BACKEND_API_CONTRACT.md`.

    Deliberately fetches investigations exactly once (`list_all()`)
    and derives every aggregate figure (`metrics`,
    `investigation_status_counts`, `risk_distribution`,
    `ioc_distribution`) from that same in-memory list via the pure
    `app.services.dashboard_aggregation` functions -- no per-
    investigation follow-up query, and no second `list_all()` call
    duplicating the first. `recent_investigations` is the one
    additional query (`DashboardInvestigationService.get_recent`,
    itself a single `find_recent()` call, already ORDER-BY'd/limited
    server-side) -- reused unchanged rather than re-sorting the
    already-fetched full list here and duplicating that ordering
    logic.

    Reuses `InvestigationSummaryDTO` unchanged for
    `recent_investigations` -- the exact same wire shape
    `get_investigation`/`list_investigations` already return -- rather
    than inventing a second investigation-summary DTO for the
    Dashboard alone.
    """

    def __init__(
        self,
        service: InvestigationService | None = None,
        recent_limit: int = DASHBOARD_RECENT_INVESTIGATIONS_LIMIT,
    ) -> None:
        self._service = service if service is not None else InvestigationService()
        self._dashboard_investigations = DashboardInvestigationService(self._service)
        self._recent_limit = recent_limit

    def handle(self, request: GetDashboardSummaryRequest) -> dict[str, Any]:
        investigations = self._service.list_all()

        metrics = compute_dashboard_metrics(investigations)
        coverage_percent = compute_threat_intel_coverage_percent(investigations)

        recent_investigations = self._dashboard_investigations.get_recent(
            limit=self._recent_limit
        )

        summary = DashboardSummaryDTO(
            metrics=DashboardMetricsDTO(
                total_reports=metrics["report_count"],
                total_iocs=metrics["total_iocs"],
                high_risk_count=metrics["high_risk"],
                threat_intel_coverage_percent=coverage_percent,
            ),
            investigation_status_counts=compute_status_counts(investigations),
            risk_distribution=compute_severity_distribution(investigations),
            ioc_distribution=compute_ioc_distribution(investigations),
            recent_investigations=[
                InvestigationSummaryDTO.from_domain(investigation)
                for investigation in recent_investigations
            ],
        )

        return ok(summary.to_dict())


class GetInvestigationAggregateSummaryCommandHandler:
    """PD-04: cross-investigation aggregate backend commands (see
    docs/phase4/PD04_CROSS_INVESTIGATION_AGGREGATE_COMMANDS.md).

    Deliberately mirrors `GetDashboardSummaryCommandHandler` --same
    single `InvestigationService.list_all()` call, same pure
    `app.services.dashboard_aggregation` functions, no per-
    investigation follow-up query -- but is Dashboard-independent: it
    has no `recent_investigations`/page-specific KPI concept, and adds
    `investigations_by_date` (`compute_investigation_activity_by_date`),
    the one aggregate PD-04 asks for that `get_dashboard_summary` does
    not already provide.
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(
        self, request: GetInvestigationAggregateSummaryRequest
    ) -> dict[str, Any]:
        investigations = self._service.list_all()

        summary = InvestigationAggregateSummaryDTO(
            total_investigations=len(investigations),
            status_counts=compute_status_counts(investigations),
            severity_distribution=compute_severity_distribution(investigations),
            ioc_distribution=compute_ioc_distribution(investigations),
            threat_intel_coverage_percent=compute_threat_intel_coverage_percent(
                investigations
            ),
            investigations_by_date=compute_investigation_activity_by_date(
                investigations
            ),
        )

        return ok(summary.to_dict())


class SearchInvestigationsCommandHandler:
    """Wraps InvestigationService.find_by_report_name -- see command-model.md
    and docs/contracts/PHASE4B_QUERY_INVENTORY.md "Find by report name".

    Replicates the blank-input short-circuit documented and relied upon at
    app.gui.controllers.HistoryController.search_by_report_name (blank
    report_name -> [] without a repository call, since it is unverified
    whether the repository would treat an empty string as a wildcard).
    This handler calls InvestigationService directly rather than importing
    HistoryController, so app.application never depends on app.gui --
    the same dependency-direction rule every other handler in this file
    already follows.
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: SearchInvestigationsRequest) -> dict[str, Any]:
        if not request.report_name.strip():
            return ok([])

        investigations = self._service.find_by_report_name(request.report_name)
        return ok(
            [
                InvestigationSummaryDTO.from_domain(investigation).to_dict()
                for investigation in investigations
            ]
        )


class GetSettingsCommandHandler:
    """Wraps SettingsService.load_settings -- see SOC-IQ Part 2A
    (Settings backend read contract).

    Exposes only the safe subset of `ApplicationSettings`: `theme`,
    `export_directory`, and `virustotal_api_key_configured` (a
    boolean derived from whether a non-empty key came back from the
    secret store). The raw `virustotal_api_key` value is deliberately
    never read off the loaded settings object for the response --
    mirroring `SaveSettingsCommandHandler`'s own "never echo a secret
    into the response envelope" rule, extended here to reads as well
    as writes.
    """

    def __init__(self, service: SettingsService | None = None) -> None:
        self._service = service if service is not None else SettingsService()

    def handle(self, request: GetSettingsRequest) -> dict[str, Any]:
        settings = self._service.load_settings()

        return ok(
            {
                "theme": settings.theme,
                "export_directory": settings.export_directory,
                "virustotal_api_key_configured": bool(settings.virustotal_api_key),
            }
        )


class SaveSettingsCommandHandler:
    """Wraps SettingsService.update_export_directory / .update_theme --
    see command-model.md `save_settings` and
    docs/contracts/PHASE4B_COMMAND_INVENTORY.md.

    MAX19A-F-01: `virustotal_api_key` is no longer one of this
    handler's branches -- `SaveSettingsRequest.__post_init__` now
    rejects that field before construction ever succeeds, so `request
    .virustotal_api_key` is always `None` by the time `handle()` runs.
    Credential writes go through `keystore_set_secret` (Rust, direct
    Tauri IPC) exclusively; this handler only ever wraps the two fields
    that actually round-trip through `config/settings.json`.

    Never echoes the persisted value back in the response: the
    redacted-repr intent documented in
    docs/security/secret-management-model.md ("log-safe, disk-unsafe")
    is deliberately extended here rather than special-cased per field --
    uniform behavior for both fields is simpler and avoids the response
    envelope becoming another place a secret-adjacent value could be
    echoed into a log line.
    """

    def __init__(self, service: SettingsService | None = None) -> None:
        self._service = service if service is not None else SettingsService()

    def handle(self, request: SaveSettingsRequest) -> dict[str, Any]:
        if request.export_directory is not None:
            self._service.update_export_directory(request.export_directory)
            field_name = "export_directory"
        else:
            self._service.update_theme(request.theme)
            field_name = "theme"

        return ok({"field": field_name, "updated": True})


class ExportReportCommandHandler:
    """Wraps InvestigationService.get_by_id + ReportingService's four
    per-format export methods -- see command-model.md `export_report`
    and docs/architecture/16-reporting-architecture.md.

    Reuses the exact same lookup as GetInvestigationCommandHandler /
    GetIocsCommandHandler (same DB round trip, same
    INVESTIGATION_NOT_FOUND semantics) rather than inventing a second
    query path. Format dispatch mirrors
    `MainWindow._export_report`'s own mapping (app/gui/main_window.py)
    exactly: same four formats, same `(investigation, output_path)`
    call shape, no new domain logic -- `ExportReportRequest.__post_init__`
    already rejects any format outside this set, so the `else` branch
    below is unreachable in practice and exists only as a defensive
    mirror of the GUI's own `raise ValueError("Unsupported export
    format...")` fallback.
    """

    def __init__(
        self,
        investigation_service: InvestigationService | None = None,
        reporting_service: ReportingService | None = None,
        timeline_repository: TimelineRepository | None = None,
    ) -> None:
        self._service = (
            investigation_service
            if investigation_service is not None
            else InvestigationService()
        )
        self._reporting_service = (
            reporting_service if reporting_service is not None else ReportingService()
        )
        self._timeline_repository = (
            timeline_repository if timeline_repository is not None else TimelineRepository()
        )

    def handle(self, request: ExportReportRequest) -> dict[str, Any]:
        investigation = self._service.get_by_id(request.investigation_id)

        if investigation is None:
            return fail(
                INVESTIGATION_NOT_FOUND,
                f"No investigation with id {request.investigation_id}.",
            )

        output_path = Path(request.output_path)

        if request.export_format == "html":
            exported_path = self._reporting_service.export_html(
                investigation, output_path
            )
        elif request.export_format == "pdf":
            exported_path = self._reporting_service.export_pdf(
                investigation, output_path
            )
        elif request.export_format == "json":
            exported_path = self._reporting_service.export_json(
                investigation, output_path
            )
        else:
            exported_path = self._reporting_service.export_markdown(
                investigation, output_path
            )

        # A4-P2-P3 Part 4: record the export on the investigation's
        # persisted timeline. A failure here must never fail an
        # already-succeeded export, so it is logged and swallowed --
        # same convention as AnalyzeReportCommandHandler's
        # _record_timeline_event.
        try:
            self._timeline_repository.append(
                TimelineEvent(
                    investigation_id=request.investigation_id,
                    event_type=TimelineEventType.REPORT_EXPORTED,
                    summary=(
                        f"Report exported as {request.export_format.upper()} "
                        f"to '{exported_path.name}'."
                    ),
                    metadata={"export_format": request.export_format},
                )
            )
        except Exception:  # noqa: BLE001 -- do not fail a succeeded export.
            logger.exception(
                "Failed to record report.exported timeline event "
                "for investigation %d",
                request.investigation_id,
            )

        return ok(
            {
                "investigation_id": request.investigation_id,
                "export_format": request.export_format,
                "output_path": str(exported_path),
            }
        )


class ExportInvestigationsCsvCommandHandler:
    """PD-08-P5.1: bulk investigation-history CSV export.

    Wraps `InvestigationService.list_all()` -- the exact same query
    `ListInvestigationsCommandHandler` already uses -- plus the new
    application-layer filter/serialize helpers in
    `app.services.investigation_csv_export`. See
    `ExportInvestigationsCsvRequest`'s docstring (app/application/dto.py)
    and docs/phase4/PD08_P5_1_BULK_CSV_EXPORT_BACKEND_CONTRACT.md for the
    full forensic/contract rationale.

    Deliberately does NOT record a timeline event. `report.exported`
    (see `ExportReportCommandHandler` above) is scoped to a single
    investigation's own timeline; a bulk, cross-investigation export has
    no single investigation to attach an event to, and Timeline is a
    frozen workstream for this part (PD-08-P5.1 Part 12) -- inventing a
    new cross-investigation timeline concept here would be exactly the
    kind of scope creep that part forbids.

    No new repository query and no new database access path: both the
    data source (`list_all()`) and its ordering (`ORDER BY id DESC`,
    see `InvestigationRepository.list_all`) are reused completely
    unchanged.
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: ExportInvestigationsCsvRequest) -> dict[str, Any]:
        investigations = self._service.list_all()

        filtered_investigations = filter_investigations_by_search_text(
            investigations, request.search
        )

        output_path = Path(request.output_path)

        exported_path = export_investigations_history_csv(
            filtered_investigations, output_path
        )

        return ok(
            {
                "output_path": str(exported_path),
                "row_count": len(filtered_investigations),
            }
        )


class EnrichIocCommandHandler:
    """Wraps ThreatIntelService.lookup_indicator -- see command-model.md
    `enrich_ioc` and the confirmed existing call site at
    `app.gui.pages.threat_intel_page._VirusTotalLookupWorker.run`
    (Phase 4C, Stage 2's interactive single-IOC lookup).

    `lookup_indicator` itself deliberately propagates every failure
    (validation, rate limit, invalid key, provider error) as a raised
    exception rather than an in-band result -- its own docstring:
    "Unlike enrich_results, this does not catch and count errors ...
    meant for interactive, single-indicator callers." This handler still
    does no *translation* of its own -- it re-raises unchanged after
    publishing the `ti.enrichment.failed` lifecycle event below, so
    `dispatch()`'s existing generic exception boundary still performs the
    actual `code_for_exception` translation exactly as before (no new
    error category is introduced here; `code_for_exception` is only
    consulted here to put the same code into the failed event's payload
    that dispatch() will independently arrive at).

    Per docs/phase4/PHASE4D_SSE_PART2_IMPLEMENTATION.md (Stages 4-5):

    - The blocking call to `ThreatIntelService.lookup_indicator` (which
      internally bridges an async provider call via `asyncio.run()`, see
      `app/application/execution.py`'s module docstring for the full
      chain) now runs via `run_blocking()`, on a dedicated worker thread,
      rather than inline on whatever thread called `.handle()`. This is
      the smallest fix for a pre-existing hazard: `asyncio.run()` raises
      `RuntimeError` if called on a thread that already has a running
      event loop (e.g. a future FastAPI request coroutine's thread).
      `ThreatIntelService` itself is unmodified.
    - `ti.enrichment.started` / `.completed` / `.failed` lifecycle events
      are published (to both the returned `EventCollector` and the
      shared `EventBroker`), mirroring `AnalyzeReportCommandHandler`'s
      existing `analysis.*` event shape and this project's established
      event-naming convention (`frontend/src/shared/events/types.ts`
      already names exactly these three event strings).
    """

    def __init__(
        self,
        service: ThreatIntelService | None = None,
        broker: EventBroker | None = None,
    ) -> None:
        self._service = service if service is not None else ThreatIntelService()
        self._broker = broker if broker is not None else get_application_broker()

    def handle(
        self, request: EnrichIocRequest
    ) -> tuple[dict[str, Any], EventCollector]:
        collector = EventCollector()
        correlation_id = new_correlation_id("ti")

        def _publish(event: Event) -> None:
            # Additive: the collector (test/local-inspection sink) and the
            # broker (live SSE-future sink) each receive the SAME Event
            # object exactly once per call site below -- never two
            # separately-constructed events for one logical occurrence,
            # so neither sink can see a duplicate the other doesn't.
            collector.publish(event)
            self._broker.publish(event)

        _publish(
            Event.create(
                "ti.enrichment.started",
                correlation_id,
                {"ioc_type": request.ioc_type, "value": request.value},
            )
        )

        try:
            # Runs on a dedicated worker thread -- see module docstring
            # in app/application/execution.py for why this is required
            # and why it is safe regardless of the calling thread's own
            # event-loop state.
            result = run_blocking(
                self._service.lookup_indicator, request.ioc_type, request.value
            )
        except Exception as error:  # noqa: BLE001 -- deliberately broad:
            # every failure mode must produce a ti.enrichment.failed event
            # before propagating; dispatch()'s outer boundary still does
            # the actual translation to a fail() envelope, unchanged.
            code = code_for_exception(error)
            message = str(error)
            _publish(
                Event.create(
                    "ti.enrichment.failed",
                    correlation_id,
                    {
                        "ioc_type": request.ioc_type,
                        "value": request.value,
                        "code": code,
                        "message": message,
                    },
                )
            )
            raise

        _publish(
            Event.create(
                "ti.enrichment.completed",
                correlation_id,
                {
                    "ioc_type": request.ioc_type,
                    "value": request.value,
                    # The full verdict-annotated result (never a secret --
                    # lookup_indicator's return shape never carries the
                    # provider API key), so a future SSE/frontend consumer
                    # can render the outcome without a second provider
                    # call (PHASE4D_SSE_PART2_IMPLEMENTATION.md Stage 5).
                    "result": result,
                },
            )
        )

        return ok(result), collector


class DeleteInvestigationCommandHandler:
    """Wraps InvestigationService.delete -- see command-model.md and
    docs/contracts/PHASE4B_COMMAND_INVENTORY.md `delete_investigation`.

    Per the inventory, a missing id is a normal `False` result, not an
    error -- InvestigationService.delete already returns bool rather than
    raising for that case, and this handler preserves that domain
    semantic unchanged rather than reinterpreting "nothing to delete" as
    INVESTIGATION_NOT_FOUND.
    """

    def __init__(self, service: InvestigationService | None = None) -> None:
        self._service = service if service is not None else InvestigationService()

    def handle(self, request: DeleteInvestigationRequest) -> dict[str, Any]:
        deleted = self._service.delete(request.investigation_id)
        return ok(
            {
                "investigation_id": request.investigation_id,
                "deleted": deleted,
            }
        )


class AnalyzeReportCommandHandler:
    """
    Wraps app.analyzer.analyze_report -- the one long-running command this
    phase implements. See docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S7
    for why this reference implementation returns synchronously (collecting
    events rather than streaming them over a live SSE connection that does
    not exist yet in this phase).

    A4-P2-P3 Part 6: also records `correlation.completed` for a newly
    analyzed investigation, using the same `CorrelationService` instance
    `GetInvestigationCommandHandler` already calls unmodified (see that
    handler's own docstring) -- no second correlation implementation is
    introduced. This closes the last unwired member of
    `TimelineEventType`'s nine-item vocabulary (Parts 4/5 wired the other
    eight); it does not add a new event type, a new option gate, or a
    new service.

    R1: `domain_analyze_report` itself now runs via `run_blocking()`
    (app/application/execution.py) rather than inline on `.handle()`'s
    own calling thread -- see the inline comment at that call site in
    `handle()` below for why this is required once `.handle()` is
    reached from `app/api/app.py`'s `async def run_command()` (a
    thread that already has a running asyncio event loop).
    """

    def __init__(
        self,
        broker: EventBroker | None = None,
        timeline_repository: TimelineRepository | None = None,
        correlation_service: CorrelationService | None = None,
    ) -> None:
        self._broker = broker if broker is not None else get_application_broker()
        self._timeline_repository = (
            timeline_repository if timeline_repository is not None else TimelineRepository()
        )
        self._correlation_service = (
            correlation_service if correlation_service is not None else CorrelationService()
        )

    def _record_timeline_event(
        self,
        investigation_id: int,
        event_type: TimelineEventType,
        summary: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """A4-P2-P3 Part 4: append one persisted TimelineEvent.

        Deliberately a thin, explicit call at one already-identified
        pipeline milestone -- not a generic hook invoked for every
        internal step -- per the Part 4 brief's "timeline generation
        must remain controlled and explicit" (S11). A failure to
        record a timeline event must never fail the analysis itself
        (the investigation is already durably saved by this point),
        so this is logged and swallowed rather than propagated.
        """

        try:
            self._timeline_repository.append(
                TimelineEvent(
                    investigation_id=investigation_id,
                    event_type=event_type,
                    summary=summary,
                    metadata=metadata or {},
                )
            )
        except Exception:  # noqa: BLE001 -- see docstring: never fail
            # the analysis command because timeline recording failed.
            logger.exception(
                "Failed to record timeline event %s for investigation %d",
                event_type.value,
                investigation_id,
            )

    def handle(
        self, request: AnalyzeReportRequest
    ) -> tuple[dict[str, Any], EventCollector]:
        collector = EventCollector()
        correlation_id = new_correlation_id("an")

        def _publish(event: Event) -> None:
            # Additive per PHASE4D_SSE_PART2_IMPLEMENTATION.md Stage 6: the
            # collector and broker each receive the SAME Event exactly
            # once per call site below -- one command execution can never
            # produce a duplicate broker event this way.
            collector.publish(event)
            self._broker.publish(event)

        if not _report_path_is_valid(request.report_path):
            error = fail(
                *_report_not_found(request.report_path),
            )
            _publish(
                Event.create(
                    "analysis.failed",
                    correlation_id,
                    {"code": error["error"]["code"], "message": error["error"]["message"]},
                )
            )
            return error, collector

        # Part 2A established the validated options on the request DTO and
        # forwarded them into the event/response envelope; Part 2B forwards
        # the same dict into domain_analyze_report below, which now
        # genuinely gates each pipeline stage on it (app/analyzer.py).
        options = request.options.to_dict()

        _publish(
            Event.create(
                "analysis.started",
                correlation_id,
                {"report_path": request.report_path, "options": options},
            )
        )

        def on_progress(percent: int, message: str) -> None:
            _publish(
                Event.create(
                    "analysis.progress",
                    correlation_id,
                    {"percent": percent, "message": message},
                )
            )

        try:
            # R1 fix: `domain_analyze_report` internally reaches
            # `ThreatIntelService._lookup_raw`, which bridges its
            # provider's async `lookup_raw()` onto a synchronous caller
            # via `asyncio.run(...)` (see app/application/execution.py's
            # module docstring for the full chain). `app/api/app.py`'s
            # `POST /commands/{name}` route is `async def`, so calling
            # `domain_analyze_report` inline here would run it on the
            # request coroutine's own thread -- the same thread already
            # running that route's event loop -- and hit `RuntimeError:
            # asyncio.run() cannot be called from a running event loop`
            # the moment threat-intel enrichment is reached.
            #
            # `run_blocking()` is the existing, narrow boundary this
            # codebase already established for exactly this hazard
            # (`EnrichIocCommandHandler.handle()`'s own call to
            # `ThreatIntelService.lookup_indicator` above -- see that
            # handler's docstring and execution.py's module docstring).
            # It runs the entire synchronous `domain_analyze_report` call
            # -- `asyncio.run()` bridge included -- on a dedicated worker
            # thread that never has a running event loop of its own, and
            # blocks this (calling) thread on the result, exactly like a
            # normal synchronous call. `domain_analyze_report`'s
            # signature, `on_progress` callback, and return shape are
            # unchanged; only which thread executes it changes.
            #
            # `on_progress` (and therefore `_publish`, which appends to
            # `collector` and publishes to `self._broker`) now runs on
            # that worker thread rather than this one -- safe here
            # because `EventBroker`/`Subscription` are explicitly
            # documented as safe for cross-thread `publish()` (see
            # broker.py's `Subscription` docstring), and `collector` is
            # only ever touched sequentially: this calling thread is
            # blocked on `run_blocking()`'s `future.result()` for the
            # entire span the worker thread could call `on_progress`, so
            # there is no concurrent access to `collector.events`.
            result = run_blocking(
                domain_analyze_report,
                Path(request.report_path),
                progress_callback=on_progress,
                options=options,
            )
        except Exception as error:  # noqa: BLE001 -- deliberately broad: every
            # domain failure must become a *.failed event + error envelope,
            # never an unhandled exception reaching the transport layer.
            logger.exception("analyze_report failed for %r", request.report_path)
            code = code_for_exception(error)
            message = str(error)
            _publish(
                Event.create(
                    "analysis.failed",
                    correlation_id,
                    {"code": code, "message": message},
                )
            )
            return fail(code, message), collector

        investigation = result["investigation"]
        summary = InvestigationSummaryDTO.from_domain(investigation).to_dict()

        # A4-P2-P3 Part 4: record the persisted investigation timeline
        # for a genuinely NEW investigation only -- a duplicate/"existing"
        # result (result["existing"] is True) means none of these facts
        # newly happened this call, so nothing is appended for it (the
        # original investigation_created/... events already exist on
        # its timeline from when it was first analyzed).
        if (
            investigation.investigation_id is not None
            and not result.get("existing", False)
        ):
            investigation_id = investigation.investigation_id

            self._record_timeline_event(
                investigation_id,
                TimelineEventType.INVESTIGATION_CREATED,
                f"Investigation created for '{investigation.report_name}'.",
            )
            self._record_timeline_event(
                investigation_id,
                TimelineEventType.REPORT_IMPORTED,
                f"Report '{investigation.report_name}' imported for analysis.",
            )
            self._record_timeline_event(
                investigation_id,
                TimelineEventType.ANALYSIS_STARTED,
                "SOC-IQ analysis pipeline started.",
                metadata={"options": options},
            )

            if options.get("extract_iocs", True):
                ioc_count = sum(
                    len(values) for values in investigation.iocs.values()
                )
                self._record_timeline_event(
                    investigation_id,
                    TimelineEventType.IOC_EXTRACTION_COMPLETED,
                    f"IOC extraction completed ({ioc_count} indicator(s)).",
                    metadata={"ioc_count": ioc_count},
                )

            if options.get("enrich_ti", True):
                ti_status = investigation.threat_intelligence.get("status")
                self._record_timeline_event(
                    investigation_id,
                    TimelineEventType.TI_ENRICHMENT_COMPLETED,
                    "Threat intelligence enrichment completed.",
                    metadata={"status": ti_status} if ti_status else {},
                )

            if options.get("score_risk", True):
                self._record_timeline_event(
                    investigation_id,
                    TimelineEventType.RISK_CALCULATED,
                    f"Risk score calculated: {investigation.risk_score} "
                    f"({investigation.severity}).",
                    metadata={
                        "risk_score": investigation.risk_score,
                        "severity": investigation.severity,
                    },
                )

            # A4-P2-P3 Part 6: not gated by an `options` flag -- unlike
            # extract_iocs/enrich_ti/score_risk, correlation has no
            # existing option to gate on (GetInvestigationCommandHandler
            # already runs it unconditionally for every view), so this
            # mirrors that same unconditional behavior rather than
            # inventing a new option. The CorrelationService call itself
            # is guarded separately from _record_timeline_event's own
            # try/except, since a correlation failure here must not fail
            # an already-succeeded analysis any more than a timeline-
            # write failure would.
            try:
                correlation_report = self._correlation_service.correlate(investigation)
            except Exception:  # noqa: BLE001 -- do not fail a succeeded analysis.
                logger.exception(
                    "Failed to compute correlation report for "
                    "investigation %d while recording its timeline",
                    investigation_id,
                )
            else:
                self._record_timeline_event(
                    investigation_id,
                    TimelineEventType.CORRELATION_COMPLETED,
                    "Correlation completed "
                    f"({correlation_report.summary.relationship_count} "
                    "relationship(s) found within this investigation's "
                    "own evidence).",
                    metadata={
                        "relationship_count": correlation_report.summary.relationship_count,
                        "correlated_evidence_count": (
                            correlation_report.summary.correlated_evidence_count
                        ),
                    },
                )

            self._record_timeline_event(
                investigation_id,
                TimelineEventType.ANALYSIS_COMPLETED,
                "SOC-IQ analysis pipeline completed.",
            )

        _publish(
            Event.create(
                "analysis.completed",
                correlation_id,
                {"existing": result.get("existing", False), "investigation": summary},
                investigation_id=investigation.investigation_id,
            )
        )

        response = ok(
            {
                "correlation_id": correlation_id,
                "investigation": summary,
                "existing": result.get("existing", False),
                "options": options,
            }
        )
        return response, collector


def _report_not_found(report_path: str) -> tuple[str, str]:
    from app.application.errors import REPORT_NOT_FOUND

    return REPORT_NOT_FOUND, f"Report path is missing or invalid: {report_path!r}"


# ---------------------------------------------------------------------------
# Dispatch table: raw dict payload in, response envelope dict out.
#
# This is the seam app/api/app.py's `POST /commands/{name}` route calls
# through (docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md S6.4) -- kept
# transport-agnostic on purpose so it is exercised directly by
# tests/test_application_layer.py without any HTTP framework involved.
# ---------------------------------------------------------------------------


def dispatch(name: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "get_investigation":
            request = GetInvestigationRequest(**payload)
            return GetInvestigationCommandHandler().handle(request)

        if name == "get_iocs":
            request = GetIocsRequest(**payload)
            return GetIocsCommandHandler().handle(request)

        if name == "get_threat_intelligence":
            request = GetThreatIntelligenceRequest(**payload)
            return GetThreatIntelligenceCommandHandler().handle(request)

        if name == "get_investigation_integrity":
            request = GetInvestigationIntegrityRequest(**payload)
            return GetInvestigationIntegrityCommandHandler().handle(request)

        if name == "get_investigation_provenance":
            request = GetInvestigationProvenanceRequest(**payload)
            return GetInvestigationProvenanceCommandHandler().handle(request)

        if name == "get_investigation_risk_explanation":
            request = GetInvestigationRiskExplanationRequest(**payload)
            return GetInvestigationRiskExplanationCommandHandler().handle(request)

        if name == "get_timeline":
            request = GetTimelineRequest(**payload)
            return GetTimelineCommandHandler().handle(request)

        if name == "get_settings":
            request = GetSettingsRequest(**payload)
            return GetSettingsCommandHandler().handle(request)

        if name == "save_settings":
            request = SaveSettingsRequest(**payload)
            return SaveSettingsCommandHandler().handle(request)

        if name == "list_investigations":
            request = ListInvestigationsRequest(**payload)
            return ListInvestigationsCommandHandler().handle(request)

        if name == "get_dashboard_summary":
            request = GetDashboardSummaryRequest(**payload)
            return GetDashboardSummaryCommandHandler().handle(request)

        if name == "get_investigation_aggregate_summary":
            request = GetInvestigationAggregateSummaryRequest(**payload)
            return GetInvestigationAggregateSummaryCommandHandler().handle(request)

        if name == "delete_investigation":
            request = DeleteInvestigationRequest(**payload)
            return DeleteInvestigationCommandHandler().handle(request)

        if name == "export_report":
            request = ExportReportRequest(**payload)
            return ExportReportCommandHandler().handle(request)

        if name == "export_investigations_csv":
            request = ExportInvestigationsCsvRequest(**payload)
            return ExportInvestigationsCsvCommandHandler().handle(request)

        if name == "search_investigations":
            request = SearchInvestigationsRequest(**payload)
            return SearchInvestigationsCommandHandler().handle(request)

        if name == "enrich_ioc":
            request = EnrichIocRequest(**payload)
            response, _collector = EnrichIocCommandHandler().handle(request)
            return response

        if name == "analyze_report":
            request = AnalyzeReportRequest(**payload)
            response, _collector = AnalyzeReportCommandHandler().handle(request)
            return response

        from app.application.errors import UNKNOWN_COMMAND

        return fail(UNKNOWN_COMMAND, f"No such command: {name!r}")

    except CommandValidationError as error:
        return fail(error.code, error.message)
    except TypeError as error:
        # dataclass __init__ rejects unexpected/missing keys with a TypeError.
        from app.application.errors import INVALID_COMMAND_PAYLOAD

        return fail(INVALID_COMMAND_PAYLOAD, str(error))
    except Exception as error:  # noqa: BLE001 -- deliberately broad, mirroring
        # AnalyzeReportCommandHandler's own internal boundary (see above): every
        # domain failure from a command handler must become a translated error
        # envelope, never a raised exception reaching the transport layer. Only
        # analyze_report did this internally before; get_investigation and
        # list_investigations had no equivalent, so an unexpected domain
        # exception (e.g. DatabaseError) previously propagated uncaught out of
        # dispatch() -- a real gap, not a hypothetical one (reproduced with
        # InvestigationService.get_by_id raising DatabaseError). This closes it
        # at the one seam shared by all three commands, per the invariant
        # app/application/responses.py's docstring already states: "never a
        # bare domain object and never a raised exception for expected failure
        # modes (only for genuine bugs)."
        logger.exception("Unhandled exception in command %r", name)
        return fail(code_for_exception(error), str(error))


COMMAND_HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "get_investigation": lambda payload: dispatch("get_investigation", payload),
    "get_iocs": lambda payload: dispatch("get_iocs", payload),
    "get_threat_intelligence": lambda payload: dispatch("get_threat_intelligence", payload),
    "get_investigation_integrity": lambda payload: dispatch(
        "get_investigation_integrity", payload
    ),
    "get_investigation_provenance": lambda payload: dispatch(
        "get_investigation_provenance", payload
    ),
    "get_investigation_risk_explanation": lambda payload: dispatch(
        "get_investigation_risk_explanation", payload
    ),
    "get_settings": lambda payload: dispatch("get_settings", payload),
    "save_settings": lambda payload: dispatch("save_settings", payload),
    "list_investigations": lambda payload: dispatch("list_investigations", payload),
    "get_dashboard_summary": lambda payload: dispatch("get_dashboard_summary", payload),
    "get_investigation_aggregate_summary": lambda payload: dispatch(
        "get_investigation_aggregate_summary", payload
    ),
    "get_timeline": lambda payload: dispatch("get_timeline", payload),
    "delete_investigation": lambda payload: dispatch("delete_investigation", payload),
    "search_investigations": lambda payload: dispatch("search_investigations", payload),
    "analyze_report": lambda payload: dispatch("analyze_report", payload),
    "export_report": lambda payload: dispatch("export_report", payload),
    "export_investigations_csv": lambda payload: dispatch(
        "export_investigations_csv", payload
    ),
    "enrich_ioc": lambda payload: dispatch("enrich_ioc", payload),
}
