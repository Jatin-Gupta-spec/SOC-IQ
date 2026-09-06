# Phase 4B — Logic Preservation Matrix

**Status:** Phase 4B (Source-Verified). Documents exactly what behavior must survive
eventual GUI retirement (Phase 4O per `06-event-architecture.md`'s migration notes).

For each category: CURRENT OWNER · CURRENT ENTRY POINT · DEPENDENCIES · TARGET OWNER ·
PRESERVE/REFACTOR/REMOVE · TEST COVERAGE · MIGRATION RISK.

## Analysis

- **Current owner:** `app.analyzer.analyze_report` (function, not a class; already outside
  `app/gui/`).
- **Entry point:** `AnalysisWorker.run()` → `AnalyzeController.analyze()` →
  `AnalysisService.analyze()` → `analyze_report()`.
- **Dependencies:** `InvestigationRepository`, `app.extractor` (`read_report`,
  `extract_iocs`), `app.threat_intel.service.ThreatIntelService`, `app.scoring.engine.
  RiskScoringEngine`.
- **Target owner:** application-layer `analyze_report` command handler.
- **Preserve/Refactor/Remove:** PRESERVE the workflow and ordering (read → extract →
  duplicate-check → TI enrich → score → persist → return) exactly. REFACTOR the two
  indirection layers (`AnalyzeController`, `AnalysisService`) into the command handler itself
  — see Controller/Service Inventory note on `analysis_service.py`.
- **Test coverage:** No direct unit test of `analyze_report()`'s full workflow was found
  under `tests/`; individual stages are tested separately (`test_extractor.py`,
  `test_scoring.py`, `test_threat_intel.py`, `test_database.py`). Flagged in
  `PHASE4B_TEST_COVERAGE_GAPS.md`.
- **Migration risk:** Medium — the duplicate-investigation short-circuit
  (`exists_by_report_name` before enrichment) and the three-way `MissingAPIKeyError` /
  generic-exception / success branching for `threat_intelligence` are easy to silently
  change while refactoring; no end-to-end test currently protects the whole shape.

## Extraction

- **Current owner:** `app.extractor` (`extract_iocs`, `read_report`, `COMPILED_PATTERNS`).
- **Entry point:** called directly by `analyze_report`.
- **Dependencies:** none beyond stdlib regex/file I/O (not independently re-verified in this
  pass — file was not opened; classification is by reference from `analyzer.py`'s import and
  existing `tests/test_extractor.py`).
- **Target owner:** domain layer.
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** `tests/test_extractor.py` (13 tests).
- **Migration risk:** Low.

## Scoring

- **Current owner:** `app.scoring.engine.RiskScoringEngine`.
- **Entry point:** `RiskScoringEngine.calculate(extracted_iocs, threat_intelligence)` in
  `analyze_report`.
- **Dependencies:** not independently re-read this pass (out of Phase 4B's stated file list);
  referenced via `app/services/ioc_significance.py` and `risk_explanation_service.py` as the
  sole authoritative source of risk score/severity — this is an explicit, repeated
  in-source design constraint ("DO NOT CHANGE THE EXISTING RISK ENGINE", per
  `risk_explanation_service.py`'s own docstring).
- **Target owner:** domain layer.
- **Preserve/Refactor/Remove:** PRESERVE, unchanged.
- **Test coverage:** `tests/test_scoring.py` (37 tests).
- **Migration risk:** Low, provided the "do not touch the scoring engine" constraint is
  carried forward into Phase 4C+ verbatim.

## Threat intelligence

- **Current owner:** `app.threat_intel.service.ThreatIntelService` (context-manager
  protocol), backed by `app.threat_intel.virustotal.VirusTotalClient` (referenced from
  `system_health_service.py` and GUI imports; not independently re-read this pass — out of
  Phase 4B's stated file list, which is `app/services/`, `app/gui/controllers/`,
  `app/gui/services/`).
- **Entry point:** `with ThreatIntelService() as service: service.enrich_results(iocs)` in
  `analyze_report`.
- **Dependencies:** VirusTotal HTTP API (external).
- **Target owner:** application layer, behind the future `ThreatIntelProvider` abstraction
  (explicitly Phase 4C scope — not touched here).
- **Preserve/Refactor/Remove:** PRESERVE current behavior as-is in 4B; REFACTOR is Phase 4C's
  job.
- **Test coverage:** `tests/test_threat_intel.py` (20), `tests/test_virustotal.py` (77).
- **Migration risk:** Low for 4B (nothing touched); the large existing VirusTotal test suite
  is a meaningful safety net for 4C.

## Investigation lifecycle

- **Current owner:** `app.database.service.InvestigationService` (save / get_by_id /
  list_all / find_by_report_name / investigation_exists / get_latest_by_report_name /
  find_by_severity / find_recent / delete / count), backed by
  `app.database.repository.InvestigationRepository`.
- **Entry point:** Called from `analyze_report` (save/lookup), `HistoryController` (get/
  delete/search), `DashboardController` (via dashboard services).
- **Dependencies:** `DatabaseConnection` → SQLite.
- **Target owner:** application service (`InvestigationService`) over a repository
  (`InvestigationRepository`) — this is already the target shape; no structural change
  needed.
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** `tests/test_database.py` (32 tests).
- **Migration risk:** Low for the CRUD surface itself. Medium for the **delete** path
  specifically: `HistoryController.delete_investigation` and the underlying
  `InvestigationService.delete`/`InvestigationRepository.delete` are implemented and tested,
  but are never invoked from any GUI page — deleting an investigation is not currently a
  reachable user action. Confirm intent before Phase 4C: is this a genuinely missing feature,
  or dead code to drop?

## History

- **Current owner:** `HistoryController` (`app/gui/controllers/history_controller.py`).
- **Entry point:** `HistoryPage` (`app/gui/pages/history_page.py`) calls only
  `get_recent_investigations()` — confirmed by direct grep; no other `HistoryController`
  method is called from `history_page.py`.
- **Dependencies:** `InvestigationService`.
- **Target owner:** application layer (already Qt-free — see Controller/Service Inventory).
- **Preserve/Refactor/Remove:** PRESERVE logic; EXTRACT file location.
- **Test coverage:** No direct test of `HistoryController` found by filename; covered
  transitively through `InvestigationService`/`InvestigationRepository` tests only.
- **Migration risk:** Low for `get_recent_investigations`; see Investigation Lifecycle above
  for the delete-path caveat, and Dashboard below for `search_by_report_name`, which is also
  unreferenced from `history_page.py` in the current grep.

## Dashboard

- **Current owner:** `DashboardController` + 6 `app/services/dashboard_*` classes +
  `SystemHealthService`.
- **Entry point:** `DashboardPage` (not independently re-read this pass).
- **Dependencies:** `InvestigationService`, `SettingsService` (via `SystemHealthService`).
- **Target owner:** application query services (already correctly placed under
  `app/services/`, only `DashboardController` itself needs relocation out of `app/gui/`).
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** `tests/test_dashboard_services.py` (16 tests) — covers the
  `app/services/dashboard_*` classes. `DashboardController` and `SystemHealthService`
  themselves have no test found by filename; flagged in coverage gaps doc.
- **Migration risk:** Low.

## Correlation

- **Current owner:** `app.services.correlation_service.CorrelationService`.
- **Entry point:** Not called from `analyze_report` (correlation is computed on-demand from
  an already-persisted `Investigation`, per its own docstring pattern shared with
  `RiskExplanationService`) — exact GUI call site not re-verified this pass (would require
  reading `investigation_workspace.py`, outside Phase 4B's stated file list).
- **Dependencies:** `app.database.models.Investigation` only (read-only, pure function).
- **Target owner:** domain layer.
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** `tests/test_correlation_service.py` (25 tests).
- **Migration risk:** Low.

## Risk explanation

- **Current owner:** `app.services.risk_explanation_service.RiskExplanationService`.
- **Entry point:** Not re-verified this pass (likely `investigation_workspace.py` /
  `risk_explanation_widget.py`, both outside Phase 4B's stated file list).
- **Dependencies:** `Investigation`, optional `CorrelationReport`, **and** two GUI-package
  modules (`app.gui.services.ioc_detail_context`, `app.gui.utils.ioc_significance`) — this
  is the one confirmed backend→GUI dependency violation (see Architectural Findings).
- **Target owner:** application layer.
- **Preserve/Refactor/Remove:** PRESERVE the explanation logic; REFACTOR the dependency
  direction before Phase 4C — either move `ioc_significance.py`'s pure functions (they wrap
  `RiskScoringEngine`, not Qt) into `app/services/` or a shared domain-utilities module, or
  invert the dependency.
- **Test coverage:** `tests/test_risk_explanation_service.py` (24 tests).
- **Migration risk:** Medium, entirely due to the dependency-direction issue, not the logic
  itself.

## Reporting

- **Current owner:** `app.reporting.service` (imported by GUI; not independently re-read
  this pass — outside Phase 4B's stated file list of `app/services/`, `app/gui/controllers/`,
  `app/gui/services/`).
- **Entry point:** Not re-verified this pass.
- **Dependencies:** Unknown until read.
- **Target owner:** application layer.
- **Preserve/Refactor/Remove:** PRESERVE (no evidence of any problem; not investigated
  further to stay within scope).
- **Test coverage:** `tests/test_reporting.py` (40 tests).
- **Migration risk:** Unknown — REMAINING UNKNOWN, see Architectural Findings.

## Settings

- **Current owner:** `app.settings.service.SettingsService` (not independently re-read this
  pass — outside stated file list).
- **Entry point:** `SettingsPage` emits `events.settings_changed`; `ThreatIntelPage`
  subscribes to it. This is the **one** signal on the `events` (ApplicationEvents) bus that
  is actually wired end-to-end (see Event Bus Findings).
- **Dependencies:** Unknown until read.
- **Target owner:** application layer.
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** `tests/test_settings.py` (25 tests).
- **Migration risk:** Low for the service itself; the `settings_changed` event's payload
  shape (`dict`) should get a real DTO in the target event model rather than a bare dict.

## Error handling

- **Current owner:** Distributed — every controller/service method in `app/gui/controllers/`
  and `DashboardController` follows one explicit, uniform policy: log with
  `logger.exception(...)`, then re-raise. Never silently return an empty/default result on
  failure. This is stated as a deliberate design decision in both controllers' docstrings.
- **Entry point:** N/A (cross-cutting).
- **Dependencies:** Python stdlib `logging`.
- **Target owner:** application layer (should become a formal error-model convention, per
  `docs/contracts/error-model.md` — not read this pass, flagged for cross-check).
- **Preserve/Refactor/Remove:** PRESERVE the policy explicitly; it is a genuine, deliberate
  architectural decision worth carrying into the application-layer command/query handlers,
  not an accident of the current code.
- **Test coverage:** Not independently verified whether tests assert the re-raise behavior
  specifically (vs. just testing the happy path). Flagged in coverage gaps doc.
- **Migration risk:** Low if the convention is written down explicitly (this document does
  so); Medium if it is only tribal knowledge carried in docstrings that don't survive a file
  move.

## Validation

- **Current owner:** `AnalyzeController.validate_report` (path existence/is-file),
  `HistoryController.search_by_report_name` (blank-string short-circuit).
- **Target owner:** application layer (input validation belongs at the application boundary
  per the target-architecture definition in this same phase's boundary design doc).
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** Not directly tested by filename; flagged.
- **Migration risk:** Low.

## System health

- **Current owner:** `app.services.system_health_service.SystemHealthService`.
- **Entry point:** `DashboardController.get_system_status`.
- **Dependencies:** `DatabaseConnection` (raw `sqlite3` check), `SettingsService`
  (VirusTotal key presence, inferred from method name `_virustotal_status`), repository,
  analysis engine.
- **Target owner:** application layer.
- **Preserve/Refactor/Remove:** PRESERVE.
- **Test coverage:** Not found under any of the 4 `app/services`-scoped test files listed in
  the phase brief by name; flagged as a coverage gap.
- **Migration risk:** Medium — untested code path that directly opens a raw `sqlite3`
  connection outside the normal `DatabaseConnection`/`InvestigationRepository` path deserves
  a test before any refactor touches it.

## Event publication

- **Current owner:** Split across two independent Qt signal singletons —
  `app.gui.events.event_bus.event_bus` (investigation lifecycle) and
  `app.gui.events.application_events.events` (settings/refresh/status).
- **Entry point:** N/A (cross-cutting; see Architectural Findings for the full emit/connect
  trace).
- **Dependencies:** PySide6 `Signal`/`QObject` — this category is the one place in the
  audited scope with real Qt coupling, by design (it is the GUI's internal pub/sub).
- **Target owner:** unified application-layer event model (`docs/contracts/event-model.md`,
  Phase 4D — not built here).
- **Preserve/Refactor/Remove:** PRESERVE current Qt behavior unchanged for Phase 4B (per the
  non-negotiable rule); REFACTOR is explicitly Phase 4D+ scope. Do **not** attempt a
  rename-and-merge of the two buses even as a "trivial" fix — the phase brief and the
  existing `06-event-architecture.md` migration notes both explicitly forbid this.
- **Test coverage:** No test was found that exercises the *interaction* between the two
  buses (confirms `06-event-architecture.md`'s flagged unknown — see Architectural
  Findings, "Unknowns resolved"). Several GUI tests exercise `event_bus.
  investigation_selected` individually.
- **Migration risk:** High if touched carelessly (many silent no-op signals — see Findings),
  Low if left untouched as instructed this phase.
