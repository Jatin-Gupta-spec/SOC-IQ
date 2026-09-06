# SOC-IQ — Current State

Re-verified this session by direct filesystem inspection and a live test run. See §"Method"
in `PROJECT_CONSTITUTION.md`. This document summarizes; `PHASE4_NEXT_GENERATION_ARCHITECTURE_MASTER_PLAN.md`
§1 is the detailed CONFIRMED/LIKELY/UNKNOWN source.

## Repository shape (CONFIRMED, this session)

```
soc-iq/
├── app/                    Python domain + PySide6 GUI + CLI + new API/application layer
│   ├── api/                NEW (Phase 4D) — FastAPI route, requires fastapi (not installed here)
│   ├── application/        NEW (Phase 4D) — handlers.py, dto.py, events.py, responses.py, errors.py
│   ├── analyzer.py, extractor.py
│   ├── scoring/
│   ├── threat_intel/       still VirusTotal-specific — CONFIRMED, no provider abstraction in source
│   ├── database/
│   ├── settings/
│   ├── reporting/
│   ├── services/           dashboard/correlation/risk-explanation/system-health services
│   ├── gui/                PySide6 presentation: controllers, pages, widgets, components, design, events, workers
│   └── cli.py
├── tests/                  27 top-level test files + tests/gui/ (13 files) + tests/fixtures/
├── docs/                   extensive existing architecture/ADR/contracts/security/migration/phase4 docs
├── samples/                sample report text files for manual testing
├── config/settings.json
├── database/soc_iq.db
└── requirements.txt
```

**No `frontend/`, `src-tauri/`, or `backend/` directory exists at the repo root.** The
target directory structure (`FILE_STRUCTURE.md`, master plan §25) has not been created yet.

## What is implemented and working (CONFIRMED)

- Full Python domain: extraction, analysis, scoring, VirusTotal-backed threat intel,
  SQLite-backed persistence, 5-format reporting (JSON/CSV/Markdown/HTML/PDF), settings.
- PySide6 desktop GUI consuming that domain in-process (no IPC boundary — same interpreter).
- Thin CLI (`app/cli.py`) sharing the same domain modules as the GUI.
- A new, real (not mocked) application/API boundary for **3 commands**:
  `get_investigation`, `list_investigations`, `analyze_report` — see
  `app/application/handlers.py::COMMAND_HANDLERS`. Proven by
  `tests/test_application_layer.py`, not by the (currently non-runnable-here) FastAPI route.
- FastAPI HTTP route exists (`app/api/app.py`) but requires `fastapi`, which was not
  installed in this sandbox; it could not be exercised this session. Its own docstring
  states this is expected pre-install behavior, not a defect.
- `GET /events` SSE endpoint is a stub that raises `NotImplementedError` — documented as
  deferred work, not a bug (`app/api/app.py`, `docs/phase4/PHASE4D_API_EVENT_ARCHITECTURE.md` §22).

## What is NOT implemented (CONFIRMED)

- `ThreatIntelProvider` protocol / provider registry / normalized cross-provider verdict
  type — design-complete (`docs/phase4/PHASE4C_THREAT_INTEL_ARCHITECTURE.md`), zero source
  changes made for it yet.
- React frontend, Tauri/Rust shell — do not exist.
- Unified event model / SSE streaming — designed, not implemented.
- Database migration runner / schema-version table — does not exist in
  `app/database/connection.py` as of this snapshot.
- OS-backed secret storage for the VirusTotal API key — settings still store it as
  redacted-in-logs, plaintext-on-disk JSON (`app/settings/models.py`,
  `docs/security/secret-management-model.md`).
- The remaining commands/queries inventoried in `docs/contracts/PHASE4B_COMMAND_INVENTORY.md`
  and `PHASE4B_QUERY_INVENTORY.md` beyond the 3 wired so far.

## Test baseline (re-verified this session)

```
$ python3 -m pytest -q --ignore=tests/gui
399 passed in 0.99s
```

`tests/gui/` could not be collected in this sandbox: `ModuleNotFoundError: No module named
'PySide6'`. This is a sandbox limitation (PySide6 was not installed / no network access to
install it here), not a confirmed test failure. Earlier project documentation cites a
"542 tests passing" baseline that presumably includes the GUI suite — that combined number
was **not** independently re-verified this session. Re-run the full suite with PySide6
installed before relying on either figure.

## Known architectural defect, documented but not fixed

`app/services/risk_explanation_service.py` has a backend→GUI import direction that violates
the target layering. Found during Phase 4B, deliberately left unfixed per the
documentation-phase discipline (see `PROJECT_CONSTITUTION.md` §29). Confirm its status
directly in source before assuming it's still present.

## Addendum — Phase 4D command/event/SSE/frontend/Tauri completion (documentation reconciliation pass)

Everything above this line is preserved unedited as the historical record of what was true
in the session that wrote it (predating the SSE Part 1–4C implementation work, the frontend/
Tauri scaffolding, and the remaining 7 commands, all of which now exist in the repository).
This addendum corrects only the claims that later became false, per
`docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md` and this pass's own fresh
re-verification. This is a **documentation reconciliation pass only** — no implementation
source was changed to produce this addendum.

### Repository shape — correction

**`frontend/` and `src-tauri/` directories now exist at the repo root**, contradicting the
"No `frontend/`, `src-tauri/`, or `backend/` directory exists" line above (which was true
only of the earlier snapshot that line describes). Current shape adds:

```
soc-iq/
├── frontend/src/shared/events/    useEventStream.ts, eventSourceManager.ts (EventSource consumer)
├── frontend/src/shared/api/       client.ts (resolves sidecar origin via Tauri invoke())
├── src-tauri/src/lib.rs           get_sidecar_origin command (registered once)
├── sidecar-core/                  Rust process-supervision logic src-tauri builds on
```

### What is implemented and working — corrections

- The application/API boundary is no longer "3 commands". **All 10 commands** now exist in
  `app/application/handlers.py::COMMAND_HANDLERS` (`get_investigation`,
  `list_investigations`, `analyze_report`, `delete_investigation`,
  `search_investigations`, `get_iocs`, `save_settings`, `export_report`, `enrich_ioc`,
  `get_threat_intelligence`), each routed through one `dispatch()` function. Proven by
  `tests/test_application_layer.py`, 77/77 passing this session.
- FastAPI HTTP route (`app/api/app.py`) is no longer "could not be exercised" — `fastapi` is
  installed in this environment and the route runs; `tests/test_api_layer.py`, 29/29 passing
  this session.
- **`GET /events` is no longer a `NotImplementedError` stub.** It is a real `StreamingResponse`
  with SSE framing (`id:`/`event:`/`data:`, blank-line termination), a heartbeat emitted as an
  SSE comment frame (structurally distinct from a named event, so it cannot be
  misinterpreted as an application event by a spec-compliant client), and
  disconnect/subscriber cleanup. See `docs/phase4/PHASE4D_SSE_ARCHITECTURE_DECISION.md` and
  the SSE Part 1–4C docs for the build history.
- The unified event model exists and is live: `app/application/events.py` (`Event`, frozen/
  immutable, `event_id`/`correlation_id`) and `app/application/broker.py` (`EventBroker`,
  bounded per-subscriber queues, thread-safe). `EventCollector` compatibility is preserved.
  Exercised by `tests/test_event_broker.py`, 37/37 passing this session.
- A React frontend exists: `frontend/src/shared/events/useEventStream.ts` and
  `eventSourceManager.ts` implement the `EventSource` consumer;
  `frontend/src/shared/api/client.ts` resolves the sidecar origin via a real
  `invoke<string>("get_sidecar_origin")` call rather than a fixed port. `npm install` (73
  packages), `npm run typecheck` (0 errors), and `npm run build` (44 modules) all ran clean
  this session.
- A Tauri/Rust shell exists at the source level: `src-tauri/src/lib.rs` has exactly one
  `#[tauri::command]` (`get_sidecar_origin`), registered exactly once. **This is a
  source-implemented finding, not a compiled/runtime-verified one** — see the toolchain
  limitation below.

### What is NOT implemented — corrections

- `ThreatIntelProvider` protocol / provider abstraction is **no longer** "design-complete,
  zero source changes" — it is implemented and frozen (see
  `docs/architecture/IMPLEMENTATION_STATUS.md` Addendum 1 and `docs/phase4/PHASE4C_FREEZE.md`).
  This line was already stale before this pass; corrected here too since this document
  repeats the claim independently.
- "React frontend, Tauri/Rust shell — do not exist" is no longer true; see above. Compiled/
  runtime verification of `src-tauri` specifically remains outstanding (see below).
- "Unified event model / SSE streaming — designed, not implemented" is no longer true; see
  above.
- The "remaining commands... beyond the 3 wired so far" line is stale — all 10 are wired.

Database migration runner, OS-backed secret storage, and the risk-explanation-service
import-direction defect above were **not** re-checked this pass and may still be accurate as
written; this addendum does not touch them.

### Rust toolchain limitation (explicit, not hidden)

`src-tauri` has never compiled successfully in any session of this project, including this
one. This environment's `cargo`/`rustc` is **1.75.0**; a transitive dependency (`dlopen2
0.8.2`) requires the `edition2024` Cargo feature, needing cargo **≥1.85**. Reproduced fresh
this session (`cargo check` in `src-tauri/`, identical error). This is an **external
toolchain-version verification blocker** — not a defect discovered in `src-tauri`'s own
source. No dependency was downgraded and no `Cargo.toml` edit was made to force a pass.
`sidecar-core` (the crate `src-tauri` depends on for process supervision) compiles cleanly on
this same toolchain and passes 49/49 tests this session.

### Test baseline (this addendum's own session, fresh — currently executed, not historical)

```
$ pytest tests/ --ignore=tests/gui -q          → 600 passed
$ QT_QPA_PLATFORM=offscreen pytest tests/gui -q → 154 passed
$ python3 -m unittest tests.test_application_layer -v → 77 passed
$ python3 -m unittest tests.test_event_broker -v      → 37 passed
$ pytest tests/test_api_layer.py -q                    → 29 passed
$ pytest tests/test_sidecar_entrypoint.py -q            → 8 passed
$ (cd sidecar-core && cargo test)                        → 49 passed
$ (cd src-tauri && cargo check)                           → BLOCKED (edition2024, cargo 1.75.0)
$ (cd frontend && npm run typecheck)                       → 0 errors
$ (cd frontend && npm run build)                            → 44 modules, success
```

These counts match `docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md` exactly; they were
independently reproduced this session, not copied forward.

**Phase 4D status: IMPLEMENTATION COMPLETE. NOT YET FROZEN.** The freeze decision itself is
out of scope for this documentation-reconciliation pass — see
`docs/phase4/PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md` for the freeze-readiness verdict
(CONDITIONAL GO) and `docs/phase4/PHASE4D_FREEZE_REMEDIATION.md` for this pass's own record.
