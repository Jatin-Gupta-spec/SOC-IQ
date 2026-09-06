# SOC-IQ — Phase 4E Full Status + Architecture Reconciliation Audit

**Date:** 2026-08-24
**Audit type:** Read-only architecture/status audit against the uploaded
`SOC-IQ-Phase4D-FINAL-AUDITED-FULL-PROJECT.zip` checkpoint. No source, test,
frontend, Rust, or configuration file was modified to produce this document.
**This document and `PHASE4E_ARCHITECTURE.md` are the only two files added
this session.**

---

## 0. Checkpoint verification

**Result: PASS, with one self-documented deviation carried forward (not
newly discovered here).**

The archive extracts cleanly to 400+ tracked files. No `.git` directory is
present (consistent with every prior audit in this repo's own history — none
of them found one either). `docs/phase4/PHASE4D_FREEZE.md` is present and
concludes **CLASS B — FREEZE READY WITH DOCUMENTED ENVIRONMENT BLOCKER**,
dated 2026-08-24, itself built on `PHASE4D_FINAL_FREEZE_READINESS_AUDIT.md`
and `PHASE4D_FREEZE_REMEDIATION.md`. This matches what the task brief calls
"the final Phase 4D audited checkpoint."

The one discrepancy against a literal reading of the task brief: the brief's
own framing implies Phase 4E has not started ("DO NOT START PHASE 4E
IMPLEMENTATION"). In fact `docs/phase4/PHASE4E_PART1_IMPLEMENTATION.md`,
`PHASE4E_PART1_REACT_TAURI_FOUNDATION_REPORT.md`, and
`PHASE4E_SIDECAR_TAURI_SCOPE.md` already exist, and `app/api/entrypoint.py`,
`frontend/`, `src-tauri/`, and `sidecar-core/` all contain real code, not
placeholders.

**This is not a fresh discovery and is not treated as a STOP condition.**
`docs/phase4/PHASE4_CHECKPOINT_NAMING.md` is a checkpoint-naming
tie-breaker document that exists specifically because a prior session
already flagged this same deviation ("the current checkpoint... already
departed from" the strict 4E→4F ordering), and `PHASE4_FULL_STATUS_AUDIT.md`
(the Phase 4 audit that predates this one) independently documents the same
fact: *"Phase 4E — partially started out of sequence... this deviation is
self-documented in `PHASE4_CHECKPOINT_NAMING.md`, not discovered fresh
here."* Classification: **harmless and expected** — the archive is exactly
what its own documentation says it is, a Phase 4D-frozen checkpoint that
also contains Phase 4E scaffolding/implementation started ahead of the
original sequencing. Per §2 of the task brief ("whether the discrepancy is
harmless, material, or indicates a later checkpoint"): harmless, and this
audit proceeds.

Files read in full or in substantial part before writing this report:
`PHASE4D_API_EVENT_ARCHITECTURE.md`, `PHASE4D_SSE_ARCHITECTURE_DECISION.md`,
`PHASE4D_SSE_PART1-4C_IMPLEMENTATION.md`, `PHASE4D_FREEZE.md`,
`PHASE4C_FREEZE.md`, `PHASE4_FULL_STATUS_AUDIT.md`,
`PHASE4E_SIDECAR_TAURI_SCOPE.md`, `PHASE4E_PART1_IMPLEMENTATION.md`,
`PHASE4E_PART1_REACT_TAURI_FOUNDATION_REPORT.md`,
`PHASE4_CHECKPOINT_NAMING.md`, `docs/architecture/IMPLEMENTATION_STATUS.md`,
`docs/architecture/CURRENT_STATE.md`, plus direct inspection of every file
under `app/application/`, `app/api/`, `app/threat_intel/`, `src-tauri/src/`,
`sidecar-core/src/`, `frontend/src/`, and `tests/`.

**Note on root-level files named in the brief:** `IMPLEMENTATION_STATUS.md`
and `CURRENT_STATE.md` do not exist at the repo root — they live at
`docs/architecture/IMPLEMENTATION_STATUS.md` and
`docs/architecture/CURRENT_STATE.md`. The root `README.md` is a 0-byte
placeholder file. This is filed as a documentation finding in §13, not a
checkpoint mismatch — the files exist and were read, just not at the literal
path named.

---

## 1. Environment for this session

| Tool | Available | Version |
|---|---|---|
| Python | yes | 3.12.3 |
| `pytest` | **no** | not installed, no network to install |
| `fastapi` / `starlette` / `uvicorn` | **no** | not installed |
| `PySide6` | **no** | not installed |
| Node.js / npm | yes | v22.22.2 / 10.9.7 |
| `frontend/node_modules` | **no** | not present, cannot install (no network) |
| `cargo` / `rustc` | **no** | not installed at all in this sandbox |

This session's environment is **strictly narrower** than the one the
`docs/architecture/IMPLEMENTATION_STATUS.md` / `CURRENT_STATE.md` addenda
describe (those report `pytest`, `fastapi`, `cargo` 1.75.0, and `npm` all
present). None of `pytest tests/ -q` (600 passed), `cargo test`
(sidecar-core, 49 passed), `cargo check` (src-tauri, blocked on
edition2024), or `npm run build`/`typecheck` could be reproduced this
session. Every number attributed to those addenda below is reported as
**PRIOR-SESSION CLAIM**, not re-verified here — this is a real regression in
what this specific session's sandbox can confirm, and it is reported
honestly rather than papered over.

What **was** run this session, fresh:

```
$ python3 -m unittest discover -s tests -v
Ran 141 tests in 0.219s — 114 ok, 27 ERROR (import-time ModuleNotFoundError
for pytest/fastapi/uvicorn/PySide6 — every one confirmed to be a missing
module, not a failing assertion or an application defect)
```

This reproduces exactly the 114/114-passing, 0-failure figure
`PHASE4D_FREEZE.md` §11 reports for its own session, and confirms the
event-broker, DTO, handler-dispatch, and pure-domain test suites all still
pass unmodified against this exact checkpoint.

---

## 2. Phase 4E capability classification

| Capability | Classification | Evidence |
|---|---|---|
| Sidecar entrypoint (`app/api/entrypoint.py`) | **IMPLEMENTED + VERIFIED** (source-level); **IMPLEMENTED + UNVERIFIED** (runtime) | Real `uvicorn.Server` + `Config.bind_socket()` pre-bind, loopback-only host hardcoded, ephemeral port by default, single-line stdout port handshake, `SOCIQ_SIDECAR_PORT` override. Cannot execute this session (no `uvicorn`); `tests/test_sidecar_entrypoint.py` exists and is reported passing (8/8) in the prior-session addendum only. |
| FastAPI app / command dispatch route | **IMPLEMENTED + VERIFIED** (source), test suite present | `POST /commands/{name}` resolves `COMMAND_HANDLERS`, returns `fail(UNKNOWN_COMMAND, ...)` for unknown names, otherwise calls the handler with the parsed JSON body. `tests/test_api_layer.py` exists; prior-session claim 29/29 passing, not reproducible here (no `fastapi`). |
| `GET /events` SSE endpoint | **IMPLEMENTED + VERIFIED** (source, direct read) | Real `StreamingResponse` over `_sse_event_stream()`, correct SSE headers (`Cache-Control`, `Connection`, `X-Accel-Buffering`), each connection gets its own bounded `Subscription`, heartbeats are comment frames never routed through `Event`/broker. This directly **supersedes** the older `PHASE4_FULL_STATUS_AUDIT.md` finding of a `501` stub — that finding was accurate for the Part-8/Part-9 checkpoint it audited, and is now obsolete: Parts 1–4C of the SSE work closed that gap in this checkpoint. |
| `EventBroker` (`app/application/broker.py`) | **IMPLEMENTED + VERIFIED** (runtime) | `tests/test_event_broker.py` — 37/37 passed, run fresh this session. Thread-safe, per-subscriber `deque(maxlen=32)` drop-oldest queues, idempotent shutdown/unsubscribe, no cross-subscriber ordering guarantee (by design, tested explicitly). |
| `Event` model (`app/application/events.py`) | **IMPLEMENTED + VERIFIED** | Frozen dataclass, `event_id` generated once at `Event.create()` via `uuid4().hex` (deliberately not a broker sequence number — replay was explicitly decided against, not merely deferred, per the module's own docstring), `correlation_id`, `to_dict()` is the literal wire payload. |
| Command/DTO/handler architecture (`app/application/{dto,handlers,responses,errors}.py`) | **IMPLEMENTED + VERIFIED** | All 10 commands route through `dispatch()` → per-command DTO → handler class → domain/service → `ok()`/`fail()` envelope. `code_for_exception` centralizes error translation. Zero imports of `fastapi`, `starlette`, `PySide6`, or Tauri/Rust anywhere under `app/application/` (grep-confirmed this session). |
| `ThreatIntelProvider` abstraction (`app/threat_intel/`) | **IMPLEMENTED + VERIFIED** (per Phase 4C, unchanged) | `provider.py` protocol, `virustotal_provider.py` implementation, `service.py` accepts `list[ThreatIntelProvider]`. Out of Phase 4E's own scope; re-confirmed present, not re-audited line-by-line this session since Phase 4C is separately frozen (`PHASE4C_FREEZE.md`). |
| `sidecar-core` Rust crate (`sidecar-core/src/`) | **IMPLEMENTED + UNVERIFIED this session** | 636 lines across `supervisor.rs`, `state.rs`, `process.rs`, `lib.rs`, `error.rs`, `timeout.rs`, `startup.rs`; 5 test files under `sidecar-core/tests/` (`lifecycle`, `startup`, `shutdown`, `error`, `supervisor`). No `cargo`/`rustc` in this sandbox at all — cannot compile or run tests this session. Prior-session claim: 49/49 passing on cargo 1.75.0. Reported as PRIOR-SESSION CLAIM, not re-verified. |
| `src-tauri` crate — process supervision wiring (`lib.rs`, `sidecar.rs`) | **IMPLEMENTED + UNVERIFIED** | `lib.rs`'s `run()` now actually constructs and starts a `SidecarProcess` on a background thread at `setup()`, and shuts it down on `RunEvent::Exit` — this is new relative to `sidecar.rs`'s own module doc, which (per `lib.rs`'s comments) previously stated nothing drove a `SidecarProcess`. Cannot compile in this sandbox (no `cargo` at all; prior sessions report `edition2024`/cargo-1.75.0 MSRV mismatch as the blocker even where cargo exists). |
| Tauri commands | **IMPLEMENTED + UNVERIFIED**, minimal by design | Exactly one `#[tauri::command]`: `get_sidecar_origin`. One `generate_handler!` registration, matching 1:1 — no orphaned or unregistered commands. Uses `try_lock` (never blocks the invoking call), returns `Err` for any non-`Running` lifecycle state rather than blocking or silently returning a stale value. |
| Tauri capabilities (`src-tauri/capabilities/*.json`) | **IMPLEMENTED + VERIFIED** (source read) | `permissions: ["core:default", "get_sidecar_origin"]` only. No `shell:*`, `fs:*`, or `http:*` permission present anywhere in the capabilities file. The file's own description documents *why* no such permission was needed (the sidecar is supervised via `std::process`/`std::net` directly, not a Tauri plugin). |
| React frontend — API client (`shared/api/client.ts`) | **PARTIALLY IMPLEMENTED**, honestly so | `getSidecarOrigin()` is a real, wired `invoke("get_sidecar_origin")` call with `isTauri()` environment detection and a typed `SidecarNotConnectedError`. `runCommand()` is an explicit, documented stub (`Promise.reject(...)`) — no typed command transport exists yet. This is scoped intentionally, not an oversight (module docstring names the exact follow-on phase). |
| React frontend — SSE consumption (`shared/events/`) | **SCAFFOLD, PARTIALLY WIRED** | `eventSourceManager.ts`, `useEventStream.ts`, `useEventStreamStatus.ts`, `types.ts` exist; treats `getSidecarOrigin()` rejection as a normal retryable state per its own contract. Not independently re-verified against a running sidecar this session (no runtime available). |
| React frontend — routing/pages | **SCAFFOLD ONLY, explicitly** | `router.tsx`'s `AppRoutes()` renders a single placeholder `<main>` with the literal text "Feature screens are not implemented in this phase." No router library is installed. `docs/architecture/13-frontend-information-architecture.md` names 8 planned destinations (Dashboard, Analyze, Investigations, IOC Explorer, Threat Intel, Risk, Reports, Settings) — **none exist as components**. This is explicitly scoped as Phase 4G+ work by the frontend module's own comments, not a gap this checkpoint claims to have closed. |
| Frontend build output (`frontend/dist/`) | **IMPLEMENTED + UNVERIFIED this session** | `dist/index.html` + `assets/` exist, dated after the latest `src/` edit (consistent with a real prior build, not a stale leftover). `node_modules/` absent, no network — cannot rebuild or typecheck this session. Prior-session addendum claims `npm run typecheck` → 0 errors, `npm run build` → 44 modules, success. Reported as PRIOR-SESSION CLAIM. |
| Full communication chain (React → Tauri → sidecar → FastAPI → application → domain → EventBroker → SSE → EventSource → React) | **PARTIALLY IMPLEMENTED** | Every individual arrow has real code behind it (see §4 below for the arrow-by-arrow breakdown). The chain has never been exercised end-to-end in any session this repo documents — no session has had `cargo`+`node_modules`+`pytest`(fastapi) all available simultaneously to actually launch Tauri, spawn the sidecar, and drive a browser/webview against it. This is the single largest unverified surface in the whole project. |

---

## 3. Layer-by-layer detail

### A. Python application/domain layer
Dependency direction is clean and grep-verified this session: no file under
`app/application/` imports `fastapi`, `starlette`, `PySide6`, or anything
Tauri/Rust. `dispatch()` is a single linear `if/elif` chain over DTO
construction → handler `.handle()` → response envelope; all 10 commands
(`get_investigation`, `list_investigations`, `analyze_report`,
`delete_investigation`, `search_investigations`, `get_iocs`,
`save_settings`, `export_report`, `enrich_ioc`, `get_threat_intelligence`)
are present in `COMMAND_HANDLERS`. This matches `PHASE4D_FREEZE.md`'s own
claim and is independently re-confirmed by direct source read this session,
not merely re-cited from that document.

### B. FastAPI sidecar (`app/api/`)
Real production shape: dynamic port via OS assignment, loopback-only bind
hardcoded (not env-configurable, by design), single-line stdout handshake
before uvicorn logging starts, `POST /commands/{name}` dispatch route,
`GET /events` SSE with per-connection bounded subscriptions and heartbeat
framing, centralized error translation. This is not merely a `/health`
stub — a real command-execution and event-streaming surface exists. What is
**not** present: CORS middleware (not found in `app.py`; not required for a
same-origin Tauri webview, but also not documented as a deliberate
non-requirement anywhere read this session — flagged as an open question in
§14), and no structured logging configuration beyond what uvicorn provides
by default.

### C. `sidecar-core` (Rust)
636 lines, 5 dedicated test files covering lifecycle, startup, shutdown,
error, and supervisor behavior. `LifecycleState`, `Supervisor`, and process
management are cleanly separated by file. This crate compiles independently
of `src-tauri` (per the prior-session addenda, on a toolchain where
`src-tauri` itself does not, because `src-tauri`'s `dlopen2` transitive
dependency needs `edition2024`/cargo ≥1.85 while `sidecar-core` has no such
dependency). This session has no Rust toolchain at all, so **none** of this
is re-verified here — classified as IMPLEMENTED + UNVERIFIED, not BROKEN,
per the task brief's own instruction not to call code broken merely because
the sandbox lacks a compiler.

### D. `src-tauri`
Two source files beyond `main.rs`: `lib.rs` (174 lines) and `sidecar.rs`
(402 lines). One command, one registration, matched. `lib.rs`'s `run()`
starts the sidecar on a background OS thread at `setup()` (not blocking
window open) and shuts it down on `RunEvent::Exit`, using
`poisoned.into_inner()` recovery rather than propagating a panic. No
hardcoded port or origin found anywhere in `src-tauri/src/` (grep-confirmed
— the only `127.0.0.1:PORT`-shaped string in the whole tree is inside a doc
comment in `frontend/src/shared/api/client.ts`, illustrating the *format*
of a real dynamic origin, not a literal value). `tauri.conf.json`'s CSP is
`connect-src 'self' http://127.0.0.1:*` — scoped to loopback with a
wildcard port (necessary, since the port is dynamic by design), not `*` or
an unrestricted origin.

### E. React frontend
`shared/api/client.ts` and `shared/events/*` are real, if partial,
integration code — not disconnected placeholders. `app/router.tsx` and
therefore every page/component the design docs describe are explicitly,
self-admittedly absent. This is a deliberate scope boundary stated in the
code's own comments (Phase 4G+), not a discovered gap. `ThemeProvider.tsx`
and `ErrorBoundary.tsx` exist as application-shell infrastructure. No
dead code was found in the files inspected this session — every file read
either does real work or explicitly documents why it is a stub and when it
stops being one.

### F. Communication chain
| Arrow | State |
|---|---|
| React → Tauri `invoke` | Implemented (`getSidecarOrigin()` only; `runCommand()` stubbed) |
| Tauri → sidecar origin | Implemented (`get_sidecar_origin` command, `try_lock`, state-gated) |
| Tauri → sidecar process | Implemented (`SidecarProcess::start()`/`shutdown()` now actually driven from `lib.rs::run()`) |
| Sidecar → FastAPI | Implemented (`entrypoint.py` runs the real `app.api.app:app`) |
| FastAPI → application dispatch | Implemented, tested (114/114 relevant unittest cases pass this session) |
| Application → domain/service | Implemented, tested |
| Domain/service → EventBroker | Implemented per SSE Part 2 (handlers publish into the broker) — not independently re-traced line-by-line this session for every one of the 10 handlers; spot-checked on the `/events` route and broker tests only |
| EventBroker → SSE | Implemented, source-verified this session |
| SSE → frontend EventSource | Frontend-side code exists (`eventSourceManager.ts`) but never exercised against a live sidecar in any session this repo documents |
| Frontend EventSource → React state/UI | No consuming UI exists yet (`router.tsx` is a placeholder) — nothing to render the events into |

**The one honest end-to-end gap:** every arrow has real code, but the full
chain has never fired in one continuous run because no single session (this
one included) has had a working Rust toolchain, installed `node_modules`,
and installed Python server dependencies simultaneously. This is the
project's single most important unverified claim and is called out
explicitly in the architecture document's completion criteria.

---

## 4. Lifecycle audit

| Lifecycle stage | State |
|---|---|
| Tauri starts | Implemented — `tauri::Builder::default().manage(...).setup(...)` |
| Sidecar starts | Implemented — background thread, non-blocking `setup()` |
| Sidecar becomes ready | Implemented in `sidecar-core` (`LifecycleState::Running` gated on health-check success, not merely handshake) |
| Origin becomes available | Implemented — `get_sidecar_origin` gates on `Running`, `try_lock` never blocks |
| Frontend can call API | **Partial** — origin resolution wired; typed command calls (`runCommand`) not wired |
| Commands execute | Implemented at the FastAPI/application layer; unreachable from the frontend until `runCommand` exists |
| Events publish | Implemented at the broker/handler layer |
| SSE delivers | Implemented at the transport layer; unconsumed by any real UI |
| Shutdown | Implemented — `RunEvent::Exit` drives `SidecarProcess::shutdown()` |
| Sidecar terminates | Implemented in `sidecar-core`, UNVERIFIED this session (no Rust toolchain) |
| Resources cleaned | Same as above |
| Startup failure | Handled — `eprintln!` on `start()` error, does not crash the app |
| Sidecar crash mid-run | **Not traced this session** — no evidence found of a supervised-restart path; `get_sidecar_origin` would simply report a non-`Running` state, which the frontend treats as retryable, but nothing re-spawns the process automatically. Flagged as UNRESOLVED in the reconciliation matrix. |
| Frontend reconnect after SSE disconnect | Code exists (`useEventStreamStatus.ts`) but not exercised live this session |
| Shutdown during active SSE stream | Handled at the FastAPI layer (`try/finally` unsubscribe, per `PHASE4D_FREEZE.md` §3) — not re-traced against a live Tauri exit event this session |
| Repeated app launches / port collision | Not addressed by anything read this session — ephemeral OS-assigned ports make a *literal* port collision unlikely, but a stale orphaned process from a prior crashed launch is not something any file inspected this session explicitly guards against beyond the `RunEvent::Exit` shutdown hook (which only fires on a clean exit, not a crash of the Tauri process itself) |

---

## 5. Security audit

| Finding | Severity |
|---|---|
| Sidecar binds to `127.0.0.1` only, hardcoded, not env-configurable | Informational (positive control, verified) |
| Tauri capability file grants exactly `core:default` + one named command; no `shell:*`/`fs:*`/`http:*` | Informational (positive control, verified) |
| CSP `connect-src 'self' http://127.0.0.1:*` — loopback-scoped with a necessary dynamic-port wildcard | Low — a wildcard port is required given the dynamic-port design, but it does widen the theoretical connect surface to any loopback port during the window the app is running. No practical exploit path identified; flagged for awareness, not remediation. |
| `export_report`'s `output_path` accepts a plain string with no path-traversal restriction | Medium — carried forward from `PHASE4D_FREEZE.md` §7, which classifies this as consistent with the existing GUI's own file-dialog export behavior and the loopback-only, single-user trust boundary (`docs/security/ipc-security-model.md`). Not re-evaluated further this session; re-stated here for visibility in one place rather than re-litigated. |
| `config/settings.json`'s shipped `virustotal_api_key` is empty | Informational — no secret present in the archive |
| No CORS middleware found in `app/api/app.py` | Low/Informational — same-origin webview access does not require CORS; if the sidecar is ever reachable from a plain browser tab against a non-Tauri origin, this becomes relevant. Not currently a live risk given the loopback/webview-only deployment model, but not explicitly documented as a deliberate non-requirement either — worth one line in a future freeze doc. |
| No sidecar crash auto-restart path found | Low — availability concern, not a security one; noted in §4 |
| Error translation centralized (`code_for_exception`), no raw stack trace found reaching the response envelope | Informational (positive control, per `PHASE4D_FREEZE.md` §7, spot-checked this session) |

No CRITICAL or HIGH findings identified this session.

---

## 6. Test / toolchain matrix

| Suite | This session | Prior-session claim |
|---|---|---|
| `python3 -m unittest discover -s tests` | **RUN THIS SESSION**: 141 discovered, 114 passed, 27 environment-blocked (import errors only) | — |
| `tests/test_event_broker.py` (36 cases within the above) | **RUN THIS SESSION**: all passed | matches |
| `pytest tests/ --ignore=tests/gui` | BLOCKED (no `pytest`) | 600 passed |
| `pytest tests/gui` (offscreen) | BLOCKED (no `pytest`, no `PySide6`) | 154 passed |
| `pytest tests/test_api_layer.py` | BLOCKED (no `fastapi`) | 29 passed |
| `pytest tests/test_sidecar_entrypoint.py` | BLOCKED (no `uvicorn`) | 8 passed |
| `cd sidecar-core && cargo test` | BLOCKED (no `cargo` at all) | 49 passed |
| `cd src-tauri && cargo check` | BLOCKED (no `cargo` at all) | BLOCKED even where cargo exists (`edition2024` needs cargo ≥1.85; environment reported as 1.75.0) |
| `cd frontend && npm run typecheck` | BLOCKED (`node_modules` absent, no network to install) | 0 errors |
| `cd frontend && npm run build` | BLOCKED (same) | 44 modules, success |

No test was fabricated or assumed passing without either a fresh run or an
explicit prior-session citation this session.

---

## 7. Phase 4D → Phase 4E reconciliation matrix

| Phase 4D decision | Current implementation | Still valid? | Phase 4E treatment |
|---|---|---|---|
| `app/application/` has zero transport/UI imports | Confirmed intact (grep, this session) | Yes | **RETAIN** |
| Single `dispatch()` + `COMMAND_HANDLERS` table | Unchanged, all 10 commands present | Yes | **RETAIN** |
| DTOs per command, explicit response-mapping functions | Unchanged | Yes | **RETAIN** |
| `Event` frozen dataclass, handler-generated `event_id` | Unchanged | Yes | **RETAIN** |
| `EventBroker`, bounded per-subscriber queues, drop-oldest | Unchanged, 37/37 tests pass fresh | Yes | **RETAIN** |
| Synchronous command execution (no async execution bridge) | Unchanged; `dispatch()` remains synchronous | Yes — no evidence Phase 4E work has needed to revisit this | **RETAIN**, revisit only if a genuinely long-running command is added later |
| SSE as `501` (Phase 4D Part 8/9 decision) | **Superseded** — `GET /events` is now a real `StreamingResponse` (SSE Parts 1–4C) | No, by design (this was always the documented next step) | **REPLACE** (already done; nothing further required architecturally) |
| FastAPI boundary owns all SSE/HTTP framing, `app/application/` stays transport-neutral | Confirmed — heartbeat/framing/disconnect logic lives in `app/api/app.py`, not `app/application/` | Yes | **RETAIN** |
| No Tauri command existed | One real command now exists (`get_sidecar_origin`), minimally scoped | N/A — this is Phase 4E's own addition, not a 4D decision being revisited | **EXTEND** — this is the correct, narrow next increment |
| Frontend `runCommand()` as a documented stub | Unchanged this checkpoint | Yes, intentionally | **EXTEND** (next real Phase 4E slice — see architecture doc) |
| No sidecar auto-restart on crash | Unchanged, never decided either way | **UNRESOLVED** | Needs an explicit decision in Phase 4E (see architecture doc §Runtime) |
| CORS posture for the sidecar | Never explicitly decided | **UNRESOLVED** | Needs one line of documented decision, not necessarily new code |

No Phase 4D decision was found to need outright replacement by newer
technology. The SSE `501`→real-implementation change is the only
"replacement," and it was always the planned direction of Phase 4D's own
SSE architecture-decision document — not a Phase 4E-driven reversal.

---

## 8. Documentation audit

| Document | Claim | Source truth | Treatment |
|---|---|---|---|
| Task brief's own checkpoint-file paths (`IMPLEMENTATION_STATUS.md`, `CURRENT_STATE.md` at repo root) | Implies root location | Actual location: `docs/architecture/` | Informational — files exist and were read; no content contradiction, just a path assumption in the brief that doesn't match this repo's layout |
| Root `README.md` | Would normally describe the project | 0 bytes | Stale/incomplete — recommend eventually populating, not urgent |
| `PHASE4_FULL_STATUS_AUDIT.md`'s SSE finding ("`GET /events` SSE is a deliberate, honest `501`") | Accurate for the checkpoint it audited (post-Part-9, pre-SSE-implementation) | **Obsolete for the current checkpoint** — SSE Parts 1–4C closed this gap | Not a contradiction — a correctly time-scoped historical finding. No edit needed; future readers should note this document predates the SSE implementation. |
| `docs/architecture/IMPLEMENTATION_STATUS.md` / `CURRENT_STATE.md` addenda | "IMPLEMENTATION COMPLETE. NOT YET FROZEN." | `PHASE4D_FREEZE.md` (dated the same day, later in the doc list) records the actual freeze decision (CLASS B) | These addenda are now one step behind the freeze record — accurate as of when written, superseded by `PHASE4D_FREEZE.md`. Recommend a follow-up addendum noting the freeze occurred, but this is not this audit's job to make (§13 of the brief: report only, do not edit). |
| `docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md` §6 / `docs/architecture/03-frontend-architecture.md` | React frontend is "Phase 4F+" work, should not exist before the Tauri/IPC contract is in place | `frontend/` already exists, built alongside the Tauri scaffold | Explicitly reconciled already by `PHASE4_CHECKPOINT_NAMING.md` — not a fresh contradiction, cited here for completeness only |

No other stale/contradictory claims were found in the files read this
session. This is not represented as an exhaustive line-by-line audit of
every one of the ~30 `docs/phase4/*.md` files — the ones most relevant to
Phase 4E status and reconciliation were read in full; older Phase 2/3
documents were not re-opened, as they are out of this audit's scope and
nothing this session touched contradicts them.

---

## 9. Adversarial findings

| Risk | Assessment |
|---|---|
| Circular dependencies | None found — `app/application/` → domain/service is one-directional, confirmed by import grep |
| Sidecar crash / no auto-restart | Real gap — see §4/§7. Not a defect in what exists, but an undecided behavior. |
| Orphaned sidecar process on Tauri crash (not clean exit) | Plausible gap — `RunEvent::Exit` only fires on a clean exit path; a hard crash of the Tauri host process is not demonstrated to be guarded against by anything read this session |
| Port collision | Unlikely given ephemeral OS-assigned ports, but not explicitly tested against a rapid-relaunch scenario |
| SSE subscriber leak | Mitigated — bounded per-subscriber queues, `try/finally` unsubscribe, tested (`ShutdownTests`, `UnsubscribeTests` in `test_event_broker.py`, all passing fresh this session) |
| Blocking the Tauri/UI thread on sidecar startup | Explicitly avoided — `get_sidecar_origin` uses `try_lock`, startup runs on a background thread |
| Blocking the FastAPI event loop | Not independently verified this session (would require a running server); `dispatch()` is synchronous by design, which is an accepted Phase 4D decision, not a defect |
| Malformed SSE / malformed API responses | Not stress-tested this session (no runtime available); error translation is centralized, reducing but not eliminating this risk class |
| Stale frontend state after reconnect | Cannot be exercised without a live sidecar + browser/webview; code exists but is unverified end-to-end (see §3F) |
| Capability escalation | None found — capabilities file is minimal and its own description explains why each permission is absent |
| Secret leakage | None found — no API key present in shipped config, error envelopes don't leak raw exceptions per `PHASE4D_FREEZE.md` §7 |

---

## 10. Final answers to the brief's §15 questions

1. **Is Phase 4E architecture fundamentally sound?** Yes. Every layer's
   internal design is coherent and the dependency direction is clean
   end-to-end on paper; the gap is verification (no session has run the
   full chain live), not design.
2. **What already exists?** Sidecar entrypoint, FastAPI command dispatch +
   SSE, `EventBroker`/`Event`, `sidecar-core` process supervision, one real
   Tauri command wired to real state, a minimal-but-correct capability
   file, and a frontend API/event scaffold that is honestly partial.
3. **What is merely scaffolded?** Frontend routing/pages (explicitly, by
   the code's own comments) and `runCommand()` (explicitly stubbed).
4. **What is missing?** A typed frontend command client; a decided,
   documented sidecar-crash/restart policy; an explicit CORS-posture
   decision (even if the decision is "not needed," it should be written
   down); any live, full-chain verification.
5. **What is broken?** Nothing found. No BROKEN classification was
   assigned to any capability in §2.
6. **What is unverified?** `sidecar-core` and `src-tauri` compilation/tests
   (no Rust toolchain this session), the frontend build/typecheck (no
   `node_modules`, no network), and the full end-to-end communication
   chain (never exercised live in any session this repo documents).
7. **Which Phase 4D decisions remain foundational?** All of them — see §7,
   every row is RETAIN except the SSE stub, which was always meant to be
   replaced and was replaced as planned.
8. **Which need extension/replacement?** Only extension: the Tauri command
   surface (one command today, more will follow) and the frontend command
   client. No replacement of any 4D decision is warranted.
9. **Unified desktop architecture?** See `PHASE4E_ARCHITECTURE.md`.
10. **How many implementation slices remain?** See
    `PHASE4E_ARCHITECTURE.md`'s work breakdown — 6 atomic slices identified.
11. **What should be implemented first?** A typed `runCommand()` transport
    in the frontend (the smallest slice that turns the already-real backend
    into something the frontend can actually use), followed by a decided
    sidecar-restart policy.
12. **What must NOT be changed?** The application-layer/domain dependency
    direction, the synchronous `dispatch()` model, the bounded-queue
    `EventBroker` design, and the minimal Tauri capability set.
13. **What blocks Phase 4E completion?** Environment/toolchain
    verification (Rust ≥1.85, Node deps, Python server deps all installed
    simultaneously) more than any missing source — most of the remaining
    work is either small (typed command client) or a documentation
    decision (crash policy, CORS), not large new subsystems.
14. **What defines the Phase 4E freeze?** See completion criteria in
    `PHASE4E_ARCHITECTURE.md`.
