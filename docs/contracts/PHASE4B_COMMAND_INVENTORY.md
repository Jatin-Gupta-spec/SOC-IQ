# Phase 4B — Command Inventory

**Status:** Phase 4B (Source-Verified). Derived directly from existing GUI controller/
service behavior — not copied from the Phase 4A master plan's illustrative list. No commands
are implemented in this phase.

A "command" here is any operation that changes state (as opposed to a read — see
`PHASE4B_QUERY_INVENTORY.md` for reads).

## `analyze_report`

- **Current entry point:** `AnalysisWorker.run()` (on a background `QThread`) →
  `AnalyzeController.analyze()` → `AnalysisService.analyze()` → `app.analyzer.
  analyze_report()`.
- **Current implementation:** Synchronous function; see Logic Preservation Matrix →
  Analysis.
- **Required inputs:** `report_path: str` (validated as existing file before dispatch).
- **Outputs:** `{"investigation": Investigation, "existing": bool}`.
- **Side effects:** Reads a file from disk; calls VirusTotal (external HTTP); writes one row
  to `investigations` table (via `InvestigationRepository.save`) unless a duplicate by
  report name already exists, in which case **no write occurs** and the existing record is
  returned instead.
- **Database interaction:** One `SELECT` (`exists_by_report_name`), conditionally one more
  `SELECT` (`find_by_report_name`) OR one `INSERT` (`save`) + one `SELECT` (`get_by_id` to
  reload).
- **Events generated:** None directly from `analyze_report()` itself. The **caller**
  (`AnalyzePage`) is responsible for emitting `event_bus.investigation_created` after
  `AnalysisWorker.finished` fires — confirmed via `main_window.py:462`.
- **Error cases:** `FileNotFoundError` (invalid path, raised by controller before the
  command runs) · `MissingAPIKeyError` (caught internally, degrades to
  `status: "unavailable", reason: "missing_api_key"`, does not fail the command) · any other
  TI exception (caught internally, degrades similarly, does not fail the command) ·
  `RuntimeError` (duplicate detected but could not be reloaded; or save succeeded but reload
  returned `None`) · any uncaught exception propagates to `AnalysisWorker.failed`.
- **Current tests:** No direct end-to-end test of `analyze_report()` found; stages tested
  separately (see Logic Preservation Matrix). **Gap.**
- **Target application handler:** `AnalyzeReportCommand` / `AnalyzeReportHandler`.

## `delete_investigation`

- **Current entry point:** `HistoryController.delete_investigation(investigation_id)` →
  `InvestigationService.delete()` → `InvestigationRepository.delete()`.
- **Current implementation:** Delegating wrapper with log+re-raise on failure.
- **Required inputs:** `investigation_id: int`.
- **Outputs:** `bool` (`True` if a row was deleted, `False` if no matching row existed).
- **Side effects:** One `DELETE` on the `investigations` table.
- **Database interaction:** One `DELETE`.
- **Events generated:** **None currently** — no call site was found emitting
  `event_bus.investigation_removed` or `events.investigation_deleted` in response to an
  actual delete. This matters because `IOCViewerPage` subscribes to
  `event_bus.investigation_removed` specifically to refresh itself; that refresh path is
  currently unreachable.
- **Error cases:** Any repository/database exception propagates (logged first).
- **Current tests:** `HistoryController.delete_investigation` has no direct test found by
  filename; `InvestigationRepository.delete`/`InvestigationService.delete` are covered by
  `tests/test_database.py`.
- **Target application handler:** `DeleteInvestigationCommand` / `DeleteInvestigationHandler`
  — **flag for product decision before implementing:** this command is fully built and
  tested at the service/repository layer but is not wired to any GUI action. Confirm this is
  intentional (a deliberately unexposed capability, e.g. reserved for a future "manage
  history" UI) rather than an accidental gap, before deciding whether Phase 4C+ exposes it.

## `save_settings` (inferred name — underlying `SettingsService` not read this pass)

- **Current entry point:** `SettingsPage` → (unverified service call) → emits
  `events.settings_changed.emit({...})` with one of three observed payload shapes:
  `{"virustotal_api_key": key}`, `{"export_directory": directory}`, `{"theme": theme}`.
- **Current implementation:** Not independently verified (`app/settings/service.py` is
  outside Phase 4B's stated file list of `app/services/`, `app/gui/controllers/`,
  `app/gui/services/`).
- **Required inputs:** One of the three key/value shapes above (never bundled together in
  the three observed emit sites — each call emits exactly one key).
- **Outputs:** Not verified.
- **Side effects:** Presumed persistence to `config/settings.json` (unverified this pass).
- **Database interaction:** None observed (settings appear to be file-based, not SQLite —
  `config/settings.json` exists in the repo root).
- **Events generated:** `events.settings_changed` (dict payload) — the **only** signal on
  the `events` (ApplicationEvents) bus confirmed to have both an emitter and a subscriber.
- **Error cases:** Not verified.
- **Current tests:** `tests/test_settings.py` (25 tests) — presumed to cover the service;
  not cross-checked against these three specific payload shapes this pass.
- **Target application handler:** `UpdateSettingCommand` / `UpdateSettingHandler` — the
  three ad-hoc payload shapes should likely become three distinct commands
  (`SetVirusTotalApiKey`, `SetExportDirectory`, `SetTheme`) or one command with a
  discriminated payload; not decided here, flagged for Phase 4D command-model design.

## Commands referenced by documentation but NOT found wired to any current code path

The Phase 4A master plan's illustrative command list included `enrich_ioc` and
`export_report`. Neither was found as a distinct callable command in the files read this
phase:

- `export_report` — `app/gui/utils/csv_exporter.py` exists and `app.reporting.service` is
  imported by GUI code, but neither was read this pass (outside the stated file list), so
  this is not confirmed as a discrete command vs. a UI-only export action. **Escalate to
  Phase 4B follow-up or Phase 4C precondition:** read `app/reporting/service.py` and
  `app/gui/utils/csv_exporter.py` before finalizing the command inventory.
- `enrich_ioc` — no standalone "re-enrich a single IOC" call site was found; TI enrichment
  currently only happens as one step inside `analyze_report`, for the whole investigation at
  once, not per-IOC on demand. If per-IOC re-enrichment is a real target-architecture
  requirement, it does not exist as a command today and would be new functionality, not an
  extraction.

This inventory is **not** claimed complete — see "Remaining unknowns" in
`PHASE4B_ARCHITECTURAL_FINDINGS.md`.
