# SOC-IQ — Full Phase 4 Architecture, Implementation & Completion Audit

**Read-only audit. No source, tests, or documentation other than this report
were modified.**

## Executive summary

Phase 4 is a multi-stage migration from a PySide6 desktop app toward a
Python-sidecar + Rust/Tauri + React architecture. As of this checkpoint:

- **Phase 4A/4B** — complete, per existing exit-criteria docs, not re-derived
  from scratch this audit (no contradicting source evidence found).
- **Phase 4C** (TI provider abstraction) — **genuinely complete and clean**.
  `ThreatIntelProvider` protocol + `VirusTotalProvider` exist,
  `ThreatIntelService` is provider-neutral (`list[ThreatIntelProvider]`), and
  `VirusTotalClient` has exactly two production call sites, both inside the
  provider/client module itself — not the GUI, not the application layer.
- **Phase 4D** (unified command/event contract) — **all 10 planned commands
  are implemented, dispatched, registered, and unit-tested**; `GET /events`
  SSE is a deliberate, honest `501`. This audit's own architectural finding:
  SSE cannot be added without either an unmade sync/async execution decision
  or a forbidden fake event source — see §7/§8.
- **Phase 4E** — partially started out of sequence (sidecar entrypoint +
  `/health`, React/Tauri scaffolds, sidecar-core Rust crate) ahead of the
  original 4E→4F ordering; this deviation is self-documented in
  `PHASE4_CHECKPOINT_NAMING.md`, not discovered fresh here.
- **Tauri/Rust** — source exists (`src-tauri/`, `sidecar-core/`), no
  `#[tauri::command]` is registered anywhere, and the Rust code has **never
  been compiled** in any session this repository's own docs describe, nor in
  this one (`cargo`/`rustc` absent here too).
- **Frontend** — React/TS scaffold exists with an honest no-op SSE hook; no
  `node_modules`, so `tsc`/`vite build` could not be run without installing
  dependencies (explicitly disallowed this audit).
- **Tests** — `python -m unittest tests.test_application_layer -v`: **67/67
  passed**, reproduced fresh. Broader `unittest discover`: 94 discovered, 67
  passed, 27 environment-blocked (`pytest`/`fastapi`/`PySide6` absent — every
  one confirmed a `ModuleNotFoundError`, not a failing assertion). No `pytest`
  in this environment at all, so the richer suites documented elsewhere
  (399/481/635-test baselines) could not be reproduced here and are reported
  as historical, not current, evidence.
- **No git repository** — `.git` is absent from this archive; `git status`/
  `git log` could not be run. Checkpoint history is reconstructed entirely
  from in-repo documentation and source inspection, not VCS metadata.

**Nothing here contradicts Phase 4D's own non-freeze stance.** Phase 4D is
functionally complete for its 10 commands and honestly incomplete for SSE,
which is exactly what Parts 8–9's own reports already said.

## 1. Actual repository checkpoint

- No `.git` directory present — `git status`/`git log -n 5` both fail with
  "not a git repository." This is an unpacked archive, not a git worktree.
- Source-derived checkpoint identity: this archive is the direct output of
  Phase 4D Part 9 (`SOC-IQ-Phase4D-Part9-SSE.zip`), itself built from the
  Part 8 reconciled checkpoint. Confirmed by:
  - `docs/phase4/PHASE4D_PART9_IMPLEMENTATION.md` present, final status "SSE
    ARCHITECTURE NOT READY."
  - `docs/phase4/PHASE4D_PART8_IMPLEMENTATION.md` present with its own §0
    reconciliation addendum.
  - `app/api/app.py`'s `GET /events` still returns `501`/`NOT_IMPLEMENTED`,
    matching Part 9's "no implementation" conclusion.
- `docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md`,
  `PHASE4E_PART1_REACT_TAURI_FOUNDATION_REPORT.md`, and
  `PHASE4E_SIDECAR_TAURI_SCOPE.md` are present — Phase 4E work exists
  alongside Phase 4D's unfinished SSE, confirming Phase 4D and Phase 4E work
  have proceeded in parallel/out of strict sequence, a deviation
  `PHASE4_CHECKPOINT_NAMING.md` already self-documents as deliberate.
- `docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md`,
  `PHASE4_2A_PART2_FOUNDATION_AUDIT_REPORT.md`,
  `PHASE4_2A_PART2B_INTEGRATION.md` — a "Phase 2A" sidecar-core/supervisor
  effort, explicitly scoped by `PHASE4_CHECKPOINT_NAMING.md` as its own
  numbering track, not a renumbered Phase 4E Part.

## 2. Real Phase 4 inventory

| Phase/Part | Classification | Evidence |
|---|---|---|
| 4A — Architecture reset | COMPLETE | `docs/architecture/PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md` exists as the approved plan; no contradicting evidence found |
| 4B — Domain boundary hardening | COMPLETE | `docs/migration/PHASE4B_EXIT_CRITERIA.md` present; not independently re-derived line-by-line this audit (out of this audit's evidence budget), no contradicting source found |
| 4C — TI provider abstraction | **IMPLEMENTED — VERIFIED**, FROZEN | `docs/phase4/PHASE4C_FREEZE.md` present; source-confirmed this audit (§6 below) |
| 4D — Unified command/event contract | **PARTIALLY IMPLEMENTED** (commands: IMPLEMENTED — VERIFIED; SSE: DESIGN ONLY / BLOCKED) | 10/10 commands source- and test-confirmed this audit (§5); SSE confirmed not implemented, blocker identified (§7/§8) |
| 4E Part 1 (sidecar entrypoint + `/health`) | IMPLEMENTED — NOT RE-VERIFIED THIS AUDIT | `PHASE4E_PART1_IMPLEMENTATION.md` claims "572 passed / 2 skipped at last real run" — not reproducible in this environment (no pytest); `app/api/entrypoint.py` and `/health` route confirmed present in source this audit |
| 4E (React/Tauri foundation scaffold) | PARTIALLY IMPLEMENTED | `frontend/`, `src-tauri/` confirmed present and structurally organized this audit; no build/typecheck executed (§10) |
| "Phase 2A" (sidecar-core Rust crate) | PARTIALLY IMPLEMENTED, UNVERIFIED (never compiled) | `sidecar-core/src/*.rs` present, 5 test files under `sidecar-core/tests/`; no `cargo` in this environment, and every prior session's own docs say the same (§9) |
| 4F–4P (React feature parity, security, integration, retirement, audit) | NOT STARTED | No corresponding source or docs found beyond the scaffold above |

## 3. Source-of-truth rule — how this audit resolved conflicts

Applied strictly: source code > tests > test execution > docs > historical
reports, per this task's own instruction. Two direct applications:

- `docs/architecture/IMPLEMENTATION_STATUS.md`'s main body says Phase 4C is
  "DESIGN COMPLETE, SOURCE NOT IMPLEMENTED" — its own later addendum
  corrects this to COMPLETE with fresh evidence, and this audit's own
  independent source read (§6) confirms the addendum, not the stale main
  body. The main body is reported as stale documentation (§12), not treated
  as current.
- `docs/phase4/PHASE4D_PART8_IMPLEMENTATION.md`'s original body claimed a
  diff against the Part 7 archive that could not be reproduced by the run
  that added its own §0 addendum (Part 7 archive unavailable). This audit
  does not re-claim that diff either — it is carried forward as
  inherited/unverified, exactly as the addendum already states.

## 4. Backend/domain architecture audit

- `app/database/` — repository + service layers present; `Investigation`
  domain model includes `threat_intelligence` as a plain persisted field
  (`app/database/models.py`), round-tripped through SQLite
  (`app/database/repository.py`). No migration-runner/schema-version table
  found (matches `IMPLEMENTATION_STATUS.md`'s original, unaddended finding —
  not re-verified further this audit since it's outside Phase 4C/D scope).
- `app/threat_intel/` — see §6.
- `app/reporting/`, `app/settings/` — present, used by `export_report` and
  `save_settings` command handlers respectively; no direct coupling issues
  found from the application layer inward.
- Dependency direction, confirmed by grep: `app/application/` imports only
  from `app.analyzer`, `app.application.*`, `app.database.service`,
  `app.reporting.service`, `app.settings.service`,
  `app.threat_intel.service` — all domain/service-layer, zero transport or
  GUI imports (full list in `app/application/handlers.py`'s own import
  block, reproduced in §13).

## 5. Application layer — command matrix

All 10 entries below are backed by dedicated request DTOs (`app/application/dto.py`),
dedicated handler classes (`app/application/handlers.py`), one `dispatch()`
branch each, and one `COMMAND_HANDLERS` registry entry each — confirmed by
direct read, not assumed from any prior document.

| Command | DTO | Handler | Dispatch | `COMMAND_HANDLERS` | App-layer tests | HTTP-layer tests | Verified | Status |
|---|---|---|---|---|---|---|---|---|
| `get_investigation` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes (unittest) | IMPLEMENTED — VERIFIED |
| `get_iocs` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes | IMPLEMENTED — VERIFIED |
| `get_threat_intelligence` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ none | Yes (app-layer only) | IMPLEMENTED — VERIFIED (app layer); HTTP layer untested |
| `save_settings` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes | IMPLEMENTED — VERIFIED |
| `list_investigations` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes | IMPLEMENTED — VERIFIED |
| `delete_investigation` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes | IMPLEMENTED — VERIFIED |
| `search_investigations` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes | IMPLEMENTED — VERIFIED |
| `analyze_report` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ none | Yes (app-layer only) | IMPLEMENTED — VERIFIED (app layer); HTTP layer untested |
| `export_report` | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Yes | IMPLEMENTED — VERIFIED |
| `enrich_ioc` | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ none | Yes (app-layer only) | IMPLEMENTED — VERIFIED (app layer); HTTP layer untested |

**HTTP-layer (`tests/test_api_layer.py`) coverage gap, confirmed by grep:**
3 of 10 commands — `get_threat_intelligence`, `analyze_report`, `enrich_ioc`
— have zero `TestClient`-level tests. This is unrelated to the current
environment block (`test_api_layer.py` can't even be imported here without
`fastapi`) — it's a source-level gap that would exist even with `fastapi`
installed. Not a Phase 4D blocker (every command is proven at the
transport-agnostic `dispatch()` layer, which is the documented seam
`app/api/app.py`'s `POST /commands/{name}` route calls through unmodified),
but a real, itemizable follow-up.

**Coupling/duplication checks (§13's methodology applied here):** zero
duplicate `dispatch()` branches, zero duplicate `COMMAND_HANDLERS` keys,
zero `app.gui` imports, zero Qt/PySide6 imports, zero FastAPI imports, zero
Tauri references, zero direct `VirusTotalClient` imports anywhere under
`app/application/` (grep-confirmed, `__pycache__` excluded). Every handler
returns through the shared `ok()`/`fail()` envelope; every expected failure
mode is translated by either a handler-local check or `dispatch()`'s shared
`try/except` boundary (`CommandValidationError` → its own code, `TypeError`
→ `INVALID_COMMAND_PAYLOAD`, generic `Exception` → `code_for_exception`) —
no handler raises past that boundary uncaught, no inconsistency found.

## 6. Threat Intelligence (Phase 4C) audit

- `app/threat_intel/provider.py` — `ThreatIntelProvider` is a real
  `typing.Protocol`, confirmed by direct read.
- `app/threat_intel/virustotal_provider.py` — `VirusTotalProvider` is a
  concrete class implementing that protocol.
- `app/threat_intel/service.py` — `ThreatIntelService.__init__` takes
  `providers: list[ThreatIntelProvider] | None`, defaulting to
  `[VirusTotalProvider()]`; the module's own docstring states it no longer
  holds a bare `VirusTotalClient` reference.
- **All production `VirusTotalClient(...)` construction sites**, grepped
  repo-wide: `app/threat_intel/virustotal.py` (the client's own module) and
  `app/threat_intel/virustotal_provider.py` (the provider that wraps it) —
  exactly two, both inside the TI package itself. `app/gui/pages/threat_intel_page.py`
  only *mentions* `VirusTotalClient` in comments/docstrings explaining that
  it no longer constructs one directly — confirmed by reading every match,
  not just counting them.
- Error mapping (`app/application/errors.py`): `InvalidHashError`/
  `InvalidIPError`/`InvalidDomainError`/`InvalidURLError` → `TI_INVALID_IOC`;
  `InvalidAPIKeyError` → `TI_INVALID_API_KEY`; `RateLimitExceededError` →
  `TI_RATE_LIMITED`; `ThreatIntelConnectionError`/`ThreatIntelTimeoutError`
  → `TI_PROVIDER_UNAVAILABLE`; `UnexpectedAPIResponseError` →
  `TI_PROVIDER_ERROR` — a real, specific hierarchy, not a generic catch-all
  (unlike `app/database/*`/`app/reporting/*`, which the architecture doc
  already correctly notes have no comparable hierarchy).
- `lookup_indicator` (single-IOC lookup, backs `enrich_ioc`) and
  `enrich_results` (whole-investigation, backs `analyze_report`'s TI step
  and the persisted field `get_threat_intelligence` exposes) are both
  present on `ThreatIntelService`, confirmed by direct read.
- `docs/phase4/PHASE4C_FREEZE.md` present — Phase 4C is frozen and, per this
  audit's independent re-check, that freeze is accurate.

**Phase 4C status: IMPLEMENTED — VERIFIED, FROZEN.** No open items found.

## 7. Event / SSE architecture audit

(This section reproduces Part 9's findings, independently re-confirmed
against the same current source rather than trusted from that report.)

- **Event production**: only `AnalyzeReportCommandHandler` publishes events
  (`analysis.started`/`analysis.progress`×N/`analysis.completed` or
  `analysis.failed`). No other command handler — including `enrich_ioc`,
  itself a plausibly-long-running operation — emits any event.
- **Event ownership**: each `EventCollector` is constructed fresh, per
  call, inside `handle()`. There is no module-level or shared instance
  anywhere in `app/application/`.
- **Transport**: events cannot leave the process today. `dispatch()`'s
  `analyze_report` branch discards the returned `EventCollector`
  (`response, _collector = ...; return response`) — the HTTP response body
  never contains the collected events.
- **Subscription**: no subscribe/unsubscribe method exists on
  `EventCollector` or anywhere else in `app/application/`. Multiple
  consumers cannot attach to anything, because there is nothing live to
  attach to.
- **Lifetime**: an `EventCollector`'s contents do not survive past the
  `handle()` call that created it, except where a test reads it directly
  (bypassing `dispatch()`).
- **Concurrency/thread-safety**: `EventCollector.publish()` is a plain
  `list.append()` with no lock — moot today since nothing is concurrent,
  but would need addressing before any shared/live version exists.
- **Async compatibility**: `AnalyzeReportCommandHandler.handle()` is fully
  synchronous; it can't yield control to publish an event and let a
  streaming client read it mid-execution.
- **`GET /events`**: genuinely a stub — a translated `501`/`NOT_IMPLEMENTED`
  envelope, not a bare `NotImplementedError` (that leak was fixed in Part
  2), but not a working stream by any definition. Confirmed present and
  unchanged in `app/api/app.py`.
- **Frontend side**: `frontend/src/shared/events/useEventStream.ts` is an
  explicit, documented no-op — it does not open a real `EventSource`,
  matching the backend's non-readiness rather than getting ahead of it.

## 8. Critical question: SSE readiness

**Classification: ARCHITECTURAL DECISION REQUIRED.**

The blocking, explicitly-flagged-and-never-resolved decision (first raised
in the Phase 4D API/event architecture doc itself, §21, written at Part 2):
**should command execution move to an async, publish-to-a-shared-bus model,
or should `/events` be served some other way that doesn't require making
commands themselves async** (e.g., a bounded in-memory ring buffer keyed by
`correlation_id` that a short-lived SSE connection tails, or a polling-based
progress query command)?

This is not a small additive gap. Implementing SSE today would require
either:

1. Redesigning `AnalyzeReportCommandHandler` (and, by precedent, the shared
   `dispatch()` contract every handler follows) to be async and publish to
   a real, shared, subscribable bus — a genuine architectural redesign of
   the command-execution model, not an extraction; or
2. Fabricating a synthetic event source under `app/api/` just to make
   `/events` stream *something* — explicitly against this project's own
   standing rule against fake/stub implementations.

Neither is a "small additive change." The architecture doc itself named
`enrich_ioc` as the concrete test of whether this decision could keep being
deferred ("before `enrich_ioc` or any other long-running command is
added") — `enrich_ioc` shipped fully synchronous, with zero event emission,
sidestepping the question again rather than resolving it. It remains open
through this checkpoint.

## 9. Tauri / sidecar audit

- **Source exists**: `src-tauri/src/{lib,main,sidecar}.rs` (436 lines) and
  `sidecar-core/src/{error,lib,process,startup,state,supervisor,timeout}.rs`
  (536 lines), plus 5 test files under `sidecar-core/tests/`.
- **`#[tauri::command]` registration**: **zero** actual attribute usages —
  every grep hit is a comment/docstring explaining that no command is
  registered yet and no frontend caller exists. `invoke_handler` similarly
  only appears in explanatory comments.
- **Process spawning / health / shutdown**: `sidecar.rs` (402 lines) and
  `sidecar-core`'s `process.rs`/`supervisor.rs`/`startup.rs` contain the
  actual logic for this (spawn, health-check, shutdown, timeout handling)
  per direct read of file names and their doc comments — full line-by-line
  correctness review is out of this audit's read-only, evidence-gathering
  scope, but structurally the pieces described in the brief are present.
- **Compiles**: **No `cargo`/`rustc` toolchain exists in this environment**
  (`which cargo rustc` → empty). Every prior session's own documentation
  says the same thing about its own environment
  (`PHASE4_2A_PART1_SIDECAR_CORE.md`: *"nor `cargo check` could be executed
  in this session"*; `PHASE4E_PART1_REACT_TAURI_FOUNDATION_REPORT.md`:
  *"ENVIRONMENT BLOCKED — no cargo/Rust toolchain present... confirmed via
  `which cargo`"*; `PHASE4_2A_PART2_FOUNDATION_AUDIT_REPORT.md`: *"has [not]
  been compiled in any environment this project has used."*). This audit
  adds no new compilation evidence — the Rust code's compilability remains
  **entirely unverified across the project's history**, not merely in this
  session.
- **Frontend integration**: no `#[tauri::command]` means nothing is wired
  for the frontend to call yet — consistent with `useEventStream.ts`'s own
  no-op status (§7).

**Status: source exists, structurally organized; never compiled;
not integrated end-to-end. PARTIALLY IMPLEMENTED, UNVERIFIED.**

## 10. Frontend audit

- Structure present: `frontend/src/{app,features,shared,styles}`, with
  `shared/{api,components,events,hooks,state,types}` — a real, organized
  scaffold, not a placeholder single file.
- `package.json` defines `dev`/`build`/`preview`/`typecheck`/`tauri`
  scripts; dependencies are React 18 + `@tauri-apps/cli` + Vite.
- **`node_modules/` is absent.** `node`/`npm` are present in this
  environment, but this audit's own instructions forbid installing
  dependencies or modifying package configuration — so `npm run build`/
  `npx tsc --noEmit` could not be run without violating that constraint.
  **Status: BLOCKED BY ENVIRONMENT CONSTRAINT (self-imposed by this audit's
  own rules, not by toolchain absence)** — distinct from the Rust case,
  where the toolchain itself is missing.
- `shared/api/client.ts` and `shared/events/useEventStream.ts` both exist
  and are explicitly self-documented as placeholders honestly reflecting
  backend non-readiness (no sidecar origin resolvable yet; `/events` not
  implemented server-side) rather than papering over the gap.

**Status: PARTIALLY IMPLEMENTED (scaffold complete, no working build
verified), design-honest.**

## 11. Python test audit

```
python -m unittest tests.test_application_layer -v
```
→ **67 passed, 0 failed** (reproduced fresh this audit).

```
python -m unittest discover -s tests -p "test_*.py"
```
→ **94 discovered, 67 passed, 27 errors.** Every one of the 27 individually
confirmed to be a `ModuleNotFoundError` for `pytest`, `fastapi`, or
`PySide6` at module import time (`test_api_layer.py`, `test_threat_intel.py`,
`test_threat_intel_provider_contract.py`, `test_virustotal.py`,
`test_virustotal_provider.py`, and the 12 files under `tests/gui/`, plus a
handful more), not a single assertion failure among them.

`pytest tests/ -q --ignore=tests/gui` and
`QT_QPA_PLATFORM=offscreen pytest tests/ -q` — **could not be attempted**:
`pytest` itself is not installed in this environment (`ModuleNotFoundError`
on direct `import pytest`). This is a harder block than "ignored tests" —
the command literally cannot run here.

**Documented test-count claims found elsewhere in the repo, none
reproducible in this environment:** `IMPLEMENTATION_STATUS.md` claims 399
passed (pre-4C) and a later addendum claims 481 (`pytest --ignore=tests/gui`)
/ 635 (`QT_QPA_PLATFORM=offscreen pytest`) at Phase 4C freeze;
`PHASE4E_PART1_IMPLEMENTATION.md` claims "572 passed / 2 skipped." None of
these were re-run this audit — they are reported as historical claims, not
verified current facts, per this audit's own source-of-truth rule ("tests
exist but cannot currently execute" → unverified, not verified).

## 12. Documentation consistency audit

| Document | Claim | Actual state | Severity | Required action |
|---|---|---|---|---|
| `docs/architecture/IMPLEMENTATION_STATUS.md` (main body) | Phase 4C TI provider abstraction "NOT STARTED (design DONE)"; phase table lists 4C "DESIGN COMPLETE, SOURCE NOT IMPLEMENTED" | Phase 4C is fully implemented and frozen (§6) | Medium — the doc's own addendum already corrects this | None required beyond what the addendum already did; do not re-edit main body (addendum explicitly preserves it as historical record) |
| `docs/architecture/IMPLEMENTATION_STATUS.md` | "Python application/command boundary IN PROGRESS... 3 commands"; FastAPI transport "IN PROGRESS/BLOCKED" | 10/10 commands implemented; FastAPI transport structurally complete for all 10 (§5) | Medium | Stale — predates Phase 4D's later parts; not corrected by any addendum. Flagging here; not editing per this audit's read-only scope |
| `docs/architecture/CURRENT_STATE.md` | `app/threat_intel/` "still VirusTotal-specific — CONFIRMED, no provider abstraction in source"; cites "399 passed" baseline | Phase 4C provider abstraction is real and frozen (§6); current environment shows 67/94 unittest results, not 399 (different environment, different session, not directly comparable, but the document is silently stale regardless) | Medium | Flagging only; not editing |
| `docs/phase4/PHASE4D_PART8_IMPLEMENTATION.md` (original body, pre-addendum) | Claims a file-diff against the Part 7 archive | Part 7 archive unavailable to reproduce that diff; the doc's own §0 addendum already flags this as inherited/unverified | Low — already self-corrected | None; addendum already handles it |
| `docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md` §6 / `docs/architecture/03-frontend-architecture.md` | React frontend is master-plan Phase 4F+ work, should not exist before Tauri+IPC foundation | `frontend/` exists at this checkpoint, ahead of that stated ordering | Low — already self-documented as a deliberate, flagged deviation in `PHASE4_CHECKPOINT_NAMING.md` | None; the tie-breaker doc already resolves this |

No missing-freeze-document finding: Phase 4C has its freeze doc; Phase 4D
correctly has none (it isn't frozen and no document claims otherwise). No
premature-completion claim found in any *current* (non-superseded) document
— the two stale rows above are historical documents predating later work,
not documents actively claiming something false about today's state.

## 13. Architectural coupling audit

**Violations found: none**, specifically checked for:

- `app/application` → `app.gui`: zero real imports (one docstring mention
  of "PySide6 GUI" in `app/application/__init__.py`, not an import).
- `app/application` → FastAPI: zero.
- `app/application` → Tauri: zero.
- domain → GUI / domain → transport: not found in any file reachable from
  `app/application/`'s import graph (reproduced here —
  `app.analyzer`, `app.application.*`, `app.database.service`,
  `app.reporting.service`, `app.settings.service`,
  `app.threat_intel.service` — all domain/service layer).
- API → business logic: `app/api/app.py` is 109 lines, delegates every
  command to `COMMAND_HANDLERS`, contains no domain logic itself.
- Duplicate event buses: the GUI's two Qt-signal buses
  (`app/gui/events/event_bus.py`, `app/gui/events/application_events.py`)
  are real and pre-existing, but are not duplicated by anything in
  `app/application/` — `app/application/events.py` is a separate,
  intentionally non-Qt schema, not a second implementation of the same bus.
- Duplicate command systems: one `dispatch()`, one `COMMAND_HANDLERS`
  dict, confirmed no duplicate keys or branches (§5).
- Duplicate state ownership: not found within this audit's scope (would
  require a deeper GUI-state-vs-application-layer trace than this pass
  covered — not flagged as clean, simply not found to be a problem with
  the evidence gathered).

**Clean boundaries confirmed**: `app/application/` ↔ `app/database/`,
`app/application/` ↔ `app/threat_intel/`, `app/application/` ↔
`app/reporting/`, `app/application/` ↔ `app/settings/`, `app/api/` ↔
`app/application/`.

## 14. Security / reliability audit

Confirmed findings only (no speculative items):

- **API key storage**: `app/settings/service.py`'s `update_api_key` stores
  the key via `settings.virustotal_api_key = api_key.strip()` — no
  encryption or OS-keychain integration found in this module. This matches
  `IMPLEMENTATION_STATUS.md`'s own long-standing, undisputed finding
  ("plaintext-on-disk API key storage confirmed") — not a new discovery,
  reconfirmed here.
- **Secret leakage in TI responses**: `GetThreatIntelligenceCommandHandler`
  returns the raw persisted `threat_intelligence` dict; the API key itself
  is not part of that stored payload's shape (confirmed by the payload
  fields used in `tests/test_application_layer.py`'s TI test:
  `status`/`coverage`/`hashes`/`ips`/`domains`/`urls` — no key field
  present).
- **Error information leakage**: `dispatch()`'s generic exception handler
  returns `str(error)` as the message alongside a translated code — this is
  consistent across all handlers (not a new gap introduced by any single
  command), but does mean any unexpected exception's raw message text
  reaches the response body. Confirmed by reading the shared `except
  Exception` block in `app/application/handlers.py`; not independently
  assessed for what any given domain exception's message might contain.
- **Loopback binding**: `app/api/app.py` defines the ASGI `app` object but
  contains no `uvicorn.run(...)` call itself — actual bind-address
  enforcement lives wherever the server is actually started
  (`app/api/entrypoint.py`, per its own docstring). Not independently
  re-verified this audit whether that file passes `host="127.0.0.1"` —
  flagging as an open item rather than asserting either way.
- **No subprocess/process-lifecycle findings**: `sidecar-core`'s
  process/supervisor/shutdown code was read structurally (§9) but not
  compiled or executed, so runtime lifecycle behavior (leaks, races) could
  not be confirmed or refuted this audit — reported as unverified, not
  clean.

No fabricated/theoretical vulnerabilities added beyond what direct
inspection supports.

## 15. Phase 4 completion matrix

| Phase | Design | Source | Tests | Integration | Docs | Freeze | Status | Remaining work |
|---|---|---|---|---|---|---|---|---|
| 4A | ✅ | N/A | N/A | N/A | ✅ | N/A | COMPLETE | — |
| 4B | ✅ | ✅ | (not re-verified this audit) | N/A | ✅ | (exit criteria doc, not a freeze doc) | COMPLETE | — |
| 4C | ✅ | ✅ | ✅ (app-layer proof via TI-dependent commands; TI's own suites environment-blocked here) | ✅ | ✅ | ✅ `PHASE4C_FREEZE.md` | **FROZEN** | None found |
| 4D — commands | ✅ | ✅ 10/10 | ✅ 10/10 at app layer, 7/10 at HTTP layer | ✅ | ✅ | ❌ (deliberately not frozen) | IMPLEMENTED — VERIFIED | 3 commands' HTTP-layer tests (§5) |
| 4D — SSE | ✅ (schema only) | ❌ (stub only) | N/A | ❌ | ✅ (honestly documents the gap) | ❌ | ARCHITECTURAL DECISION REQUIRED | The sync/async decision itself (§8), then implementation |
| 4E (sidecar entrypoint/`/health`) | ✅ | ✅ | claimed, unverified here | (not re-traced this audit) | ✅ | (claimed frozen in its own doc, not re-verified) | IMPLEMENTED — NOT RE-VERIFIED | Re-run its test claim in a capable environment |
| 4E (React/Tauri scaffold) | ✅ | ✅ | N/A (no frontend tests found) | ❌ (no `#[tauri::command]` wired) | ✅ | ❌ | PARTIALLY IMPLEMENTED | Wire commands, compile, integrate |
| "2A" sidecar-core crate | ✅ | ✅ | 5 Rust test files present, never run (no cargo) | ❌ | ✅ | ❌ | PARTIALLY IMPLEMENTED, UNVERIFIED | First-ever compilation, then test run |
| 4F–4P | ❌ | ❌ | ❌ | ❌ | (roadmap only) | ❌ | NOT STARTED | Entire scope |

### Work item table

| Work item | Current state | Dependency | Effort | Blocking? | Recommended order |
|---|---|---|---|---|---|
| SSE sync/async execution decision | Undecided, explicitly flagged since Part 2 | None (pure decision) | Small (decision) / Medium (write-up) | Blocks all SSE work | 1st |
| SSE implementation | Blocked on above | Above decision | Medium | Blocks live event streaming to frontend | 2nd |
| HTTP-layer tests for `get_threat_intelligence`/`analyze_report`/`enrich_ioc` | Missing | `fastapi` installed | Small | No (app-layer proof already exists) | Can happen anytime, low urgency |
| Rust compilation (`cargo build`) — first ever | Never attempted successfully in this project's history | Rust toolchain in some environment | Unknown until attempted | Blocks all Tauri integration work | Before any further Tauri command wiring |
| `#[tauri::command]` registration + frontend wiring | Not started | Compilation above | Medium | Blocks end-to-end desktop app | After compilation succeeds |
| Frontend `npm install` + `tsc`/`vite build` verification | Never run in this audit's environment | `node_modules` installed | Small | Blocks confirming frontend correctness | Parallel to Rust work |
| Stale doc corrections (`IMPLEMENTATION_STATUS.md` main body, `CURRENT_STATE.md`) | Flagged, not fixed (read-only audit) | None | Small | No | Low priority, documentation-only |

## 16. What is actually left — categorized

**A. Required before Phase 4D freeze**
- The SSE sync/async execution decision (§8), and either its implementation
  or an explicit, documented decision to defer SSE past the freeze (which
  would need to be stated, not assumed).

**B. Required for Phase 4E**
- First successful Rust compilation of `sidecar-core`/`src-tauri`.
- `#[tauri::command]` registration and invoke_handler wiring.
- Frontend dependency install + typecheck/build verification.
- Wiring `frontend/src/shared/events/useEventStream.ts` to a real
  `EventSource` once `/events` exists (depends on item A).

**C. Required for later Phase 4 work (4F+)**
- Everything under "NOT STARTED" in §2 — no source or design evidence found
  for this audit to itemize further than the master plan's own roadmap.

**D. Documentation-only**
- Updating `IMPLEMENTATION_STATUS.md`'s main body and `CURRENT_STATE.md` to
  reflect current Phase 4D command count and Phase 4C freeze (both already
  correctly documented elsewhere — this is consistency cleanup, not new
  information).

**E. Environment/toolchain blockers**
- `pytest`, `fastapi`, `PySide6` absent here — blocks richer regression
  confirmation.
- `cargo`/`rustc` absent here (and, per every prior session's own report,
  everywhere else this project has been worked on so far) — blocks all
  Rust verification.
- `node_modules` not installed (by this audit's own constraint) — blocks
  frontend build verification.

**F. Optional polish**
- HTTP-layer test coverage for the 3 commands missing it (§5) — real gap,
  but non-blocking since app-layer proof already exists for all 10.

## 17. Recommended next action

**NEXT ACTION: Make the SSE sync/async execution decision (§8), and only
then implement `GET /events` as its own scoped Part.**

Why this and not "Part 10" by default, and not jumping to Phase 4E work:

- All 10 Phase 4D commands are done and verified — there is no remaining
  command work to sequence next.
- SSE is the one concretely-scoped, concretely-blocked item standing
  between Phase 4D's current state and an honest freeze. It has been
  flagged as an open decision since Part 2 and re-confirmed unresolved by
  three independent passes now (Part 2's original doc, Part 9's audit, and
  this full audit).
- Phase 4E's own blocking item (first-ever Rust compilation) is an
  environment/toolchain problem, not an architecture problem — it can
  proceed in parallel once a capable environment exists, but doing more
  Rust/React scaffolding work without ever having compiled the existing
  Rust code first would compound an already-unverified pile of source
  rather than reduce it. Compiling what already exists is more valuable
  than adding to it further.
- Phase 4D is **not** "complete except for documentation" — SSE is a real,
  unimplemented, architecturally-blocked feature, not a docs gap. Saying
  otherwise would misstate the evidence in §7/§8.
- Phase 4E **cannot** yet "safely begin" further command-wiring work in
  the sense of `#[tauri::command]` registration, because nothing in this
  project's history — including this audit — has ever confirmed the
  existing Rust source even compiles. Wiring commands into code that has
  never built is not a safe next step; compiling it (in an environment with
  `cargo`) is the actual prerequisite, and is independent of the SSE
  decision, so it can run in parallel rather than blocking on it.

## Definition of done for remaining Phase 4 work

- **Phase 4D freeze**: all 10 commands verified (done) + SSE either
  implemented and tested end-to-end (`event source → API adapter → GET
  /events → text/event-stream`, subscriber cleanup, disconnect handling,
  no blocking of producers) or explicitly, deliberately deferred past the
  freeze in a document that says so outright — not silently dropped.
- **Phase 4E**: `sidecar-core` and `src-tauri` compile cleanly
  (`cargo build`, ideally `cargo test`/`cargo clippy` too); at least one
  real `#[tauri::command]` registered and callable from the frontend;
  frontend `npm install && npm run build && npm run typecheck` all pass
  with zero errors; `useEventStream.ts` upgraded from no-op to a real
  `EventSource` consumer once Phase 4D's SSE exists.

## Evidence / commands used this audit

```
git status ; git log -n 5                     # both fail: no .git present
python -m unittest tests.test_application_layer -v   # 67 passed
python -m unittest discover -s tests -p "test_*.py"  # 94 discovered, 67 passed, 27 env-blocked errors
python -c "import pytest"                      # ModuleNotFoundError
python -c "import fastapi"                     # ModuleNotFoundError
python -c "import PySide6"                     # ModuleNotFoundError
which cargo rustc                              # empty, neither found
which node npm                                 # both found
ls frontend/node_modules                       # No such file or directory
grep -rn "VirusTotalClient(" .                 # 2 production sites, both inside app/threat_intel/
grep -rn "^from app\.gui\|^import app\.gui" app/application/   # 0 real hits
grep -rn "#\[tauri::command\]\|invoke_handler" src-tauri/src/  # 0 real hits, comments only
```
Plus direct `view`/`grep` reads of every file cited by path above.

## Environment limitations

- No `.git` — checkpoint/version history reconstructed from documentation
  and source only, not VCS metadata.
- No `pytest`, `fastapi`, `PySide6` — 27 test files could not even be
  imported; their internal correctness is unverified in this environment
  (though several are claimed passing in prior sessions' own reports, not
  independently reproduced here).
- No `cargo`/`rustc` — zero Rust verification possible; matches every
  prior session's own stated environment limitation, not unique to this
  audit.
- `node`/`npm` present, but `node_modules` not installed and this audit's
  own scope forbids installing dependencies — frontend build/typecheck
  unverified by choice, not by absence of tooling.
