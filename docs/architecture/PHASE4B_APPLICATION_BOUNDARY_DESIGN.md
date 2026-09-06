# Phase 4B — Application Boundary Design

**Status:** Phase 4B (Source-Verified). Defines DOMAIN / APPLICATION / API / PRESENTATION /
PERSISTENCE boundaries from the actual code read this phase, not copied from the Phase 4A
master plan.

## Layer definitions (as actually observed in source, not aspirational)

**DOMAIN** — Pure business rules and models, no I/O, no framework dependency.
**APPLICATION** — Use cases / orchestration / commands and queries that coordinate domain +
persistence.
**API** — Transport and DTO validation only (not yet built; Phase 4C+).
**PRESENTATION** — React/Qt UI concerns (widgets, pages, view-model shaping for display).
**PERSISTENCE** — Repository implementation (SQLite access).

## Where each currently-existing service/controller belongs

### DOMAIN

- `app/services/correlation_models.py` (dataclasses) — pure value objects.
- `app/services/correlation_service.py` — pure function of an `Investigation`, no I/O.
- `app.gui.utils.ioc_significance` functions — pure functions wrapping `RiskScoringEngine`,
  zero I/O, zero Qt. **Currently mis-located** under `app/gui/utils/`; belongs in domain.
- `app.scoring.engine.RiskScoringEngine` (not re-read this pass, but its status as sole
  authority for risk score/severity is stated repeatedly and explicitly elsewhere in the
  codebase — treated as DOMAIN by reference).
- `app.extractor` (`extract_iocs`, `read_report`) — not re-read this pass; treated as DOMAIN
  by reference from its usage and existing test file name.

### APPLICATION

- `app.analyzer.analyze_report` — the primary use case / command orchestrator (read →
  extract → duplicate-check → enrich → score → persist → return). Currently a bare function,
  not a class — functionally already at the right layer, just not yet wrapped in a formal
  command-handler shape.
- `AnalyzeController`, `HistoryController`, `DashboardController` (`app/gui/controllers/`) —
  confirmed 100% Qt-free this phase; belong here once relocated out of `app/gui/`.
- `AnalysisService` (`app/gui/services/analysis_service.py`) — currently a pure pass-through
  with no independent logic; candidate to collapse into the `analyze_report` command handler
  rather than surviving as its own class (see Controller/Service Inventory).
- All 6 `app/services/dashboard_*.py` classes — already correctly placed; these are the
  application-layer query services for the dashboard.
- `app.services.system_health_service.SystemHealthService` — application-layer health-check
  orchestration; already correctly placed, but see Test Coverage Gaps (untested).
- `app.services.risk_explanation_service.RiskExplanationService` — application-layer
  explanation logic; already correctly placed under `app/services/`, but its dependency on
  two GUI-package modules must be resolved before it can be considered a clean application
  boundary (see Architectural Findings).
- `app.database.service.InvestigationService` — the application-layer facade over the
  repository; already correctly placed and shaped.
- `app.gui.services.ioc_detail_context` functions — application-layer query logic (builds a
  view-model-adjacent but not purely presentational shape from domain data); currently
  mis-located under `app/gui/services/`.

### PRESENTATION

- `app.gui.services.investigation_correlation_context` — reshapes a `CorrelationReport` into
  a display-specific structure; this is the one file in the audited `app/gui/services/`
  directory that is genuinely presentation logic wearing an "application service" name, not
  just a misplaced application service.
- `DashboardTimelineService._icon_for_severity` (one method, not the whole class) — severity→
  icon-name mapping is a presentation concern embedded inside an otherwise-application-layer
  query service; flagged for `SPLIT` in the Controller/Service Inventory.
- `DashboardThreatService`'s return of `BadgeType` (an enum defined in `app/services/
  models.py`) — the enum's *existence* (threat status classification) is application-layer,
  but a UI badge-color mapping for that enum, if one exists in a widget file, is presentation
  and was not traced this pass (widget files are outside stated scope).
- Everything under `app/gui/pages/`, `app/gui/widgets/`, `app/gui/components/`, `app/gui/
  design/` — not individually re-read this pass (outside stated Phase 4B scope), but
  presentation by construction (Qt widgets).

### PERSISTENCE

- `app.database.connection.DatabaseConnection` — connection lifecycle, WAL/pragma config.
- `app.database.repository.InvestigationRepository` — all SQL, parameterized throughout
  (confirmed by direct read of every query in the file), row↔model mapping.
- `app.database.models.Investigation` — the persistence-facing model (not re-read line-by-
  line this pass, but its `slots=True` and lack of a `reasons` field is directly referenced
  and relied upon by `risk_explanation_service.py`'s own docstring, and was cross-checked).

### API

Does not exist yet. No FastAPI/transport code exists in the current codebase (confirmed —
no `fastapi` import found anywhere in the files read or grepped this phase, and none is
listed in `requirements.txt`). This layer is entirely Phase 4C+ scope.

### Cross-cutting: Events

The two Qt event buses (`event_bus`, `application_events.events`) do not map cleanly onto
any single layer above — architecturally they are PRESENTATION-layer pub/sub (GUI components
talking to each other without direct references), even though `ApplicationState` (which
holds SERVER STATE, not just UI state) is one of their emitters. This mismatch — a
PRESENTATION-layer mechanism carrying at least one piece of SERVER STATE change notification
— is itself worth naming explicitly: it's part of why the target architecture's unified
event model (Phase 4D) needs the backend to be the sole publisher, rather than continuing the
current pattern where `ApplicationState` (conceptually application/domain-adjacent) reaches
directly into a Qt-specific signal object to announce a change.

## Net assessment

The existing codebase's actual DOMAIN/APPLICATION boundary is already closer to the target
than the Phase 4A master plan's speculative framing suggested. The primary structural
problem is not tangled business logic requiring a rewrite — it is **package-path
misplacement**: 6 files/~800 LOC of genuine application logic living under `app/gui/`
despite having zero Qt dependency, plus one confirmed backward dependency
(`risk_explanation_service.py` → GUI-package modules) that inverts the intended direction.
Both are mechanically fixable (move files, fix imports) without behavior change — which is
precisely why this phase's `EXTRACT` actions are marked low-risk throughout the Controller/
Service Inventory.
