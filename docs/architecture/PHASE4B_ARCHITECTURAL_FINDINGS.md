# Phase 4B — Architectural Findings

**Status:** Phase 4B (Source-Verified). This is the authoritative summary of everything
directly confirmed, corrected, or newly discovered this phase.

## Confirmed

- The repository shipped as a source-only archive with **no `.git` history** — there was no
  baseline `git log`/`git status` to compare against. See "Corrected" below.
- Baseline test count matches the documented Phase 4 checkpoint exactly: **542 passed, 0
  failed, 0 warnings, 0 collection errors** (Python 3.12.3, PySide6 6.11.2, pytest 9.1.1,
  `QT_QPA_PLATFORM=offscreen`).
- `analysis_worker.py`'s complete concurrency model (UNKNOWN #1): `QObject` moved to a
  freshly-constructed, deliberately-unparented `QThread` per analysis run; fully synchronous
  work on the worker thread; no cancellation support of any kind; a defensive (not
  Qt-mandated) double-run guard; exceptions logged with full traceback and converted to a
  `failed` signal. Full detail in `PHASE4B_THREADING_WORKFLOW_ANALYSIS.md`.
- `connection.py`'s exact behavior (UNKNOWN #2): WAL journal mode + `foreign_keys=ON` are
  configured; **no `busy_timeout` pragma exists**; **no schema-version/migration table
  exists**; a half-configured connection is never published to `self._connection` on init
  failure (retryable by design); despite `DatabaseConnection` looking like a persistent
  single-connection object, `InvestigationRepository` opens/closes a **new connection per
  operation** via `with self._database as connection:` on every single method — i.e. the
  actual runtime pattern is connection-per-operation, not one persistent connection reused
  across calls.
- Every file under `app/services/` (12 files) and `app/gui/controllers/` (3 files) and
  `app/gui/services/` (3 files) was read in full (UNKNOWNs #3, #4, #5). All 18 files are
  **100% free of PySide6/Qt imports** — confirmed by both `grep -l PySide6` and manual
  import inspection. No method in any of these files falls into presentation-logic (A),
  Qt-orchestration (D), or state-management-via-Qt (H) categories from the phase brief's
  classification scheme — everything present is application logic (B), data-access
  delegation (C), validation (E), transformation (F), or error-handling policy (I).
- **One confirmed backend→GUI dependency violation**: `app/services/
  risk_explanation_service.py` imports `app.gui.services.ioc_detail_context.
  build_investigation_threat_intel_overview` and three functions from
  `app.gui.utils.ioc_significance`. This is the only ARCHITECTURALLY INVALID FOR TARGET
  dependency found in the files read this phase (dependency-map category from phase brief
  §6). It is not fixed here per the non-negotiable rule, but is precisely located.
- No duplication was found between `app/services/*` and `app/gui/services/*` — they are
  complementary (domain/application computation vs. presentation reshaping of that
  computation's output), addressing UNKNOWN #5's specific duplication-detection requirement.
- The two Qt event buses' actual signal graph (§5 of the phase brief), traced by direct
  `grep` of every `.emit(` and `.connect(` call site for every signal on both buses:
  - `event_bus.investigation_selected` — emitted from `ApplicationState` (2 sites),
    connected in `main_window.py`, `dashboard_page.py`, `investigation_workspace.py`,
    `ioc_viewer_page.py`. **Live, well-connected.**
  - `event_bus.investigation_created` — emitted once, from `main_window.py:462`. Connected
    in `dashboard_page.py` and `live_security_events_widget.py`. **Live.**
  - `event_bus.investigation_updated` — **zero emit sites found anywhere in the codebase.**
    Connected only in `ioc_viewer_page.py`. **Dead signal** (connected, never fired).
  - `event_bus.investigation_removed` — **zero emit sites found anywhere in the codebase.**
    Connected only in `ioc_viewer_page.py`. **Dead signal** (connected, never fired) —
    directly relevant because `HistoryController.delete_investigation` exists, is
    implemented, and is tested at the service/repository layer, but nothing in the GUI ever
    calls it, so this signal has no path to ever fire even indirectly.
  - `event_bus.application_state_changed` — **zero emit or connect sites found anywhere.**
    Fully dead in both directions.
  - `events.investigation_created`, `events.investigation_deleted`,
    `events.investigation_updated`, `events.dashboard_refresh_requested`,
    `events.history_refresh_requested`, `events.ioc_refresh_requested`,
    `events.threat_intelligence_refresh_requested`,
    `events.risk_dashboard_refresh_requested`, `events.status_message`,
    `events.error_occurred` — **all ten have zero emit sites AND zero connect sites found
    anywhere in the codebase.** Fully dead, both directions, all ten signals.
  - `events.settings_changed` — the **only** signal on the `application_events.events` bus
    with both a live emitter (`settings_page.py`, 3 call sites) and a live subscriber
    (`threat_intel_page.py`). **Live.**
  - **Net finding:** of 16 total signals across both buses, only 3 are genuinely live end to
    end (`investigation_selected`, `investigation_created`, `settings_changed`). 2 are
    connected-but-never-emitted (`investigation_updated`, `investigation_removed`). 10 are
    completely unused in either direction (all of `application_events.events` except
    `settings_changed`), and 1 is unused in both directions on the other bus
    (`application_state_changed`).
  - `events.investigation_deleted` vs. `event_bus.investigation_removed` (the specific pair
    the phase brief asked to verify, §5): **they are not the same event, and neither is
    actually fired by anything.** The existing source docstrings' warning not to confuse the
    two remains valid advice for future engineers, but the more consequential finding is that
    an investigation being deleted currently notifies **no one, on either bus** — there is no
    live "an investigation was deleted" event on this codebase today, under either name.

## Corrected

- **`docs/architecture/09-database-architecture.md`**: its "UNKNOWN / REQUIRES
  VERIFICATION" section is now fully resolved — see the BEFORE/AFTER edit applied directly
  to that file this phase (§16 of phase brief). Summary: WAL mode IS configured (the doc's
  own TARGET STATE section had already assumed this was worth having; CURRENT STATE can now
  say it exists); no `busy_timeout` exists (new negative finding, not previously flagged);
  no migration/schema-version table exists (upgraded from "LIKELY" to "CONFIRMED", exactly
  as the doc's own UNKNOWN section requested).
- **`docs/architecture/06-event-architecture.md`**: its "UNKNOWN / REQUIRES VERIFICATION"
  section asked specifically whether any test exercises the interaction between the two
  buses. **Answer: no such test exists.** BEFORE/AFTER edit applied. Additionally, the
  existing CURRENT STATE section's characterization ("the same docstring flags
  `investigation_deleted` as dead in practice") undersold the actual finding — the dead-code
  problem is far larger than one signal (13 of 16 signals across both buses are dead in one
  or both directions, not one) — corrected in place.
- **`docs/architecture/07-state-architecture.md`**: its "UNKNOWN / REQUIRES VERIFICATION"
  section asked for `ApplicationState`'s current responsibilities and its relationship to
  the two event buses. Fully resolved in `PHASE4B_STATE_INVENTORY.md`; BEFORE/AFTER edit
  applied to this file pointing to that document, and confirming its existing TARGET STATE
  table requires no changes.
- No ADR required a status change (Proposed/Accepted/Superseded/Rejected) this phase — none
  of the findings above contradict a decision an ADR actually made; they fill in previously
  flagged UNKNOWNs and add detail, they don't overturn a prior decision. (Confirmed by
  reading `ADR-005-sqlite-remains-database.md`'s scope — its decision, "keep SQLite," is
  unaffected by the WAL/busy-timeout/migration-table findings, which are implementation
  details within that decision, not challenges to it.)

## New discoveries

1. **`HistoryController.delete_investigation` is fully implemented and tested at the
   service/repository layer but unreachable from any GUI action.** No page, button, or menu
   item was found calling it. This was not previously documented anywhere in the Phase 4A
   docs. See Command Inventory and Test Coverage Gaps for the full trail.
2. **10 of 11 signals on `application_events.events` are entirely dead code** (not just the
   one, `investigation_deleted`, that the existing docs already called out). This is a
   materially larger finding than what `06-event-architecture.md` previously documented.
3. **`InvestigationRepository` is connection-per-operation, not a persistent connection**,
   despite `DatabaseConnection`'s shape suggesting otherwise. This matters directly for the
   target Tauri → Python-sidecar → SQLite model: a connection-per-operation pattern is
   *more* portable to a sidecar-process model than a long-lived single connection would have
   been (fewer cross-request state assumptions), which is a small positive finding worth
   carrying into `09-database-architecture.md`'s TARGET STATE reasoning, though not acted on
   this phase.
4. **No `busy_timeout` pragma is set**, despite WAL mode being configured specifically (per
   the code's own comment) to reduce "database is locked" risk under the exact
   background-thread-writes-while-GUI-reads pattern this application already has today. WAL
   reduces but does not eliminate this risk without a busy timeout as a backstop. This is a
   genuine, previously undocumented latent-bug risk, not a hypothetical one — the
   `AnalysisWorker`/GUI-read concurrency pattern that would trigger it already exists in the
   current, shipped code.
5. **`app/services/risk_explanation_service.py`'s backend→GUI import** is a real,
   previously-unflagged instance of the exact "domain code importing GUI code" failure mode
   the phase brief's dependency-classification scheme (§6) was designed to catch.

## Unknowns resolved

Every UNKNOWN listed in phase brief §1 (the numbered UNKNOWN #1–#5) is resolved above and in
the linked deliverable documents. Every UNKNOWN previously flagged inside the existing Phase
4A docs that fell within this phase's stated scope (`09-database-architecture.md`,
`06-event-architecture.md`, `07-state-architecture.md`) is also resolved, with BEFORE/AFTER
edits applied directly to those files.

## Remaining unknowns

These are explicitly **not** resolved this phase, because resolving them would require
reading files outside the phase brief's stated scope (`app/services/`, `app/gui/
controllers/`, `app/gui/services/`, plus the specifically-named `analysis_worker.py` and
`connection.py`). Listed here rather than silently left undocumented, per the phase brief's
own "escalate, don't hide" instruction:

- `app/reporting/service.py` — imported from GUI code, has 40 passing tests
  (`test_reporting.py`), but its internal shape, DB/Qt coupling, and exact relationship to
  the `export_report` command referenced in the Phase 4A master plan were not verified.
- `app/settings/service.py` — backs `events.settings_changed`'s three observed payload
  shapes; 25 passing tests exist (`test_settings.py`), but the service's own file was not
  read.
- `app/threat_intel/service.py` and `app/threat_intel/virustotal.py` — heavily tested (97
  tests combined) but not re-read this phase; their exact retry/error behavior referenced in
  the Threading/Workflow Analysis is inferred from `analyzer.py`'s call site, not verified
  at the source.
- `app.scoring.engine.RiskScoringEngine` and `app.extractor` — both treated as DOMAIN by
  reference in the Application Boundary Design doc, not by direct read.
- Whether `list_all()` and `find_by_severity()` (both on `InvestigationService`/
  `InvestigationRepository`, both tested) have any live caller at all — no call site was
  found in the files read this phase, but the pages that might call them
  (`app/gui/pages/*`) are outside this phase's scope.
- The exact GUI call sites for `CorrelationService.correlate()` and
  `RiskExplanationService.explain()` (likely `investigation_workspace.py` and/or
  `risk_explanation_widget.py`) were not traced — their existence and logic are confirmed,
  their invocation context is not.
- Whether `git status`/`git log` would show anything meaningful is moot this phase since no
  `.git` directory shipped with the source archive — see "Corrected" above. If the actual
  development repository has history that wasn't included in this archive, that history was
  not available for §3/§20 of the phase brief.

## Risks

1. **Busy-timeout gap** (see New Discoveries #4) — recommend adding a `busy_timeout` pragma
   before any change that could increase write contention (e.g. a future background job
   queue). Not fixed this phase (out of the non-negotiable "do not change application
   behavior" rule), but flagged as a pre-Phase-4C recommendation.
2. **Dead-event-signal debt** — 13 of 16 signals across both buses are non-functional in one
   or both directions. This is low risk *today* (nothing depends on them working), but is a
   trap for Phase 4D: any "faithful" 1:1 port of the current event surface into the new
   unified model would be porting mostly dead code. The event catalog for the new model
   should be derived from the 3 confirmed-live signals plus genuinely new requirements, not
   from the full existing signal list.
3. **`HistoryController.delete_investigation`'s reachability gap** — a product decision is
   needed (see Command Inventory) before Phase 4C decides whether to expose or drop this
   capability; shipping it into the new command model without checking would either silently
   introduce a new user-facing delete feature that was never actually reachable before, or
   silently drop a deliberately-reserved-for-later capability.
4. **`risk_explanation_service.py`'s backward dependency** must be resolved before or during
   Phase 4C's provider-abstraction work touches anything nearby, since it currently makes
   `app/services/` not fully independently importable without pulling in `app/gui/`.
5. **No end-to-end test of `analyze_report()`'s full sequence** (see Test Coverage Gaps #2)
   is the single highest-value test to add before any refactor of this workflow begins.

## Recommendations (changes required before Phase 4C)

1. Add the 5 tests listed in `PHASE4B_TEST_COVERAGE_GAPS.md`'s "MUST exist" section,
   starting with the `SystemHealthService` test and the end-to-end `analyze_report()`
   sequence test.
2. Resolve `risk_explanation_service.py`'s backend→GUI dependency (likely by relocating
   `ioc_significance.py`'s functions to a domain-layer module, since they have zero Qt
   dependency and are already conceptually domain logic) before Phase 4C's
   `ThreatIntelProvider` work touches any neighboring code.
3. Get an explicit product decision on `delete_investigation`'s intended reachability before
   the command model formalizes it one way or the other.
4. Carry the "log + re-raise, never mask a failure as an empty/default result" error-handling
   convention (documented at length in the Logic Preservation Matrix) forward explicitly into
   the application-layer command/query handler design — it is a genuine, deliberate
   architectural decision already made by this codebase's authors, not an artifact worth
   losing in the move.
5. When Phase 4D designs the unified event catalog, start from the 3 confirmed-live signals
   (`investigation_selected`, `investigation_created`, `settings_changed`) rather than
   treating the full 16-signal surface as a requirements baseline.
