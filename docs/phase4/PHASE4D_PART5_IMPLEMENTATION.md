# Phase 4D Part 5 — `save_settings` Vertical Slice

**Status:** Complete for the one command implemented here. Builds on the
verified Phase 4D Part 4 checkpoint (`get_investigation`,
`list_investigations`, `analyze_report`, `delete_investigation`,
`search_investigations`, `get_iocs` — 505 non-GUI / 659 offscreen / 48
application+API tests, all reproduced fresh before this slice was
started). This is **not** a Phase 4D freeze and does not claim Phase 4D
complete — 3 named commands (`export_report`, `enrich_ioc`,
`get_threat_intelligence`) remain unimplemented, and `GET /events` SSE
remains an honest 501.

## 1. Checkpoint audit performed before any change

No new archive was uploaded with the Part 5 brief, so the Part 4 output
ZIP (`SOC-IQ-Phase4D-Part4-Command-Slice.zip`) was re-extracted fresh
into a clean directory and verified directly, rather than trusting the
brief's description or reusing an in-memory copy:

| Item | Result |
|---|---|
| Six completed commands (`get_investigation`, `get_iocs`, `list_investigations`, `delete_investigation`, `search_investigations`, `analyze_report`) | Present — confirmed by direct read of `handlers.py`'s `COMMAND_HANDLERS` dict |
| Phase 4C provider abstraction (`app/threat_intel/provider.py`, `virustotal_provider.py`) | Present |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| `docs/phase4/PHASE4D_PART4_IMPLEMENTATION.md` | Present |
| `app/application/`, `app/api/` architecture | Intact, unchanged shape (5 files / 3 files) |
| Pre-existing Phase 4E scaffolding (`app/api/entrypoint.py`, `GET /health`, `src-tauri/`, `frontend/src/`) | Present, confirmed untouched by this slice (byte-identical to the Part 4 checkpoint — verified with `diff`) |
| Baseline tests | **505 passed** (non-GUI) / **659 passed** (offscreen) / **48 passed** (application+API) — reproduced fresh this session, matches the brief's stated baseline exactly |

## 2. Command selected: `save_settings`

Evaluated all four remaining named candidates:

- `export_report` — `docs/contracts/PHASE4B_COMMAND_INVENTORY.md` still
  explicitly says this was never confirmed as a discrete command vs. a
  UI-only export action, and still escalates reading
  `app/reporting/service.py` / `app/gui/utils/csv_exporter.py` as an
  unresolved precondition. Not selected — no stronger contract than
  Part 4 found.
- `enrich_ioc` — `PHASE4B_COMMAND_INVENTORY.md` still states outright
  that no standalone per-IOC enrichment call site exists; TI enrichment
  only happens inside `analyze_report`, for a whole investigation.
  Implementing this would still be new functionality, not an
  extraction. Not selected.
- `get_threat_intelligence` — unchanged from Part 4's assessment: its
  natural backing (`app.gui.services.ioc_detail_context
  .build_investigation_threat_intel_overview`) still lives under
  `app/gui/`, still takes GUI-adjacent inputs
  (`api_key_configured`), and still depends on
  `app.gui.utils.ioc_significance`. Wrapping it would mean either a new
  `app.gui` import into `app/application` (forbidden coupling) or
  reimplementing its logic (invented behavior). Deferred again, not
  selected.
- **`save_settings` — selected.** `PHASE4B_COMMAND_INVENTORY.md` called
  the name "inferred" and flagged the underlying service as
  "not independently verified" at the time it was written. Direct
  inspection this session of `app/settings/service.py` and
  `app/settings/models.py` (both outside that earlier doc's stated file
  list) confirms a real, already-tested, already-injectable contract:
  `SettingsService.update_api_key(str)`,
  `.update_export_directory(str)`, `.update_theme(str)` — three
  distinct, single-responsibility methods, each already covered by
  `tests/test_settings.py`. The three confirmed GUI emit sites in
  `app/gui/pages/settings_page.py` (`events.settings_changed.emit(...)`)
  each send exactly one of the three keys, never bundled — resolving
  the "not decided here" ambiguity `PHASE4B_COMMAND_INVENTORY.md` had
  originally flagged, without requiring any new domain code. This is
  now the strongest, most source-verified contract of the four
  remaining candidates and requires the least invented behavior.

## 3. Exact existing contract used

- `app/settings/models.py` — `ApplicationSettings` (`virustotal_api_key`,
  `export_directory`, `theme`), unchanged, not touched.
- `app/settings/service.py` — `SettingsService.update_api_key`,
  `.update_export_directory`, `.update_theme`, all pre-existing,
  unchanged, not touched. Each internally calls `load_settings()` then
  `save_settings()` — no new domain logic was written for this slice.
- `app/gui/pages/settings_page.py` — confirmed (read-only, not modified)
  that `virustotal_api_key` is the only one of the three fields with an
  existing blank-rejection rule (`if not key: QMessageBox.warning(...)`
  before calling `update_api_key`); `export_directory` and `theme` have
  no such rule at the GUI layer. The new DTO's validation mirrors this
  exactly rather than inventing a uniform rule across all three.

## 4. Implementation

- `app/application/dto.py` — added `SaveSettingsRequest` (frozen
  dataclass, three optional fields —
  `virustotal_api_key: str | None`, `export_directory: str | None`,
  `theme: str | None` — all defaulting to `None`). `__post_init__`
  rejects any payload that doesn't set exactly one of the three fields,
  rejects a non-string value for whichever field is set, and rejects a
  blank/whitespace-only `virustotal_api_key` specifically (matching
  §3's GUI-layer rule; no equivalent rule added for the other two
  fields, since none exists in source).
- `app/application/handlers.py` — added `SaveSettingsCommandHandler`,
  constructed the same way as every other handler
  (`SettingsService | None` injection point). Routes to whichever
  `update_*` method matches the one field the DTO validated, then
  returns `ok({"field": <name>, "updated": True})`. The persisted value
  itself is never echoed back in the response envelope — a deliberate,
  uniform choice across all three fields (not special-cased just for
  the API key) that extends the redaction intent already documented in
  `docs/security/secret-management-model.md` ("log-safe, disk-unsafe")
  to the command-response boundary as well.
- `app/application/handlers.py` `dispatch()` — added one
  `if name == "save_settings":` branch, positioned directly after
  `get_iocs`. Falls through the same `CommandValidationError` /
  `TypeError` / catch-all `Exception` → `code_for_exception()`
  translation every other command already uses.
- `app/application/handlers.py` `COMMAND_HANDLERS` — added one entry:
  `"save_settings": lambda payload: dispatch("save_settings", payload)`.
- `app/api/app.py` — **not modified.** `POST /commands/{name}` already
  routes generically through `COMMAND_HANDLERS`.

## 5. Files created/modified

- Modified: `app/application/dto.py`, `app/application/handlers.py`,
  `tests/test_application_layer.py`, `tests/test_api_layer.py`.
- Created: `docs/phase4/PHASE4D_PART5_IMPLEMENTATION.md` (this file).
- Not touched: everything else, including all Phase 4C source, all five
  previously-implemented command handlers/DTOs, `app/api/app.py`,
  `app/api/entrypoint.py`, `src-tauri/`, `frontend/`.

## 6. Tests added (11 total)

`tests/test_application_layer.py` (10):
`SaveSettingsCommandHandlerTests` — updates API key / export directory /
theme, updating one field does not clobber others (mirrors
`tests/test_settings.py`'s own `test_updating_one_field_does_not_clobber_others`),
rejects no field provided, rejects more than one field provided, rejects
blank API key, rejects non-string value, dispatched via command name —
plus one entry in `DispatchErrorTranslationTests`
(`test_save_settings_translates_unexpected_service_exception`).

`tests/test_api_layer.py` (1):
`test_save_settings_validation_error_never_reaches_domain` — the only
save_settings case exercised through the live HTTP transport, and
deliberately so: every *valid* save_settings payload is a real write to
the project's own `config/settings.json`, and this file's own module
docstring already restricts HTTP-layer tests to read-only/validation-only
paths to avoid mutating real state. Verified directly this session
(`config/settings.json` diffed byte-for-byte before and after the test
run) that the validation-rejection path never reaches `SettingsService`
and never touches the file.

## 7. Focused test results

`pytest tests/test_application_layer.py -q -k "SaveSettings or save_settings"`
→ **10 passed**.
`pytest tests/test_api_layer.py -q -k "save_settings"` → **1 passed**.

## 8. Fresh full-suite results

| Suite | Before this slice | After this slice |
|---|---|---|
| `pytest tests/ -q --ignore=tests/gui` | 505 passed | **516 passed** (+11) |
| `QT_QPA_PLATFORM=offscreen pytest tests/ -q` | 659 passed | **670 passed** (+11) |
| `pytest tests/test_application_layer.py tests/test_api_layer.py -q` | 48 passed | **59 passed** (+11) |

Zero regressions, zero skips — the +11 matches the 11 tests added exactly.
Re-ran every previously-completed command's own test classes
(`GetInvestigation*`, `ListInvestigations*`, `SearchInvestigations*`,
`DeleteInvestigation*`, `AnalyzeReport*`, `GetIocs*`) in isolation: all
22 still pass unchanged.

## 9. Adversarial audit result

- No Qt/PySide6, FastAPI, or Tauri/Rust imports added to
  `app/application/*` (grepped directly — none found).
- No direct `VirusTotalClient` usage introduced (grepped — none found).
- No provider-specific model exposed as a DTO — this command never
  reaches `app/threat_intel/*`; the provider-neutral-error check does
  not apply to this slice.
- Exactly one new `dispatch()` branch, one new `COMMAND_HANDLERS` entry
  (both counts confirmed at 7, matching 7 implemented commands).
- Response envelope shape (`{"success", "data", "error"}` via `ok()`) is
  identical to every other command; no bespoke envelope introduced.
- `app/api/app.py`, `src-tauri/`, `frontend/src/` confirmed
  byte-identical to the Part 4 checkpoint via `diff` — no accidental
  Phase 4E modification.
- No accidental changes to Phase 4C or to any of the six previously
  completed commands — confirmed both by `diff` (Phase 4C files
  untouched) and by re-running their test classes (§8).

## 10. Documentation changes

Created `docs/phase4/PHASE4D_PART5_IMPLEMENTATION.md` only. No freeze
created, Phase 4D not claimed complete, no historical document rewritten.

## 11. Remaining Phase 4D commands

`export_report`, `enrich_ioc`, `get_threat_intelligence` — none started.
`GET /events` SSE remains an honest 501, untouched by this slice.

## 12. Known limitations

- `save_settings` accepts exactly one field per call, matching every
  confirmed real call site — a caller wanting to update all three
  settings must send three separate commands. This is a direct mirror
  of current GUI behavior, not a new constraint invented for this
  slice.
- The persisted `virustotal_api_key` remains plaintext on disk
  (`config/settings.json`) after this command runs, unchanged from
  before this slice — `docs/security/secret-management-model.md`
  already documents this as current-state ("log-safe, disk-unsafe") and
  scopes the OS-secure-storage migration to Phase 4M, out of scope here.
- `get_threat_intelligence`'s natural implementation still depends on
  GUI-adjacent code (unchanged blocker from Part 4 — see §2).
