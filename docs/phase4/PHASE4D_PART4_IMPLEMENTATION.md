# Phase 4D Part 4 — `get_iocs` Vertical Slice

**Status:** Complete for the one command implemented here. Builds on the
verified Phase 4D Part 3 checkpoint (`get_investigation`,
`list_investigations`, `analyze_report`, `delete_investigation`,
`search_investigations` — 498 non-GUI / 652 offscreen / 41
application+API tests, all reproduced fresh before this slice was
started). This is **not** a Phase 4D freeze and does not claim Phase 4D
complete — 4 named commands (`save_settings`, `export_report`,
`enrich_ioc`, `get_threat_intelligence`) remain unimplemented, and
`GET /events` SSE remains an honest 501.

## 1. Checkpoint audit performed before any change

All items verified directly against the uploaded archive before touching
anything:

| Item | Result |
|---|---|
| `app/threat_intel/models.py`, `provider.py`, `virustotal_provider.py` | Present |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| `app/application/`, `app/api/` | Present, 5 files / 3 files respectively |
| `get_investigation`, `list_investigations`, `analyze_report`, `delete_investigation` | Present, all four command handlers confirmed by direct read of `handlers.py` |
| `search_investigations` (Part 3's command) | Present — `SearchInvestigationsRequest`/`SearchInvestigationsCommandHandler`, dispatch entry, `COMMAND_HANDLERS` entry, all confirmed by direct read |
| Baseline tests | **498 passed** (non-GUI) / **652 passed** (offscreen) / **41 passed** (application+API) — reproduced fresh this session |

**One checkpoint observation, not a blocker, carried forward unchanged
from Part 3's own audit:** this archive already contains
`app/api/entrypoint.py`, a `GET /health` route, a `src-tauri/` Rust
shell, and a `frontend/src/` React tree, all attributed by their own
docstrings/status headers to a later phase (Phase 4E Part 1,
`docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md` and
`docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md`) that predates this
snapshot. This was already flagged as pre-existing and non-blocking by
both Part 3's own checkpoint audit and
`docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md` §4/§16 before this
session began. It is unrelated to the command-slice pipeline
(`DTO → handler → dispatch → API`), was not touched by this pass
(confirmed: no diff to `app/api/entrypoint.py`, `src-tauri/`, or
`frontend/`), and does not conflict with anything this document claims.
Re-flagged here only for continuity, per this brief's own "do not trust
the checkpoint summary blindly" instruction.

## 2. Command selected: `get_iocs`

Evaluated the four remaining named candidates (`save_settings`,
`export_report`, `enrich_ioc`, `get_iocs`, `get_threat_intelligence` —
five, not four, until this slice removes one):

- `save_settings` — `docs/contracts/PHASE4B_COMMAND_INVENTORY.md` itself
  calls the name "inferred," documents three different, never-bundled
  payload shapes, and explicitly says the one-command-vs-three-commands
  split "is not decided here, flagged for Phase 4D command-model
  design." Ambiguous contract — not selected.
- `export_report` — `PHASE4B_COMMAND_INVENTORY.md` explicitly says this
  was never confirmed as a discrete command vs. a UI-only action, and
  escalates reading `app/reporting/service.py` /
  `app/gui/utils/csv_exporter.py` as a precondition, not yet done.
  Ambiguous contract — not selected.
- `enrich_ioc` — `PHASE4B_COMMAND_INVENTORY.md` states outright that no
  standalone per-IOC enrichment call site exists today; TI enrichment
  only happens as one step inside `analyze_report`, for a whole
  investigation. Implementing this would be "new functionality, not an
  extraction" — exactly the invented-behavior this brief forbids. Not
  selected.
- `get_threat_intelligence` — real command, but its natural source-level
  backing (`app.gui.services.ioc_detail_context
  .build_investigation_threat_intel_overview`) lives under `app/gui/`,
  takes GUI-adjacent inputs (`api_key_configured`), and depends on
  `app.gui.utils.ioc_significance` — itself flagged in
  `docs/contracts/PHASE4B_QUERY_INVENTORY.md` as a mis-located module
  with "zero Qt dependency" that is nonetheless not part of
  `app/application` today. Wrapping it here would mean either pulling an
  `app.gui` import into `app/application` (a new architectural coupling,
  forbidden by this brief's "do not redesign" / adversarial-audit rules)
  or reimplementing its logic (invented behavior). Deferred, not
  selected.
- **`get_iocs` — selected.** `InvestigationSummaryDTO`'s own docstring
  already states the summary DTO "deliberately omits `iocs` /
  `threat_intelligence` ... Full IOC/TI detail belongs to the
  not-yet-implemented `get_iocs` / `get_threat_intelligence` commands."
  `Investigation.iocs` (`app/database/models.py`) is already loaded by
  the exact same `InvestigationService.get_by_id` call
  `GetInvestigationCommandHandler` already uses — no new query, no new
  domain call, no GUI-layer dependency. This is the strongest existing
  source-level contract and the lowest amount of invented behavior of
  the five remaining candidates.

## 3. Implementation

- `app/application/dto.py` — added `GetIocsRequest` (frozen dataclass,
  `investigation_id: int`, validation copied verbatim from
  `GetInvestigationRequest`/`DeleteInvestigationRequest`: reject
  non-int, reject `bool` masquerading as `int`, reject non-positive).
- `app/application/handlers.py` — added `GetIocsCommandHandler`,
  constructed the same way as every other handler
  (`InvestigationService | None` injection point), calling
  `self._service.get_by_id(request.investigation_id)`. Returns
  `INVESTIGATION_NOT_FOUND` (already an existing error code — no new
  code added) when the lookup misses, otherwise
  `ok({"investigation_id": ..., "iocs": investigation.iocs})`. `iocs`
  is a plain `dict[str, list[str]]` already on the domain object, not a
  domain object itself, so passing it through is consistent with
  `responses.py`'s "never a bare domain object" rule.
- `app/application/handlers.py` `dispatch()` — added one `if name ==
  "get_iocs":` branch, positioned directly after `get_investigation`,
  before `list_investigations`. Falls through the same
  `CommandValidationError` / `TypeError` / catch-all `Exception` →
  `code_for_exception()` translation every other command already uses —
  no new exception handling introduced.
- `app/application/handlers.py` `COMMAND_HANDLERS` — added one entry:
  `"get_iocs": lambda payload: dispatch("get_iocs", payload)`, matching
  every other entry exactly.
- `app/api/app.py` — **not modified.** `POST /commands/{name}` already
  looks up `COMMAND_HANDLERS.get(name)` generically; `get_iocs` is
  reachable over HTTP with zero transport-layer changes.

## 4. Error handling verified

| Case | Path | Result |
|---|---|---|
| Valid request, investigation exists | `GetIocsCommandHandler.handle` | `ok()` envelope with `investigation_id` + `iocs` |
| Valid request, investigation missing | same | `fail(INVESTIGATION_NOT_FOUND, ...)` |
| Invalid payload (`investigation_id` non-positive) | `GetIocsRequest.__post_init__` → `CommandValidationError` | `dispatch()`'s own `except CommandValidationError` → `fail(INVALID_COMMAND_PAYLOAD, ...)`; domain layer never reached (asserted at the HTTP boundary in `test_api_layer.py`, mirroring the existing `get_investigation` test) |
| Malformed/missing field | dataclass `__init__` → `TypeError` | `dispatch()`'s own `except TypeError` → `INVALID_COMMAND_PAYLOAD` (covered by the existing generic `DispatchTests`, not duplicated per-command) |
| Unexpected `DatabaseError` from `InvestigationService.get_by_id` | `dispatch()` catch-all `except Exception` → `code_for_exception()` | `fail("DATABASE_ERROR", ...)` — reproduced directly via `patch.object(InvestigationService, "get_by_id", side_effect=DatabaseError(...))`, mirroring the existing `get_investigation` translation test |
| Unknown command name | n/a — `get_iocs` is a known command | Not applicable to this slice; existing `UNKNOWN_COMMAND` path untouched |
| Provider failure | n/a — this command never reaches `app/threat_intel/*` | Not applicable |

No framework/infrastructure exception was observed able to escape either
`dispatch()` or the FastAPI route for this command.

## 5. Adversarial coupling audit (this slice's changed files only)

- No Qt (`PySide6`/`app.gui`) imports added to `app/application/*`.
- No FastAPI imports added to `app/application/*` (`app/api/app.py` was
  not touched).
- No Tauri/Rust files touched (`src-tauri/` untouched, confirmed).
- No direct `VirusTotalClient`/provider usage — this command never
  reaches `app/threat_intel/*`.
- No provider-specific model leaked into the DTO — `GetIocsRequest`
  carries only `investigation_id: int`; the response is a plain dict
  built explicitly in the handler, matching `delete_investigation`'s
  existing pattern.
- One dispatch branch, one `COMMAND_HANDLERS` entry — no duplicate
  registration.
- Response envelope shape (`{"success", "data", "error"}` via `ok()`) is
  identical to every other command; no bespoke envelope introduced.
- No duplicated handler logic beyond the deliberate, documented mirror
  of `GetInvestigationCommandHandler`'s lookup-and-404 shape (same
  pattern already reused by that handler itself — not new duplication
  this slice introduced).
- No accidental changes to `get_investigation`, `list_investigations`,
  `search_investigations`, `delete_investigation`, or `analyze_report` —
  confirmed by re-running their existing test classes unchanged and
  passing (§6).

## 6. Test results

| Suite | Before this slice | After this slice |
|---|---|---|
| `pytest tests/ -q --ignore=tests/gui` | 498 passed | **505 passed** (+7) |
| `QT_QPA_PLATFORM=offscreen pytest tests/ -q` | 652 passed | **659 passed** (+7) |
| `pytest tests/test_application_layer.py tests/test_api_layer.py -q` | 41 passed | **48 passed** (+7) |

Zero regressions, zero skips, zero unexplained deltas — the +7 matches
the 7 tests added (5 in `test_application_layer.py`:
`GetIocsCommandHandlerTests` × 4 +
`DispatchErrorTranslationTests.test_get_iocs_translates_unexpected_service_exception`;
2 in `test_api_layer.py`: `test_get_iocs_not_found_is_translated_not_raised`,
`test_get_iocs_validation_error_never_reaches_domain`).

## 7. Remaining Phase 4D commands

`save_settings`, `export_report`, `enrich_ioc`, `get_threat_intelligence`
— none started. `GET /events` SSE remains an honest 501, untouched by
this slice, as required.

## 8. Known limitations

- `get_iocs` returns the raw `iocs` dict exactly as stored on
  `Investigation` (`dict[str, list[str]]`, keyed by IOC type). It does
  not add significance/title/enrichment metadata — that richer,
  per-IOC view belongs to `get_threat_intelligence` and/or a future
  `get_ioc_detail`-style command, not this one.
- `get_threat_intelligence`'s natural implementation currently depends
  on GUI-adjacent code (`app.gui.services.ioc_detail_context`,
  `app.gui.utils.ioc_significance`); resolving that dependency
  direction is a precondition for implementing it cleanly and was
  intentionally left untouched by this slice (see §2).
