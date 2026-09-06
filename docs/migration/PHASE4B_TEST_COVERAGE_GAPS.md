# Phase 4B — Test Coverage Gaps

**Status:** Phase 4B (Source-Verified). Covers every controller/service responsibility
inventoried in `PHASE4B_CONTROLLER_SERVICE_INVENTORY.md`. Per phase scope, this document
identifies gaps; it does not fill them with a large new test suite. No new tests were added
in this phase.

Legend: **Covered** (direct test exists) · **Partial** (covered transitively through a
lower layer, not directly) · **Untested** (no test found by filename, direct or transitive)
· **Integration-only** · **GUI-only**.

| Responsibility | Direct test file | Status | Notes |
|---|---|---|---|
| `AnalyzeController.analyze` / `.validate_report` | — | **Partial** | No file named after this controller exists under `tests/`; only exercised indirectly through GUI-level tests, if any (not confirmed this pass) |
| `HistoryController` (all 5 methods) | — | **Partial** | Same pattern — logic is delegated to `InvestigationService`, which *is* tested (`test_database.py`), but the controller's own added behavior (blank-string short-circuit, log+re-raise policy) has no direct assertion |
| `DashboardController` (all 8 methods) | — | **Partial** | Underlying `app/services/dashboard_*` classes are tested (`test_dashboard_services.py`, 16 tests); the controller's composition/delegation and its uniform re-raise policy are not directly asserted |
| `AnalysisService.analyze` | — | **Untested (direct)**, Partial (transitive via `analyze_report`'s own stage tests) | |
| `app.gui.services.ioc_detail_context` functions | `tests/test_ioc_detail_context.py` (14), `tests/gui/test_ioc_detail_context_url.py` (12) | **Covered** | |
| `app.gui.services.investigation_correlation_context` | — | **Untested** | No file matching this name found under `tests/` or `tests/gui/` |
| `app/services/correlation_service.py` | `tests/test_correlation_service.py` (25) | **Covered** | |
| `app/services/dashboard_*.py` (6 files) | `tests/test_dashboard_services.py` (16) | **Covered**, but coarse — one file for 6 classes; not verified whether every public method of every class has its own assertion vs. shared setup covering several at once | Worth a closer per-method audit before extraction, not done this pass |
| `app/services/risk_explanation_service.py` | `tests/test_risk_explanation_service.py` (24) | **Covered** | Does not appear to specifically test the backend→GUI import boundary issue (i.e. no test would currently fail if that dependency were removed incorrectly) |
| `app/services/system_health_service.py` | — | **Untested** | No file found under `tests/` covering this service directly. Given it opens a raw `sqlite3` connection outside the normal repository path (see Architectural Findings), this is the **highest-priority gap** identified in this phase |
| `app.gui.events.event_bus` (`EventBus`) | Indirect only, e.g. `tests/gui/test_ioc_viewer_page_defect_fix.py` references `event_bus.investigation_selected` behavior via `ApplicationState` | **Partial / GUI-only** | No test exercises `investigation_updated` or `investigation_removed` at all (consistent with them never being emitted anywhere — see Findings) |
| `app.gui.events.application_events` (`ApplicationEvents`) | — | **Untested** | No test file matches this module by name. Given 10 of 11 signals are never emitted or connected anywhere in the codebase (see Findings), this is expected, but means there is also no regression protection if the one live signal (`settings_changed`) breaks |
| Interaction between the two event buses | — | **Untested — confirms `06-event-architecture.md`'s own flagged UNKNOWN** | No test simulates a scenario that would catch the `investigation_deleted` (dead) vs. `investigation_removed` (also dead, but connected) naming confusion in practice |
| `app.gui.events.application_state` (`ApplicationState`) | `tests/gui/test_application_state_selected_ioc.py` (5) | **Covered** for `_selected_ioc`; **Untested (direct)** for `_current_investigation`'s deep-copy defensive behavior specifically, though it is exercised indirectly by any test that calls `select_investigation`/`get_current_investigation` | |
| `app/gui/workers/analysis_worker.py` | — | **Untested (direct)** | No file found testing `AnalysisWorker` itself — its double-run guard, its exception-to-`failed`-signal conversion, and its progress-callback wiring have no direct test. Only the underlying `analyze_report()` stages are unit-tested individually |
| `app.database.connection.DatabaseConnection` | `tests/test_database.py` (32, shared with `InvestigationRepository`/`InvestigationService`) | **Partial** | Not verified whether any test specifically asserts WAL mode, `foreign_keys=ON`, or the "half-configured connection is never published" retry behavior described in the file's own comments — these are exactly the kind of invisible-until-it-breaks behaviors worth a small targeted test before Phase 4C touches this file |
| `app.database.repository.InvestigationRepository` (all 8 public methods incl. `delete`) | `tests/test_database.py` | **Covered** | Confirms `delete()` itself is tested even though nothing in the GUI calls it — see Command Inventory |
| End-to-end `analyze_report()` workflow (all 7 stages as one sequence, including the duplicate-detection early return) | — | **Untested as a whole** | Each stage is unit-tested independently (extraction, scoring, TI, database), but no test asserts the full sequence, its progress-callback checkpoints, or the duplicate-detection short-circuit's exact return shape (`{"existing": True, ...}`) |

## Tests that MUST exist before Phase 4C/4D migration begins (per phase brief §14)

Ranked by risk, drawing directly from the gaps above:

1. **`SystemHealthService`** — untested, touches raw `sqlite3` outside the normal repository
   path. Any refactor of `DatabaseConnection` (e.g. adding the `busy_timeout` this phase's
   findings recommend, or a migration runner) could silently break this service with no
   test to catch it.
2. **End-to-end `analyze_report()` sequence test**, including the duplicate-detection
   early-return path and the exact progress-checkpoint sequence — this is the single most
   important user-facing workflow in the application and currently has zero test coverage
   of the sequence as a whole, only of its parts.
3. **`AnalysisWorker`'s double-run guard and exception→`failed`-signal conversion** — this is
   exactly the kind of defensive code (per its own docstring, protecting against a
   hypothetical duplicate signal connection) that silently stops mattering if a refactor
   removes it without anyone noticing, because nothing currently proves it does anything.
4. **A minimal `DatabaseConnection` pragma-assertion test** (WAL mode, `foreign_keys=ON`,
   and the half-configured-connection-not-published behavior on init failure) — small,
   cheap, and directly protects the exact facts this phase's UNKNOWN #2 investigation
   depended on being true.
5. **A test proving `event_bus.investigation_removed` currently has zero emitters** (or,
   preferably, wiring the missing emit in `HistoryController.delete_investigation`'s GUI
   call site and then testing that) — this is lower priority than 1–4 since it is a known,
   already-documented gap rather than a silent one, but should not be allowed to regress
   further before Phase 4D's event-bus unification work begins.

Per the phase brief's instruction to prefer documentation over new test suites in this
phase, none of the above were added here — this section exists so Phase 4C's owner does not
have to re-derive this list from scratch.
