# Phase 4B — Controller / Service Extraction Inventory

**Status:** Phase 4B (Source-Verified). Supersedes speculative Phase 4A claims about
`app/gui/controllers/`, `app/gui/services/`, and `app/services/`.

**Method:** Every file listed below was read in full. Nothing here is inferred from
filenames. Qt coupling was verified by `grep -l "PySide6"` against each file plus manual
read of imports.

Target layer values: `domain`, `application`, `repository`, `API`, `presentation`, `remove`,
`unknown`.
Migration action values: `PRESERVE`, `EXTRACT`, `ADAPT`, `SPLIT`, `REMOVE`, `INVESTIGATE`.

## `app/gui/controllers/`

| Current File | Class/Function | Responsibility | Qt Coupling | Business Logic | Data Access | Target Layer | Migration Action | Risk | Tests |
|---|---|---|---|---|---|---|---|---|---|
| `analyze_controller.py` | `AnalyzeController.analyze` | Validates report path, delegates to `AnalysisService`, raises `FileNotFoundError` on invalid input | **None** | B (input validation is application-layer, not domain) | None (delegates) | application | EXTRACT (move as-is; class body is already Qt-free) | Low | Indirect only — no direct unit test found for this class; exercised transitively via `AnalysisWorker`/GUI tests |
| `analyze_controller.py` | `AnalyzeController.validate_report` | Existence/is-file check on a path string | **None** | E (validation) | None | application | EXTRACT | Low | Same as above |
| `history_controller.py` | `HistoryController.get_recent_investigations` | Delegates to `InvestigationService.find_recent`, logs+re-raises on failure | **None** | B/I (error-handling policy: never mask a failure as empty result) | Indirect (via service) | application | EXTRACT | Low | No direct test found |
| `history_controller.py` | `HistoryController.search_by_report_name` | Blank-name short-circuit, delegates to service, logs+re-raises | **None** | B/E/I | Indirect | application | EXTRACT | Low | No direct test found |
| `history_controller.py` | `HistoryController.delete_investigation` | Delegates to `InvestigationService.delete`, logs+re-raises | **None** | B/I | Indirect | application | EXTRACT | **Medium — dead capability** (see §6 of Findings: never invoked from any GUI page/button) | No direct test found |
| `history_controller.py` | `HistoryController.get_investigation` | Delegates to `get_by_id`, logs+re-raises | **None** | B/I | Indirect | application | EXTRACT | Low | No direct test found |
| `history_controller.py` | `HistoryController.get_total_investigations` | Delegates to `count()`, logs+re-raises | **None** | B/I | Indirect | application | EXTRACT | Low | No direct test found |
| `dashboard_controller.py` | `DashboardController.__init__` | Instantiates and wires 6 dashboard services + `SystemHealthService` | **None** | D-analog (composition root, no Qt) | None | application | EXTRACT (this is a use-case composition root, not a widget) | Low | No direct test found |
| `dashboard_controller.py` | `get_summary` / `get_threat_status` / `get_latest_investigation` / `get_recent_investigations` / `get_dashboard_timeline` / `get_ioc_distribution` / `get_system_status` / `get_threat_feed` | Each is a thin delegate to one dashboard service, with logging + re-raise | **None** | I (uniform "never mask failure" policy, documented explicitly in the class docstring) | Indirect | application (query side) | EXTRACT | Low | No direct test — covered transitively via `tests/test_dashboard_services.py`, which tests the underlying services, not this controller |

**Finding:** All three controller files are already 100% free of `PySide6`/Qt imports.
Nothing here is "GUI orchestration" (category D) in the PySide6 sense — no `QObject`,
`Signal`, `Slot`, widget, or event-loop reference exists anywhere in `app/gui/controllers/`.
They are constructor-injectable, framework-independent Python classes that happen to live
under the `app/gui/` package path. The correct Phase 4B classification is that the
**package location is wrong, not the code**. `EXTRACT` here means "move the file", not
"rewrite the logic" — no method has mixed responsibility requiring a split.

## `app/gui/services/`

| Current File | Class/Function | Responsibility | Qt Coupling | Business Logic | Data Access | Target Layer | Migration Action | Risk | Tests |
|---|---|---|---|---|---|---|---|---|---|
| `analysis_service.py` | `AnalysisService.analyze` | Pure pass-through to `app.analyzer.analyze_report` | **None** | None (deliberate — docstring: "never performs analysis itself") | None (delegates) | application | EXTRACT (or REMOVE as a redundant indirection layer — see note) | Low | No direct test; covered transitively |
| `ioc_detail_context.py` | `build_investigation_threat_intel_overview` and related functions | Builds per-IOC significance/context data from an `Investigation`, using `app.gui.utils.ioc_significance` and `app.scoring.engine` | **None** | C/F (transformation of domain data into a display-ready shape) | None (read-only, operates on in-memory `Investigation`) | application (query/view-model source) | EXTRACT — but see coupling note below | Medium (consumed by `app/services/risk_explanation_service.py`, a **backend** file — see §6 Findings) | `tests/test_ioc_detail_context.py` (14 tests), `tests/gui/test_ioc_detail_context_url.py` (12 tests) |
| `investigation_correlation_context.py` | Correlation-context builder functions | Maps `CorrelationReport`/`CorrelationResult` (from `app/services/correlation_models.py`) into a presentation-friendly shape, using `ioc_type_title` | **None** | F (transformation only) | None | application/presentation boundary (view-model) | EXTRACT | Low | No direct test file found by name; check for indirect coverage in workspace tests before migration |

**Note on `analysis_service.py`:** its docstring states it exists so "the GUI interacts only
with this service instead of calling the backend analysis engine directly" — i.e. it is an
indirection layer with zero added logic. In the target Application layer this collapses into
a single `analyze_report` command handler; `AnalysisService` itself does not need to survive
as a distinct class. Recommend `REMOVE` (fold into the future `analyze_report` command
handler) rather than `EXTRACT` as a separate file — flagged here rather than decided, per the
"do not invent target locations without evidence" instruction; final call belongs to Phase
4C/4D design, not this inventory.

**Duplication check (explicitly required by scope §4, UNKNOWN #5):** No functional
duplication was found between `app/services/*` and `app/gui/services/*`. They are
complementary, not overlapping: `app/services/ioc_detail_context.py` and
`investigation_correlation_context.py` both build *presentation* shapes on top of results
produced by `app/services/correlation_service.py` and `app/services/risk_explanation_service.py`
respectively — one produces the domain-ish computation, the other reshapes it for display.
The one real defect is architectural direction, not duplication: `app/services/
risk_explanation_service.py` (a backend file) importing *from* `app/gui/services/
ioc_detail_context.py` and `app/services/ioc_significance.py` (GUI-package files) — see
`PHASE4B_ARCHITECTURAL_FINDINGS.md` §Confirmed for the full trace.

## `app/services/` (already outside `app/gui/`, included per scope §4 UNKNOWN #3)

| Current File | Class/Function | Responsibility | Qt Coupling | Business Logic | Data Access | Target Layer | Migration Action | Risk | Tests |
|---|---|---|---|---|---|---|---|---|---|
| `correlation_models.py` | `CorrelatedEvidence`, `CorrelationResult`, `CorrelationSummary`, `CorrelationReport` (dataclasses) | Domain data shapes for correlation results | None (docstring explicitly forbids PySide6 import) | Domain models | None | domain | PRESERVE | Low | Covered via `test_correlation_service.py` |
| `correlation_service.py` | `CorrelationService.correlate` + 4 private `_correlate_*` helpers | Detects duplicate evidence, domain/URL/host overlaps, and threat-intel links across an investigation's IOCs | None | Domain logic (pure function of an `Investigation`) | None (read-only) | domain | PRESERVE | Low | `tests/test_correlation_service.py` (25 tests) |
| `dashboard_investigation_service.py` | `DashboardInvestigationService.get_latest` / `get_recent` | Query wrapper over `InvestigationService` for dashboard "latest/recent" views | None | Query/read logic | Indirect (via `InvestigationService` → repository) | application (query service) | PRESERVE (already correctly placed) | Low | `tests/test_dashboard_services.py` |
| `dashboard_ioc_distribution_service.py` | `DashboardIOCDistributionService.get_distribution` | Counts IOC types across investigations using `collections.Counter` | None | Aggregation/query logic | Indirect | application (query service) | PRESERVE | Low | `tests/test_dashboard_services.py` |
| `dashboard_statistics_service.py` | `DashboardStatisticsService.get_summary` | Aggregates summary metrics | None | Aggregation/query logic | Indirect | application (query service) | PRESERVE | Low | `tests/test_dashboard_services.py` |
| `dashboard_threat_feed_service.py` | `DashboardThreatFeedService.get_feed` | Builds recent threat-intel feed entries | None | Query/transform logic | Indirect | application (query service) | PRESERVE | Low | `tests/test_dashboard_services.py` |
| `dashboard_threat_service.py` | `DashboardThreatService.get_threat_status` | Computes overall dashboard threat level + `BadgeType` | None | Domain-ish scoring/classification logic on top of stored investigations | Indirect | application (query service) | PRESERVE | Low | `tests/test_dashboard_services.py` |
| `dashboard_timeline_service.py` | `DashboardTimelineService.get_timeline`, `_icon_for_severity` | Builds `TimelineEvent` list from investigations | None | Query/transform + presentation-icon mapping (`_icon_for_severity` is arguably presentation, not application) | Indirect | application (query service), with `_icon_for_severity` flagged `presentation` | SPLIT (icon mapping should move to a presentation-layer mapper, everything else `PRESERVE`) | Low | `tests/test_dashboard_services.py` |
| `models.py` | `BadgeType` (Enum), `TimelineEvent` (dataclass) | Shared value types for dashboard services | None (docstring explicitly notes it avoids PySide6) | Domain/application value objects | None | application (DTO-ish, not persisted) | PRESERVE | Low | Covered transitively |
| `risk_explanation_models.py` | `IocCategoryContribution`, `RiskExplanation` | Value objects for risk explanations | None | Domain/application value objects | None | application | PRESERVE | Low | `tests/test_risk_explanation_service.py` |
| `risk_explanation_service.py` | `RiskExplanationService.explain` + 5 private helpers | Builds a human-readable "why this risk score" explanation from an existing `Investigation`'s score/evidence/TI/correlations. Explicitly documented as read-only and non-authoritative — does **not** compute risk itself (`RiskScoringEngine` remains sole source of truth) | None | Domain/application explanation logic | None (read-only) | application | PRESERVE, **but** its import of `app.gui.services.ioc_detail_context` / `app.gui.utils.ioc_significance` must be resolved first — see Findings | **Medium — architecturally invalid dependency direction** | `tests/test_risk_explanation_service.py` (24 tests) |
| `system_health_service.py` | `SystemHealthService.get_status` + 4 private `_*_status` helpers | Checks DB/VirusTotal/repository/analysis-engine health | None | Application/infrastructure health-check logic; uses `sqlite3` directly (not through the repository) for one check | Direct (`sqlite3`, `DatabaseConnection`) | application | PRESERVE | Low | Not found in the four `app/services` test files listed by name in scope §4 — flagged for coverage-gap check in `PHASE4B_TEST_COVERAGE_GAPS.md` |

All 12 files under `app/services/` are confirmed 100% Qt-free by direct inspection (the three
`grep` hits for the literal string `PySide6` in this directory are documentation comments
stating the *absence* of the import, not the import itself).
