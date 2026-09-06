# Phase 4D Part 6 — `export_report` Vertical Slice

**Status:** Complete for the one command implemented here. Builds on the
verified Phase 4D Part 5 checkpoint (`get_investigation`, `get_iocs`,
`list_investigations`, `delete_investigation`, `search_investigations`,
`analyze_report`, `save_settings` — 516 non-GUI / 670 offscreen / 59
application+API tests, all reproduced fresh before this slice was
started). This is **not** a Phase 4D freeze and does not claim Phase 4D
complete — 2 named commands (`enrich_ioc`, `get_threat_intelligence`)
remain unimplemented, and `GET /events` SSE remains an honest 501.

## 1. Checkpoint audit performed before any change

The uploaded `SOC-IQ-Phase4D-Part5-Command-Slice.zip` was extracted fresh
into a clean directory and verified directly, rather than trusting the
brief's description:

| Item | Result |
|---|---|
| Seven completed commands (`get_investigation`, `get_iocs`, `list_investigations`, `delete_investigation`, `search_investigations`, `analyze_report`, `save_settings`) | Present — confirmed by direct read of `handlers.py`'s `COMMAND_HANDLERS` dict |
| Phase 4C provider abstraction (`app/threat_intel/provider.py`, `virustotal_provider.py`) | Present |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| All Phase 4D implementation docs (Part 2–5) | Present |
| `app/application/`, `app/api/` architecture | Intact, unchanged shape (5 files / 3 files) before this slice |
| Pre-existing Phase 4E scaffolding (`app/api/entrypoint.py`, `GET /health`, `src-tauri/`, `frontend/`) | Present, confirmed untouched by this slice (byte-identical to the Part 5 checkpoint — verified with `diff -rq --exclude=__pycache__`) |
| Baseline tests | **516 passed** (non-GUI) / **670 passed** (offscreen) / **59 passed** (application+API) — reproduced fresh this session, matches the brief's stated baseline exactly |

## 2. Command selected: `export_report`

Evaluated all three remaining named candidates:

- `enrich_ioc` — confirmed again this session (`grep -rn "def enrich"
  app`): only `ThreatIntelService.enrich_results` exists, which operates
  on a whole investigation's IOC set, not a single IOC. No standalone
  per-IOC enrichment call site exists anywhere in source. Implementing
  this would still be new functionality, not an extraction. Not
  selected.
- `get_threat_intelligence` — confirmed again this session
  (`grep -rn build_investigation_threat_intel_overview app`): its
  natural backing still lives at
  `app.gui.services.ioc_detail_context.build_investigation_threat_intel_overview`,
  still takes GUI-adjacent inputs, and is still imported by
  `app.gui.pages.investigation_workspace` /
  `app.gui.pages.ioc_viewer_page` / `app.services.risk_explanation_service`
  — all GUI or GUI-adjacent call sites. Wrapping it would mean either a
  new `app.gui` import into `app/application` (forbidden coupling, per
  every prior part's own dependency-direction rule) or reimplementing
  its logic (invented behavior). Deferred again, not selected.
- **`export_report` — selected.** Direct inspection this session of
  `app/reporting/service.py` (outside the file list Part 5's own
  candidate evaluation cited) found a real, already-tested,
  already-injectable contract: `ReportingService.export_html`,
  `.export_json`, `.export_markdown`, `.export_pdf` — four
  single-responsibility methods, each `(investigation: Investigation,
  output_path: Path) -> Path`, each already covered by
  `tests/test_reporting.py`. `app/reporting/*` has zero Qt/PySide6
  imports (confirmed by grep across the package). The GUI call site
  (`app/gui/main_window.py`'s `_export_report`) shows the exact
  format-dispatch mapping this handler mirrors. This is now the
  strongest, most source-verified contract of the three remaining
  candidates and requires the least invented behavior — the same
  evaluation Part 5 made for `save_settings`, applied to the one
  candidate Part 5's own audit didn't reach.

## 3. Exact existing contract used

- `app/reporting/service.py` — `ReportingService.export_html`,
  `.export_json`, `.export_markdown`, `.export_pdf`, all pre-existing,
  unchanged, not touched. Each internally builds an
  `InvestigationReport` via `ReportBuilder.build()` then delegates to
  `ExportManager`. `.build_default_filename()` exists but is a GUI-only
  concern (default save-dialog filename) with no equivalent in this
  command's contract — not wrapped here, since the caller supplies
  `output_path` directly, mirroring how `save_settings` did not invent
  a GUI-only concern (blank-rejection uniformity) it had no source
  evidence for.
- `app/database/service.py` — `InvestigationService.get_by_id`, reused
  unchanged, identical to `GetInvestigationCommandHandler` /
  `GetIocsCommandHandler`'s own lookup.
- `app/gui/main_window.py` — `MainWindow._export_report` (read-only, not
  modified): confirmed the four-format dispatch
  (`html`/`pdf`/`json`/`markdown`) this handler mirrors, and confirmed
  a 5th format (`csv`, from `docs/architecture/16-reporting-architecture.md`'s
  exporter list) has no single-investigation call site — see §7 Known
  limitations.
- `app/reporting/json_exporter.py` / `markdown_exporter.py` /
  `html_exporter.py` — confirmed (read-only) that `OSError` during
  write is wrapped as a bare `RuntimeError`, not a `SOCIQError`
  subclass. `pdf_exporter.py` does not catch `OSError` at all (raw
  exception can propagate). Neither is in `errors.py`'s exception-code
  map, so both fall through `code_for_exception`'s MRO walk to the
  existing `INTERNAL_ERROR` fallback — the same documented gap
  `errors.py`'s own module docstring already notes for
  `app/reporting/*`, and the same fallback Part 5 pinned for
  `SettingsService`'s uncaught `OSError`. No new exception-code mapping
  was invented for this slice.

## 4. Implementation

- `app/application/dto.py` — added `ExportReportRequest` (frozen
  dataclass: `investigation_id: int`, `export_format: str`,
  `output_path: str`) and a module-level `VALID_EXPORT_FORMATS = ("html",
  "pdf", "json", "markdown")` constant. `__post_init__` rejects a
  non-positive `investigation_id` (mirrors `GetInvestigationRequest` /
  `GetIocsRequest` / `DeleteInvestigationRequest` exactly), rejects an
  `export_format` outside the four confirmed formats, and rejects a
  blank/non-string `output_path`.
- `app/application/handlers.py` — added `ExportReportCommandHandler`,
  constructed the same way as every other handler
  (`InvestigationService | None` and `ReportingService | None`
  injection points). Looks up the investigation via the same
  `get_by_id` call `GetInvestigationCommandHandler`/`GetIocsCommandHandler`
  use, returns `INVESTIGATION_NOT_FOUND` before ever touching
  `ReportingService` if the lookup misses, then dispatches to whichever
  `export_*` method matches the validated format and returns
  `ok({"investigation_id", "export_format", "output_path"})`.
- `app/application/handlers.py` `dispatch()` — added one
  `if name == "export_report":` branch, positioned directly after
  `delete_investigation`. Falls through the same
  `CommandValidationError` / `TypeError` / catch-all `Exception` →
  `code_for_exception()` translation every other command already uses.
- `app/application/handlers.py` `COMMAND_HANDLERS` — added one entry:
  `"export_report": lambda payload: dispatch("export_report", payload)`.
- `app/api/app.py` — **not modified.** `POST /commands/{name}` already
  routes generically through `COMMAND_HANDLERS`.

## 5. Files created/modified

- Modified: `app/application/dto.py`, `app/application/handlers.py`,
  `tests/test_application_layer.py`, `tests/test_api_layer.py`.
- Created: `docs/phase4/PHASE4D_PART6_IMPLEMENTATION.md` (this file).
- Not touched: everything else, including all Phase 4C source, all
  seven previously-implemented command handlers/DTOs, `app/reporting/*`,
  `app/database/*`, `app/gui/*`, `app/api/app.py`,
  `app/api/entrypoint.py`, `src-tauri/`, `frontend/` — all confirmed
  byte-identical to the Part 5 checkpoint via `diff -rq
  --exclude=__pycache__` (§6).

## 6. Tests added (15 total)

`tests/test_application_layer.py` (12, in `ExportReportCommandHandlerTests`
plus 2 in `DispatchErrorTranslationTests`):
exports json / markdown / html / pdf for an existing investigation and
confirms the file is actually written; returns `INVESTIGATION_NOT_FOUND`
for a missing investigation; confirms the not-found short-circuit
happens *before* any export is attempted (a deliberately-bogus,
nonexistent output directory is never created); rejects a non-positive
`investigation_id`; rejects an unsupported `export_format` (`csv`,
`xml`); rejects a blank `output_path`; dispatched via command name
(real write to a temp path, confirmed with the real DB) —
`ExportReportCommandHandlerTests` (10) — plus
`test_export_report_translates_unexpected_service_exception` and
`test_export_report_translates_exporter_write_failure` in
`DispatchErrorTranslationTests` (2).

`tests/test_api_layer.py` (3): `test_export_report_not_found_is_translated_not_raised`,
`test_export_report_validation_error_never_reaches_domain`,
`test_export_report_rejects_unsupported_format_before_domain` — all
three are read-only/validation-only against the live HTTP transport
(no real file is ever written), consistent with this file's own
module docstring restricting HTTP-layer tests to non-mutating paths.

## 7. Focused test results

`pytest tests/test_application_layer.py -q -k "ExportReport or export_report"`
→ **12 passed**.
`pytest tests/test_api_layer.py -q -k "export_report"` → **3 passed**.

## 8. Fresh full-suite results

| Suite | Before this slice | After this slice |
|---|---|---|
| `pytest tests/ -q --ignore=tests/gui` | 516 passed | **531 passed** (+15) |
| `QT_QPA_PLATFORM=offscreen pytest tests/ -q` | 670 passed | **685 passed** (+15) |
| `pytest tests/test_application_layer.py tests/test_api_layer.py -q` | 59 passed | **74 passed** (+15) |

Zero regressions, zero skips — the +15 matches the 15 tests added
exactly. Re-ran every previously-completed command's own test classes
(`GetInvestigation*`, `GetIocs*`, `ListInvestigations*`,
`SearchInvestigations*`, `DeleteInvestigation*`, `AnalyzeReport*`,
`SaveSettings*`) together in isolation: all 31 still pass unchanged.

## 9. Adversarial audit result

- No Qt/PySide6, FastAPI, or Tauri/Rust imports added to
  `app/application/*` (grepped directly — none found; the only
  "PySide6" hit anywhere in the package is a pre-existing, untouched
  docstring line in `app/application/__init__.py`).
- No `VirusTotalClient` or other provider-specific import introduced
  (grepped — none found); this command never reaches
  `app/threat_intel/*`.
- No provider-specific model exposed as a DTO.
- Exactly one new `dispatch()` branch, one new `COMMAND_HANDLERS`
  entry (both confirmed: `COMMAND_HANDLERS` has exactly 8 keys now,
  matching 8 implemented commands; `grep -n '"export_report"'
  handlers.py` shows exactly one `if name ==` branch and one dict
  entry).
- Response envelope shape (`{"success", "data", "error"}` via `ok()`)
  is identical to every other command; no bespoke envelope introduced.
- `app/api/app.py`, `app/threat_intel/`, `src-tauri/`, `frontend/src/`
  confirmed byte-identical to the Part 5 checkpoint via `diff -rq
  --exclude=__pycache__` — no accidental Phase 4C or Phase 4E
  modification.
- `app/reporting/`, `app/database/`, `app/settings/`, `app/gui/`
  confirmed byte-identical to the Part 5 checkpoint via the same
  `diff -rq` — no accidental domain-code modification.
- `app/exceptions.py`, `app/application/errors.py`,
  `app/application/events.py`, `app/application/responses.py`
  confirmed byte-identical — no accidental change to shared
  infrastructure this slice didn't need to touch.
- No accidental changes to any of the seven previously-completed
  commands — confirmed both by `diff` (only `dto.py` and `handlers.py`
  changed within `app/application/`, both additively) and by
  re-running their test classes together (§8).

## 10. Documentation changes

Created `docs/phase4/PHASE4D_PART6_IMPLEMENTATION.md` only. No freeze
created, Phase 4D not claimed complete, no historical document
rewritten, SSE not implemented.

## 11. Remaining Phase 4D commands

`enrich_ioc`, `get_threat_intelligence` — neither started; both remain
blocked exactly as Part 4/Part 5 documented (no standalone per-IOC
enrichment call site; `get_threat_intelligence`'s natural backing still
lives under `app/gui/`). `GET /events` SSE remains an honest 501,
untouched by this slice.

## 12. Known limitations

- `export_report` supports exactly the four formats `ReportingService`
  implements (`html`, `pdf`, `json`, `markdown`). CSV export
  (`app.gui.utils.csv_exporter.export_investigations_to_csv`) is
  **not** wrapped by this command: that function's signature takes a
  *list* of investigations (a bulk/history-page export), not one, and
  no call site was found that exports a single investigation to CSV —
  wrapping it here would mean inventing a new single-investigation CSV
  contract, not extracting an existing one. If a single-investigation
  CSV export is wanted later, it needs its own source-verified contract
  first, the same standard this slice held `enrich_ioc` and
  `get_threat_intelligence` to.
- `ExportReportCommandHandler` does not call
  `ReportingService.build_default_filename()` — the command requires
  the caller to supply a full `output_path`, matching every confirmed
  domain method's actual signature; filename defaulting is a GUI-only
  save-dialog concern (`MainWindow._select_export_path`) with no
  equivalent in the command contract, so none was invented.
- A write failure (disk full, permission denied, nonexistent parent
  directory) surfaces as the existing generic `INTERNAL_ERROR` code,
  not a dedicated `EXPORT_ERROR` code — `app/reporting/*`'s exporters
  raise a bare `RuntimeError` (json/markdown/html) or let a raw
  `OSError` propagate (pdf), neither of which is a `SOCIQError`
  subclass with an existing entry in `errors.py`'s exception-code map.
  This is the same documented gap `errors.py`'s own module docstring
  already notes for `app/reporting/*` in general (no per-module
  exception hierarchy exists to map from) — not a new gap introduced
  by this slice, and not silently invented around.
- This handler does not create the output path's parent directory
  itself; each exporter's own `mkdir(parents=True, exist_ok=True)`
  call (where present) or lack thereof (pdf) is preserved unchanged,
  matching the "existing domain/service code, called as-is" rule every
  prior slice has followed.
