# SOC-IQ — Unified Phase 4E Desktop Architecture

**Date:** 2026-08-24
**Status:** Proposed canonical architecture, derived from actual source
inspection and `PHASE4E_FULL_STATUS_AUDIT.md`, not written independently of
it. This document defines what Phase 4E should build on top of what already
exists — it is not a rewrite of the frozen Phase 4D decisions.

This is architecture, not UI. Colors, spacing, animation, and page layout
are out of scope (see `docs/architecture/11-design-system-architecture.md`
and `13-frontend-information-architecture.md` for that work).

---

## 1. Process architecture

Four processes/runtimes, one owner each:

| Component | Owner | Lifetime |
|---|---|---|
| Tauri host process | OS / user launches it | Full application lifetime |
| Python sidecar (uvicorn + FastAPI) | Spawned and supervised by `src-tauri` via `sidecar-core::Supervisor` | Started on Tauri `setup()`, on a background thread; stopped on `RunEvent::Exit` |
| React frontend | Runs inside the Tauri webview (no separate process) | Same lifetime as the Tauri window |
| `EventBroker` | In-process, owned by the Python application layer, inside the sidecar | Same lifetime as the sidecar process |

No component is duplicated across boundaries: the frontend never talks to
Python directly, Rust never contains domain logic, and Python never knows
Tauri exists. This is unchanged from Phase 4D/4E-to-date and should stay
unchanged.

---

## 2. Runtime architecture

**Startup**
1. Tauri `Builder::setup()` runs, manages `SidecarState`, spawns a
   background thread.
2. Background thread calls `SidecarProcess::start()`, which resolves the
   working directory, launches `python -m app.api.entrypoint`, and reads
   the port handshake from stdout.
3. `sidecar-core`'s `Supervisor` health-checks the process; only once a
   health check succeeds does `LifecycleState` become `Running`.
4. `get_sidecar_origin` becomes callable-and-successful only once state is
   `Running` — before that it returns a fast `Err`, never blocks.
5. The frontend treats a rejected `getSidecarOrigin()` as a normal,
   retryable state (already implemented in `eventSourceManager.ts`'s
   contract) and should poll or retry on a short backoff until it
   succeeds — this retry loop itself is one of the remaining
   implementation slices (§8, Slice 3).

**Readiness** is therefore a three-state model end to end: *not started*,
*starting* (process exists, health check not yet passed), *running*
(health check passed, origin resolvable). No component should ever
observe a fourth ambiguous state — this is already how `sidecar-core`'s
`LifecycleState` and the Tauri command are built, and the frontend should
be held to the same three-state contract when `runCommand()` is built.

**Requests**: frontend → `invoke()` for origin resolution only; all actual
command execution goes over HTTP to the resolved origin, never through
Tauri IPC. This keeps the command surface transport-agnostic (the same
FastAPI routes could, in principle, be hit from a browser during
development) and keeps Rust's role strictly to "supervise the process,
relay the port" — never a business-logic proxy.

**Events**: SSE only, one `GET /events` connection per frontend session,
each subscription independently bounded (already implemented, `deque(maxlen=32)`
drop-oldest). No polling fallback should be added — if a future need for
one arises, that is a new architectural decision requiring its own
document, not a silent addition.

**Shutdown**: `RunEvent::Exit` → `SidecarProcess::shutdown()`. This is
implemented for the *clean-exit* path. The *crash* path (Tauri host
process killed externally, or panics before `RunEvent::Exit` fires) is
currently unaddressed — see §3 and Slice 4.

**Failure/recovery**: sidecar start failure is logged (`eprintln!`) and
does not crash the host application; the frontend continues to see
"not connected" and can retry. What Phase 4E must still decide explicitly
(not silently default to "no retry"): whether a failed sidecar start is
retried automatically by Rust, or whether retry is purely a frontend-driven
re-poll of `get_sidecar_origin` (which itself never re-attempts
`start()` — it only reads current state). Recommendation: keep `start()`
single-attempt in Rust (simpler, matches the current code), and make
frontend retry-on-poll the one and only recovery path, documented
explicitly rather than left implicit.

---

## 3. Dependency architecture

```
frontend (React/TS)
    ↓ invoke() [origin only]         ↓ HTTP [commands + SSE]
src-tauri (Rust)                 sidecar origin (dynamic)
    ↓ owns/supervises                    ↓
sidecar-core (Rust)               app/api (FastAPI)
                                          ↓
                                   app/application (dispatch, DTOs, broker)
                                          ↓
                                   domain/services (Investigation, ThreatIntel, ...)
```

Rules (all already enforced in source, grep-confirmed this audit — this
section documents the existing invariant, it does not introduce a new one):

- `app/application/` never imports `fastapi`, `starlette`, `PySide6`, or
  anything from `src-tauri`/`sidecar-core`/`frontend`.
- `src-tauri` never contains domain/business logic — it supervises a
  process and relays a port, nothing else.
- `sidecar-core` knows nothing about Tauri, FastAPI, or SOC-IQ's domain —
  it is a generic process-lifecycle crate.
- `frontend` never calls Python directly — only through the resolved HTTP
  origin, itself only obtainable through Tauri.

Any future PR that adds an import crossing one of these arrows backward is
a regression, not a refactor, and should be rejected in review.

---

## 4. API architecture

- **REST**: `POST /commands/{name}` — single dispatch surface, JSON body,
  DTO-validated, uniform `ok()`/`fail()` envelope. New commands are added
  by adding a DTO + handler + one `dispatch()` branch + one
  `COMMAND_HANDLERS` entry — never a new bespoke route.
- **SSE**: `GET /events` — one real-time stream, framed per the SSE spec,
  heartbeats as comment frames, never mixed with real `Event` traffic.
- **Errors**: centralized translation (`code_for_exception`), no raw
  exception detail beyond `str(exception)` reaches the client.
- **DTOs**: one request DTO and one response-mapping function per command;
  domain objects never cross the boundary directly.

This is the existing Phase 4D contract. Phase 4E's only addition here
should be a typed frontend client (`runCommand<T>()`) that calls this
existing surface — not a new backend API shape.

---

## 5. Event architecture

- `Event`: frozen dataclass — `event`, `version`, `correlation_id`,
  `investigation_id`, `timestamp`, `payload`, `event_id` (uuid4, generated
  once at construction).
- `EventBroker`: thread-safe, per-subscriber bounded queues, drop-oldest,
  no global replay/history (deliberate — not a gap).
- Subscribers: one per SSE connection, isolated from each other.
- SSE: FastAPI-owned framing (`id:`/`event:`/`data:`), broker-agnostic on
  the wire.
- Frontend consumers: `eventSourceManager.ts` owns the `EventSource`
  lifecycle; `useEventStream`/`useEventStreamStatus` are the React-facing
  hooks. No consuming UI exists yet — this is expected at this stage (see
  Slice 5) and is not a defect in the event architecture itself.

No change to this model is warranted by anything found in this audit.

---

## 6. Tauri architecture

- **Commands**: one today (`get_sidecar_origin`), read-only, `try_lock`,
  never blocks the invoking call. Future commands (when `runCommand()`
  needs richer Tauri-side behavior, if ever) must follow the same pattern:
  fast, non-blocking, no business logic, minimal capability grant per
  command.
- **State**: a single `Mutex<SidecarProcess>` managed by Tauri. A `Mutex`
  is correct today (no read-heavy contention pattern); revisit only if a
  second, independent piece of Tauri-managed state is introduced.
- **Sidecar manager**: `sidecar.rs` + `sidecar-core`, unchanged.
- **Lifecycle**: background-thread start, `RunEvent::Exit`-driven shutdown.
- **Capabilities**: minimal by construction (`core:default` +
  `get_sidecar_origin` only). New commands must each justify their own
  named permission in the capabilities file's own description, exactly as
  `get_sidecar_origin` already does — this pattern should be treated as a
  standing requirement, not a one-off.

---

## 7. Frontend architecture

- **API client**: `shared/api/client.ts` — `getSidecarOrigin()` (done),
  `runCommand<T>()` (stub, next slice).
- **EventSource**: `shared/events/*` — connection lifecycle, retry/backoff
  contract already defined; needs to be exercised against a real running
  sidecar once environment allows.
- **State management**: not yet chosen beyond React's own state/hooks —
  no state library (Redux/Zustand/etc.) has been added, and none should be
  added speculatively ahead of the first real page needing one.
- **Pages/components**: intentionally absent. `AppRoutes()` is a named
  mount point, not a router. The 8 destinations named in
  `13-frontend-information-architecture.md` are Phase 4G+ scope.
- **Connection lifecycle**: not-connected → connecting → connected →
  (disconnected → retry) — this should be the explicit state machine
  `useEventStreamStatus.ts` exposes; verify it matches this shape when the
  live-verification slice runs (Slice 6).

---

## 8. Security architecture

Trust boundary: one local, already-trusted user and process, loopback-only,
no multi-tenant or internet-facing exposure. This is the boundary every
existing security decision in the codebase is built against
(`docs/security/ipc-security-model.md`), and Phase 4E should not silently
widen it (e.g., binding to `0.0.0.0`, adding a filesystem/shell capability,
or accepting a non-loopback CORS origin) without a new, explicit security
decision document.

Capabilities: additive-only, one named permission per command, each
justified in the capabilities file itself.

Two decisions Phase 4E should make explicit (not necessarily by writing new
code, but by writing down the decision):
1. **CORS posture** — confirm no CORS middleware is needed given the
   webview-only deployment model, or add a narrowly-scoped one if a
   non-Tauri dev-browser workflow is meant to be supported.
2. **Sidecar crash/restart policy** — decide whether Rust retries
   `start()` automatically or whether recovery is frontend-poll-only (see
   §2), and document it once, in one place.

---

## 9. Packaging architecture (Windows, eventual)

Not implemented in this checkpoint and correctly out of scope for it
(`resolve_working_directory()`'s own comment already flags that a bundled
installer needs a different working-directory resolution strategy than the
current source-checkout-relative one). When packaging work begins, it needs
its own document — this section is a placeholder naming the one known gap
(`CARGO_MANIFEST_DIR`-relative path resolution won't survive bundling) so
it isn't rediscovered from scratch later.

---

## 10. Remaining implementation — atomic slices

Six slices identified. Ordered by dependency, not by size.

### 4E-P1 — Typed frontend command client
- **Objective**: implement `runCommand<T>()` in `shared/api/client.ts`
  against the real `POST /commands/{name}` route.
- **Current state**: explicit stub (`Promise.reject`).
- **Files**: `frontend/src/shared/api/client.ts`,
  `frontend/src/shared/api/types.ts`.
- **Dependencies**: none — `getSidecarOrigin()` already works.
- **Work**: fetch/axios-style call to `${origin}/commands/${name}`, parse
  the existing `ApiResponse<T>` envelope, surface `fail()` errors as typed
  rejections mirroring `SidecarNotConnectedError`'s pattern.
- **Tests required**: unit tests mocking `fetch`/origin resolution; no new
  backend test needed (the route is already tested).
- **Verification required**: a live sidecar to hit against, once
  environment allows (see Slice 6).
- **Risk**: low — additive, no existing contract changes.
- **Parallelizable**: yes, independent of all other slices below.
- **Completion criteria**: every one of the 10 commands callable from the
  frontend with correct typed success/error handling; no `any` at the
  call-site boundary.

### 4E-P2 — Sidecar crash/restart decision + implementation
- **Objective**: close the "sidecar crashes mid-run" gap named in
  `PHASE4E_FULL_STATUS_AUDIT.md` §4/§9.
- **Current state**: undecided; `RunEvent::Exit` only covers clean exit.
- **Files**: `src-tauri/src/lib.rs`, `src-tauri/src/sidecar.rs`,
  `sidecar-core/src/supervisor.rs`.
- **Dependencies**: none.
- **Work**: decide (per §8) whether Rust auto-restarts on unexpected
  process exit; if yes, add a bounded retry (with backoff and a max-attempt
  cap to avoid a restart storm) inside `Supervisor`; if no, document the
  frontend-poll-only recovery model explicitly in `sidecar.rs`'s own
  module doc.
- **Tests required**: `sidecar-core` test for the chosen behavior
  (extend `supervisor_tests.rs`).
- **Verification required**: Rust toolchain ≥1.85 available.
- **Risk**: medium — process-supervision logic is easy to get subtly
  wrong (restart storms, double-shutdown races).
- **Parallelizable**: yes.
- **Completion criteria**: documented, tested behavior for at least one
  crash scenario (process killed externally mid-run).

### 4E-P3 — Frontend origin-retry loop
- **Objective**: make `getSidecarOrigin()` rejection actually drive a
  retry/backoff in the UI layer, not just be treated as "normal" in
  isolation.
- **Current state**: `eventSourceManager.ts` treats rejection as
  retryable in contract/comment form; whether an actual retry timer exists
  was not confirmed line-by-line this session.
- **Files**: `frontend/src/shared/events/eventSourceManager.ts`,
  `useEventStreamStatus.ts`.
- **Dependencies**: none (can run before or alongside 4E-P1).
- **Work**: confirm/implement a bounded backoff retry against
  `getSidecarOrigin()` until `Running` or a max-attempt UI-visible failure
  state.
- **Tests required**: frontend unit test with a mocked rejecting/then-
  resolving `invoke`.
- **Verification required**: none beyond unit tests (no live sidecar
  needed to test the retry logic itself).
- **Risk**: low.
- **Parallelizable**: yes.
- **Completion criteria**: a killed/slow-starting sidecar does not leave
  the UI stuck in a silent, unrecoverable state.

### 4E-P4 — CORS posture decision
- **Objective**: close the open question named in §8/§9 of the audit.
- **Current state**: no CORS middleware present; not documented as
  deliberate.
- **Files**: `app/api/app.py` (only if the decision is "add narrow CORS
  for dev-browser support"), plus one paragraph in
  `docs/security/ipc-security-model.md`.
- **Dependencies**: none.
- **Work**: decide, document; implement only if the decision requires code.
- **Tests required**: none if no code changes; one integration test if
  CORS middleware is added.
- **Verification required**: none.
- **Risk**: low.
- **Parallelizable**: yes.
- **Completion criteria**: one sentence in the security docs settling the
  question either way.

### 4E-P5 — Environment/toolchain unification for verification
- **Objective**: get to a single environment (CI or local) where
  `cargo` ≥1.85, `node_modules`, and Python server deps
  (`fastapi`/`uvicorn`/`PySide6`) are all installed simultaneously, so the
  full chain can be exercised at least once.
- **Current state**: no session in this project's history has had all
  three simultaneously.
- **Files**: none (infrastructure/CI work, not source).
- **Dependencies**: none.
- **Work**: CI pipeline or documented local setup steps.
- **Tests required**: N/A.
- **Verification required**: this slice *is* the verification enabler.
- **Risk**: low technically, but this is the single biggest blocker to
  everything else being provably correct rather than "implemented and
  individually plausible."
- **Parallelizable**: yes, independent of all source-touching slices.
- **Completion criteria**: one documented environment where
  `cargo test` (both crates), `pytest tests/` (full suite), and
  `npm run build && npm run typecheck` all run in the same session.

### 4E-P6 — Live full-chain verification
- **Objective**: actually launch the Tauri app, spawn the sidecar, and
  confirm React → Tauri → sidecar → FastAPI → application → EventBroker →
  SSE → EventSource → React fires correctly end to end, at least once.
- **Current state**: never done in any documented session.
- **Files**: none (verification, not implementation) — may surface small
  bugs in any of the layers above, to be filed as their own follow-up
  slices if found.
- **Dependencies**: 4E-P1 (need a real command call to verify),
  4E-P5 (need the environment).
- **Work**: manual or scripted end-to-end run; capture the result.
- **Tests required**: ideally one automated E2E test, but a documented
  manual run is an acceptable first bar.
- **Verification required**: this is the verification.
- **Risk**: unknown until run — this is exactly why it must happen before
  Phase 4E is called complete.
- **Parallelizable**: no — depends on 4E-P1 and 4E-P5.
- **Completion criteria**: one documented successful end-to-end command
  execution and one documented successful end-to-end SSE event delivery,
  from a real Tauri window.

---

## 11. Phase 4E completion criteria

Phase 4E is complete when **all** of the following hold, each with source
or run evidence (not "looks complete"):

1. **Source architecture** — dependency directions in §3 hold with no
   violation (grep-verifiable, as this audit did).
2. **Sidecar lifecycle** — start, ready, and clean-shutdown paths tested
   (`sidecar-core`); crash/restart behavior decided and tested (4E-P2).
3. **Tauri integration** — commands match registrations 1:1; capabilities
   minimal and each individually justified.
4. **Frontend integration** — `runCommand()` implemented and tested
   (4E-P1); origin-retry implemented and tested (4E-P3).
5. **Security** — CORS posture documented (4E-P4); no capability grants
   beyond what's individually justified; loopback-only bind unchanged.
6. **API** — all 10 commands reachable from the frontend, not just from
   `TestClient`/`curl`.
7. **SSE** — delivered and consumed by at least a hook-level test, ideally
   by real (even minimal) UI.
8. **Tests** — `cargo test` (both crates), `pytest tests/` (full suite),
   `npm run build`/`typecheck` all passing in one environment (4E-P5).
9. **Build** — `npm run build` succeeds and `frontend/dist/` is current.
10. **Packaging** — not required for Phase 4E completion (explicitly
    Phase-4-later scope, §9), but the one known blocker
    (`CARGO_MANIFEST_DIR`-relative path resolution) must be logged as a
    tracked follow-up, not forgotten.
11. **E2E** — at least one documented live full-chain run (4E-P6).
12. **Documentation** — `IMPLEMENTATION_STATUS.md`/`CURRENT_STATE.md`
    addenda updated to reflect the freeze that already happened
    (`PHASE4D_FREEZE.md`) and the slices above as they close.
13. **Adversarial audit** — a follow-up pass re-running §9 of the status
    audit against the *implemented* crash/restart and CORS decisions
    (today's adversarial audit found no CRITICAL/HIGH issues, but it also
    couldn't test what didn't exist yet).

Phase 4E freeze = all 13 criteria met, with a freeze document in the same
style as `PHASE4D_FREEZE.md` — direct source/test evidence, explicit
prior-session-claim labeling for anything not reproduced fresh in the
freeze session itself.

---

## 12. What must not change

- The application-layer/domain dependency direction (§3).
- The synchronous `dispatch()` model — no async execution bridge should be
  introduced without its own architecture decision document, exactly as
  Phase 4D's own SSE decision was handled.
- The bounded, drop-oldest, no-replay `EventBroker` design.
- The minimal, per-command-justified Tauri capability model.
- The loopback-only, single-user trust boundary.

These are the Phase 4D decisions this audit found still fully valid, and
none of the Phase 4E work identified above requires touching any of them.
