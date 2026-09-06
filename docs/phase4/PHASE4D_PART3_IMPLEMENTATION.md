# Phase 4D Part 3 — `search_investigations` Vertical Slice

**Status:** Complete for the one command implemented here. Builds on the
verified Phase 4D Part 2 checkpoint (`get_investigation`,
`list_investigations`, `analyze_report`, `delete_investigation` — 488
non-GUI / 642 offscreen / 31 application+API tests, all reproduced fresh
before this slice was started). This is **not** a Phase 4D freeze and does
not claim Phase 4D complete — 5 named commands
(`save_settings`, `export_report`, `enrich_ioc`, `get_iocs`,
`get_threat_intelligence`) remain unimplemented, and `GET /events` SSE
remains an honest 501.

## 1. Checkpoint audit performed before any change

All items verified directly against the uploaded archive before touching
anything:

| Item | Result |
|---|---|
| `app/threat_intel/models.py`, `provider.py`, `virustotal_provider.py` | Present |
| `app/application/`, `app/api/` | Present, 5 files / 3 files respectively |
| `docs/phase4/PHASE4C_FREEZE.md` | Present |
| `docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md` | Present |
| `delete_investigation` (DTO, handler, dispatch entry, `COMMAND_HANDLERS` entry, 8 tests) | Present, all four command handlers confirmed by direct read of `handlers.py` |
| Baseline tests | **488 passed** (non-GUI) / **642 passed** (offscreen) / **31 passed** (application+API) — matches the prompt's stated baseline exactly |

**One checkpoint observation, not a blocker:** this archive also already
contains `app/api/entrypoint.py` and a `GET /health` route, both
documented in `docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md` as added in a
later phase (4E Part 1) predating this snapshot. That work is unrelated
to the command-slice pipeline (`DTO → handler → dispatch → API`), was not
touched by this pass, and does not conflict with anything this document
claims — noted here only because the Part 3 brief's checkpoint
description did not mention it and the brief itself says not to assume
the checkpoint matches the prompt without checking.

## 2. Command selected: `search_investigations`

Evaluated all six remaining candidates
(`save_settings`, `export_report`, `enrich_ioc`, `get_iocs`,
`get_threat_intelligence`, `search_investigations`) against
`docs/contracts/PHASE4B_COMMAND_INVENTORY.md`,
`docs/contracts/PHASE4B_QUERY_INVENTORY.md`,
`docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md`, and
`docs/phase4/PHASE4D_RECONCILIATION_AUDIT.md`. Only `search_investigations`
has a fully source-verified contract with no open design questions:

- **Existing domain/service capability:** `InvestigationService.find_by_report_name`
  → `InvestigationRepository.find_by_report_name`, exact-match, tested at
  `tests/test_database.py::test_find_by_report_name` /
  `test_find_by_report_name_no_match_returns_empty_list`.
- **Existing GUI-side contract:** `HistoryController.search_by_report_name`
  (`app/gui/controllers/history_controller.py`) — same method, plus a
  documented blank-input short-circuit (blank `report_name` → `[]`,
  never reaches the repository, since it is unverified whether the
  repository would treat an empty string as a wildcard).
- **Expected input:** `report_name: str` (blank permitted, non-string
  rejected).
- **Expected output:** list of investigation summaries, same shape as
  `list_investigations`.
- **Existing error semantics:** repository/database failures propagate as
  `DatabaseError`, already mapped in `app/application/errors.py`.
- **Dependencies:** `InvestigationService` only — same as
  `get_investigation`/`list_investigations`/`delete_investigation`.

Why the other five were rejected for this slice (not disqualified
forever, just not the strongest contract available right now):

- `enrich_ioc` — `PHASE4D_API_EVENT_ARCHITECTURE.md` §21 explicitly flags
  how a partially-succeeded bulk/enrichment response should be shaped as
  an **open question**, unresolved by any document.
- `save_settings` — `PHASE4B_COMMAND_INVENTORY.md` calls its own name
  "inferred," never confirms the underlying service, and explicitly
  defers the one-command-vs-three-commands payload-shape decision to
  "Phase 4D command-model design" (i.e., not decided anywhere yet).
- `export_report` — `PHASE4B_COMMAND_INVENTORY.md` explicitly says this
  is not confirmed as a discrete command vs. a UI-only action, and
  escalates reading `app/reporting/service.py` /
  `app/gui/utils/csv_exporter.py` as a precondition before finalizing
  the contract — not done in any prior phase.
- `get_iocs`, `get_threat_intelligence` — both are one-line entries in
  `docs/contracts/command-model.md` with no backing service method
  identified by any prior phase's source audit; `dto.py`'s own docstring
  lists both as "not-yet-implemented" with no contract attached.

## 3. What was implemented

1. **`app/application/dto.py` — `SearchInvestigationsRequest`.** Frozen
   dataclass, one field (`report_name: str`). Unlike
   `GetInvestigationRequest`/`DeleteInvestigationRequest`, blank input is
   *not* rejected by `__post_init__` — only a non-string value raises
   `CommandValidationError`. Blank is a legitimate "no search term" per
   the GUI-side contract, not a malformed payload.
2. **`app/application/handlers.py` — `SearchInvestigationsCommandHandler`.**
   Calls `InvestigationService.find_by_report_name` directly (not
   `HistoryController`), replicating that controller's documented
   blank-input short-circuit inline so `app.application` never imports
   `app.gui` — the same dependency-direction rule every existing handler
   in this file already follows. Maps results through the existing
   `InvestigationSummaryDTO.from_domain`, identical to
   `ListInvestigationsCommandHandler`.
3. **`dispatch()` and `COMMAND_HANDLERS`** — one new branch, one new dict
   entry, following the identical pattern of the four existing commands.
4. **No other file touched.** Confirmed by `find . -newer <upload>`: only
   `app/application/dto.py`, `app/application/handlers.py`,
   `tests/test_application_layer.py`, `tests/test_api_layer.py` changed.

## 4. Architecture of the vertical slice

```
SearchInvestigationsRequest (dto.py)
  -> __post_init__ validation (type check only; blank allowed)
  -> SearchInvestigationsCommandHandler.handle() (handlers.py)
  -> InvestigationService.find_by_report_name() (unmodified, existing)
  -> InvestigationSummaryDTO.from_domain() per result (existing)
  -> ok([...]) response envelope (responses.py, unmodified)
  -> dispatch("search_investigations", payload) (handlers.py)
  -> COMMAND_HANDLERS["search_investigations"] (handlers.py)
  -> POST /commands/search_investigations (app/api/app.py, unmodified —
     generic dispatch, no route-specific code needed)
```

No second architectural pattern introduced. No existing command touched.

## 5. Error boundary

- No Qt/FastAPI/Tauri imports added to `app/application/` (grep-verified:
  zero matches for `PySide6`, `PyQt`, `fastapi`, `tauri` in the two edited
  files).
- No `app.gui` import added — the two docstring mentions of
  `HistoryController` are prose references explaining *why* the handler
  doesn't import it, not imports themselves (grep-verified).
- `DatabaseError` from `find_by_report_name` is not caught locally by the
  handler; it propagates to `dispatch()`'s existing catch-all, which
  already maps it to `DATABASE_ERROR` — the same mechanism proven for
  `get_investigation`/`list_investigations`/`delete_investigation`. No new
  error-translation code was needed.
- No TI-exception → dispatch coverage added for this command: it never
  calls `ThreatIntelService`, so per Step 4's own instruction ("only add
  TI-exception → dispatch integration coverage if the selected command
  actually reaches ThreatIntelService"), none was forced in here. The
  pre-existing TI-exception → dispatch gap noted in
  `PHASE4D_RECONCILIATION_AUDIT.md` §7/§14 remains open, unrelated to this
  slice.

Tests added, by category:

- Validation failure: non-string `report_name` (handler-level + dispatch-level + API-level).
- "Not-found" behavior: no match returns `success: true, data: []` — not
  an error, matching `list_investigations`'s own empty-list semantics and
  `find_by_report_name`'s tested repository behavior.
- Infrastructure/database failure: `DatabaseError` from
  `find_by_report_name` translated to `DATABASE_ERROR` through `dispatch()`.
- Domain/blank-input short-circuit: blank name never reaches the
  repository, returns `[]`.
- Dispatch wiring: command reachable by name through `dispatch()`.
- API transport: three `test_api_layer.py` cases (no-match, blank,
  validation error) — all read-only against the real database per that
  file's existing constraint of not exercising mutating paths over HTTP.

## 6. Testing

```
Focused (new tests only):
tests/test_application_layer.py -k "SearchInvestigations or search_investigations": 7 passed
tests/test_api_layer.py -k "search_investigations": 3 passed

python3 -m pytest tests/ -q --ignore=tests/gui
498 passed  (488 baseline + 10 new, 0 failed, 0 skipped)

QT_QPA_PLATFORM=offscreen python3 -m pytest tests/ -q
652 passed  (642 baseline + 10 new, 0 failed, 0 skipped)

python3 -m pytest tests/test_application_layer.py tests/test_api_layer.py -q
41 passed  (31 baseline + 10 new, 0 failed, 0 skipped)
```

No existing test was modified, weakened, skipped, or deleted. The 10-test
delta is entirely new `search_investigations` coverage.

## 7. Adversarial audit findings

| Check | Result |
|---|---|
| Duplicate command registration | None — one `if name ==` branch, one `COMMAND_HANDLERS` entry |
| Duplicate DTO definitions | None — one `SearchInvestigationsRequest` class |
| Duplicate handler patterns | None — one `SearchInvestigationsCommandHandler` class |
| Inconsistent dispatch behavior | None — same try/except/translation path as the other four commands |
| Framework leakage (Qt/FastAPI/Tauri) into `app/application` | None found |
| `app.gui` import into `app/application` | None found (docstring mentions only) |
| Provider-specific (VirusTotal) leakage into DTOs | None found |
| Accidental modification of Phase 4C (`app/threat_intel/**`) | None — confirmed by `find . -newer <upload>`: only 4 files changed, all in `app/application/` and `tests/` |
| Accidental modification of Rust/Tauri/React (`src-tauri/`, `frontend/`, `sidecar-core/`) | None — untouched |
| Accidental behavior change to the existing four commands | None — their 13 tests re-run and re-pass unchanged |

**Verdict: zero findings requiring fixes.**

## 8. Remaining Phase 4D commands

`save_settings`, `export_report`, `enrich_ioc`, `get_iocs`,
`get_threat_intelligence` — none started, no stub/TODO present for any of
them (consistent with the Reconciliation Audit's prior finding for the
7-command backlog, now reduced to 5 after Part 2's `delete_investigation`
and this slice's `search_investigations`).

## 9. `/events` status

Unchanged. Still returns a translated `501 NOT_IMPLEMENTED` — real,
honestly documented gap, not touched this slice.

## 10. Known limitations

- `search_investigations` matches only on exact `report_name`, inherited
  unchanged from `InvestigationRepository.find_by_report_name` — no
  partial/fuzzy matching, since the underlying repository method doesn't
  support it and this slice does not add new repository behavior.
- The blank-input short-circuit is duplicated (once in
  `HistoryController`, once in `SearchInvestigationsCommandHandler`)
  rather than shared — consistent with this codebase's existing pattern
  of the application layer calling `InvestigationService` directly rather
  than the GUI controller layer (see `get_investigation` /
  `list_investigations` / `delete_investigation`, none of which reuse
  their `HistoryController`/`Controller` equivalents either).
- The TI-exception → dispatch end-to-end test gap (§7/§14 of the
  Reconciliation Audit) remains open — unrelated to this command, not
  addressed here per Step 4's scope.

## 11. Files created/modified

- `app/application/dto.py` — added `SearchInvestigationsRequest`.
- `app/application/handlers.py` — added `SearchInvestigationsCommandHandler`,
  one `dispatch()` branch, one `COMMAND_HANDLERS` entry.
- `tests/test_application_layer.py` — added `SearchInvestigationsCommandHandlerTests`
  (5 tests) plus one `DispatchTests` case and one `DispatchErrorTranslationTests`
  case (7 new tests total in this file).
- `tests/test_api_layer.py` — added 3 new `CommandRouteTests` cases.
- `docs/phase4/PHASE4D_PART3_IMPLEMENTATION.md` — this document (new).

No other file touched.
