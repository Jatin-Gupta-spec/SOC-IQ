# Phase 4E-P2, Part 1 — Sidecar Crash/Restart Architecture & Decision

**Status:** Architecture/decision checkpoint only. No supervisor was implemented by this
document — see §15 "Source changes: 0". Builds on `docs/phase4/PHASE4E_ARCHITECTURE.md`
§8/§10 (4E-P2 scoping), `docs/phase4/PHASE4_PRE_2A_CONTRACT.md` (lifecycle vocabulary),
`docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md` (why no auto-restart exists yet),
`docs/phase4/PHASE4E_FULL_STATUS_AUDIT.md` §4/§9 (the gap this document closes).

**Phase 4E-P1 is COMPLETE / FROZEN and was not reopened or modified to produce this
document.** See §17.

---

## 1. Scope

What Phase 4E-P2 solves: the sidecar process can crash after it becomes `RUNNING`, and
today nothing detects or recovers from that (§2, §3). This document is Part 1 of P2: it
inspects the real, already-substantial existing sidecar-lifecycle implementation, and
establishes the single authoritative design for crash detection, restart policy, backoff,
crash-loop protection, intentional-shutdown/restart-race safety, and the event/error/GUI
contract Parts 2–3 will implement against and Part 4 will audit against.

It does **not** implement the restart loop, add a timer, or modify
`sidecar-core`'s transition table or `src-tauri`'s command surface. See §19 (Scope Guard)
for the explicit boundary and §15 for the (zero) source changes made.

---

## 2. Existing Architecture

This is a materially more mature starting point than a from-scratch design: an earlier
increment ("Phase 2A"/"Part 2B", predating and separate from 4E-P1) already built a real,
tested lifecycle core and a real process adapter. Nothing below was inferred from
filenames — every claim was checked against the actual source in this archive.

### 2.1 Component inventory

| Layer | File | Responsibility |
|---|---|---|
| Framework-independent state machine | `sidecar-core/src/state.rs` | `Lifecycle`/`LifecycleState` — 8 states, an explicit transition table, rejects invalid transitions |
| Framework-independent orchestration | `sidecar-core/src/supervisor.rs` | `Supervisor` — event-driven methods (`request_start`, `spawn_failed`, `health_check_succeeded`, `request_shutdown`, `process_exited`, `unexpected_exit`, `reset`, …), no I/O, no timing, no process spawning |
| Typed errors | `sidecar-core/src/error.rs` | `SidecarError` with a stable `.code()` per variant (e.g. `SIDECAR_UNEXPECTED_EXIT`) |
| Timeout config | `sidecar-core/src/timeout.rs` | `TimeoutConfig { startup, shutdown }`, both bounded, no defaults mandate restart behavior |
| Handshake parsing | `sidecar-core/src/startup.rs` | Parses the real Python sidecar's stdout handshake line |
| Real process adapter | `src-tauri/src/sidecar.rs` | `SidecarProcess` — spawns `python -m app.api.entrypoint`, reads the handshake, polls `/health`, owns the `Child` handle and captured port |
| Application wiring | `src-tauri/src/lib.rs` | Constructs one `SidecarState(Mutex<SidecarProcess>)`, starts it on a background thread at `setup`, exposes `get_sidecar_origin`, shuts it down on `RunEvent::Exit` |
| Python sidecar process itself | `app/api/entrypoint.py`, `app/api/app.py` | FastAPI app; `GET /health`; `GET /events` (SSE); `POST /commands/{name}` |
| Frontend origin/command bridge | `frontend/src/shared/api/client.ts` | `getSidecarOrigin()` (wraps the Tauri `invoke`), `runCommand<T>()`; defines `SidecarNotConnectedError` |
| Frontend event stream | `frontend/src/shared/events/eventSourceManager.ts` | Ref-counted `EventSource` to `GET /events`; tracks `idle/connecting/open/unavailable/closed` |

### 2.2 Current sidecar owner

`src-tauri/src/lib.rs` is already the single lifecycle owner, and already correctly
prevents the anti-pattern this document's brief warns against (GUI/API-client/worker each
independently restarting the sidecar): there is exactly one `SidecarState`, constructed
once, and exactly two places that ever call into it — the `setup` closure (`start()`) and
the `RunEvent::Exit` handler (`shutdown()`). `sidecar.rs`'s own module doc states this
explicitly: `sidecar_core::Supervisor` "remains the single source of truth for lifecycle
*state*", and `SidecarProcess` "never reads or mutates `Supervisor`'s internal state
directly; it only calls its public event methods". This ownership model is correct and is
**kept unchanged** by this decision (§6) — P2 extends it, it does not replace it.

The GUI (`app/gui/`, PySide6) and the frontend (`frontend/src/`) have **no** sidecar
lifecycle authority today and none is proposed: they can only observe (`get_sidecar_origin`,
future events) or request (a future explicit "restart" command, not designed here — see
§19), never decide.

### 2.3 Current lifecycle states

Already defined, already exercised by tests (per `docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md`,
49 `sidecar-core` tests were passing at that checkpoint's own session — this session's
sandbox has no Rust toolchain to re-run them; see §20):

```
NOT_STARTED → STARTING → RUNNING → STOPPING → STOPPED
                   ↓          ↓         ↓
                 FAILED    CRASHED   FAILED
                   ↓
                TIMEOUT
```

`FAILED`, `TIMEOUT`, `CRASHED`, `STOPPED` are terminal; recovery requires an explicit
`transition(NotStarted)` (i.e. `Supervisor::reset()`) before a fresh
`NotStarted → Starting` cycle. This is already exactly the "requiring a fresh
`NOT_STARTED → STARTING` transition to recover" vocabulary this task brief's §7 example
independently re-derives — no new state names are needed (§7 decision, below).

### 2.4 Current failure handling (exactly what happens today)

1. **Startup failure** (spawn fails, handshake malformed/absent, or process exits before
   ever becoming healthy, or the startup timeout elapses): `SidecarProcess::start()` kills
   and reaps the child, transitions the supervisor to `FAILED` or `TIMEOUT`, and returns
   `Err`. In `lib.rs`, the background-thread caller only does
   `eprintln!("SOC-IQ sidecar failed to start: {err}")` — **nothing retries, nothing
   restarts, nothing notifies the frontend beyond the fact that `get_sidecar_origin` will
   keep returning `Err` because `state() != Running`.**
2. **Runtime crash** (process exits on its own after reaching `RUNNING`): `unexpected_exit()`
   exists and correctly transitions `RUNNING → CRASHED`, but **it is never called in the
   running application.** `poll_for_crash()` — the method that would detect this by
   `try_wait()`-ing the child — exists on `SidecarProcess` but has no caller anywhere in
   `lib.rs`. This is the concrete gap `PHASE4E_FULL_STATUS_AUDIT.md` §4 already flagged as
   unresolved: **today, a mid-run crash is not detected by the running application at all.**
   The `Supervisor` would remain reporting `Running` state forever, and `get_sidecar_origin`
   would keep returning the stale (now-dead) port as if it were still valid.
3. **Health/readiness failure**: only checked during `start()`'s polling loop, before
   `RUNNING` is reached. There is no ongoing/periodic health poll once `RUNNING` — "healthy"
   currently means "the one-time `/health` poll during startup succeeded," not "is still
   healthy right now." (This is a real, separate gap from crash detection: a process that
   stays alive but stops responding to `/health` would never be detected either. See §9.3.)
4. **API request cannot reach the sidecar**: this is a **frontend/HTTP-layer** concern, not
   a Rust-supervisor one — `runCommand()`'s `fetch()` would simply fail with a
   `CommandNetworkError`, independent of whatever `Supervisor` currently believes. This
   already works correctly and is unrelated to the crash-detection gap.
5. **Application shutdown**: `RunEvent::Exit` calls `process.shutdown()`, which does
   `RUNNING → STOPPING`, sends a hard kill (`Child::kill()`), waits (bounded by
   `timeouts.shutdown`) for the exit, and reports `STOPPING → STOPPED` or
   `STOPPING → FAILED` on timeout. This is the **only** call to `shutdown()` anywhere in the
   application — i.e., today there is exactly one, unambiguous "this exit was intentional"
   signal, and it is structurally impossible for it to race a restart because no restart
   exists yet (§7.3 explains why P2 must preserve this property once one does).

### 2.5 Current retry/restart behavior

**None exists.** Confirmed by direct source read (not inferred): no timer, no loop, no
retry counter anywhere in `sidecar.rs` or `lib.rs`. `sidecar-core`'s own crate doc and
`PHASE4_2A_PART1_SIDECAR_CORE.md` state this as a deliberate prior decision ("Part 1
implements no automatic-retry state machine — restart is always an explicit, separate
caller action... an explicit future enhancement, not an implicit requirement"). **This
document is that future enhancement being decided.**

---

## 3. Problems / Gaps (verified findings only)

| # | Gap | Verified how |
|---|---|---|
| G1 | Mid-run crash is never detected by the running app | `poll_for_crash()` has zero call sites in `lib.rs` (grep-confirmed) |
| G2 | No restart of any kind exists (startup failure or crash) | No timer/loop/retry counter in `sidecar.rs`/`lib.rs` (direct read) |
| G3 | No lifecycle event is ever emitted to the frontend | No Tauri event (`app.emit(...)`) call exists in `lib.rs`; the only frontend-visible signal is `get_sidecar_origin`'s success/failure |
| G4 | `get_sidecar_origin` cannot distinguish "never started", "starting", "crashed and about to retry", or "permanently failed" — every non-`Running` state returns the same shape: `Err(format!("sidecar is not ready yet (state: {:?})", process.state()))` | Direct read of `lib.rs` |
| G5 | Ongoing health is never re-checked after startup | `health_check_ok()` is only called inside `start()`'s loop (§2.4.3) |

None of these are P1 defects — P1's own scope (`docs/phase4/PHASE4E_P1_PART2_IMPLEMENTATION.md`)
never touched `sidecar-core`/`sidecar.rs`/`lib.rs`. They are the explicitly-undecided gap
`PHASE4E_ARCHITECTURE.md` §8 named ("Sidecar crash/restart policy... decide... and document
it once, in one place") and `PHASE4E_FULL_STATUS_AUDIT.md` marked **UNRESOLVED**. G5 is
adjacent but out of P2's stated scope (crash/restart, not ongoing health polling); it is
recorded here per §19 ("document, don't fix unrelated defects") and left for a future
increment to decide whether it needs its own policy.

---

## 4. Lifecycle Owner

**Decision: `src-tauri/src/lib.rs`'s existing `SidecarState`/background-thread ownership
model remains the single authoritative lifecycle owner.** No new owner is introduced.

Concretely, P2's restart logic extends the same component that already exclusively holds
`Mutex<SidecarProcess>` — it does not add a second thread, a second mutex, or a second
place that can call `start()`/`shutdown()`. The existing architecture already satisfies
§6's requirement ("GUI page / API client / worker / event handler must not independently
restart") structurally, because none of those layers currently has, or is given, a handle
to `SidecarState` at all — only `lib.rs` does. P2 must preserve this: the restart decision
loop is additional logic *inside* the one component that already owns the process, driven
by the same `Mutex` that already serializes every access to it (this is also the primary
mechanism for the race protections in §12).

---

## 5. State Machine

**Decision: the existing 8-state `LifecycleState` enum and its transition table
(`sidecar-core/src/state.rs`) are reused unchanged.** No new state is added to the core
crate.

This is a direct application of §7's own instruction ("if the existing architecture
already has equivalent states, reuse them... base the final state machine on the actual
inspected architecture"). Walking through why the existing table is already sufficient for
automatic restart:

- A crash is `RUNNING → CRASHED` — already valid, already implemented (`unexpected_exit`).
- Recovery from any terminal state already requires exactly `terminal → NOT_STARTED`,
  already valid (`reset()`).
- A fresh restart attempt is then exactly `NOT_STARTED → STARTING`, already valid
  (`request_start()`).

So "automatically restart after a crash" is, at the `Lifecycle` FSM level, nothing more
than the supervisor loop calling `reset()` immediately followed by `request_start()` — two
already-existing, already-tested transitions, invoked automatically instead of only ever
manually. **No FSM change is required or proposed.**

The task brief's illustrative example (§7) names a `RESTARTING` state as one to evaluate.
It was evaluated and **rejected as a core-FSM addition**, for a specific reason: adding it
would mean either (a) inserting a new state between `CRASHED` and `NOT_STARTED`, which
would touch the transition table `sidecar-core/src/state.rs` guards with 49 existing tests
and is described in that crate's own doc as intentionally frozen scope for its phase, for
no behavioral gain (the FSM does not need to know *why* a `NOT_STARTED → STARTING` cycle is
happening — manually or automatically — only that it is), or (b) redefining what `CRASHED`
means, which would be a breaking change to an already-correct, already-tested contract.
Instead, "is this an automatic retry in progress" is modeled **one layer above** the FSM,
in a new restart-policy component (§7), and only externalized as a synthesized status label
for observers (§13/§15) — never as a `sidecar-core::LifecycleState` variant. This keeps
`sidecar-core` exactly as framework-independent and minimal as its own crate doc requires,
and satisfies §6's "do not automatically introduce new names if equivalent states already
exist."

---

## 6. Failure Classification

### 6.1 Intentional shutdown

Unchanged from today (§2.4.5): `RunEvent::Exit → SidecarProcess::shutdown()`. Decision
carried forward unchanged: **no automatic restart** ever follows an intentional shutdown.
§7.3/§12 describe the specific mechanism that keeps this true once a background
crash-poll/restart loop exists (today it's trivially true only because no such loop exists
yet).

### 6.2 Startup failure

- **What constitutes it**: spawn failure, handshake failure/timeout, or process exit before
  the first successful `/health` response — all already implemented exactly as today
  (§2.4.1); unchanged by P2.
- **Is readiness required?** Yes, unchanged — `RUNNING` still means "a `GET /health` call
  returned `200`", never merely "the OS reports the PID alive" (this distinction already
  exists and is preserved; see §9).
- **Timeout**: yes, unchanged — `TimeoutConfig::startup` (10s default).
- **Restartable?** **Yes — this is the P2 decision.** Today it is not (§2.5). Startup
  failure and runtime crash are unified under one restart policy (§7): both are "the
  process is not currently healthy and was not intentionally stopped," and both consume
  attempts from the same bounded counter (§7.4) — there is no reason to give a
  crash-immediately-after-launch a separate, more lenient budget than a crash after an hour
  of healthy operation; a process crashing immediately on every launch is exactly the
  scenario the attempt cap exists to catch fastest.

### 6.3 Runtime crash

- **Detection**: extend the existing (currently unused) `poll_for_crash()` primitive with an
  actual periodic caller (§7.2) — this is the one piece of new *plumbing* this document
  identifies as necessary, though its implementation is still deferred to Part 2/3 (§19).
- **Differs from intentional shutdown how**: by the same mechanism `sidecar.rs` already
  uses to distinguish `process_exited` (after a `request_shutdown()`) from
  `unexpected_exit` (without one) — i.e., *which lifecycle state the process was in when the
  exit was observed* (`STOPPING` vs. `RUNNING`) is already the authoritative signal, not a
  side flag. P2 adds one explicit guard on top for the race case (§12, Race B).
- **Automatic restart**: yes, subject to §7's bounded policy.

### 6.4 Health/readiness failure

- **Signal available**: `GET /health`, already implemented, already loopback-only, already
  has no DB/domain dependency (per `PHASE4_PRE_2A_CONTRACT.md` §2).
- **Should it restart the process?** **Not decided by P2 as a new behavior**, because there
  is currently no *ongoing* health poll to fail (G5, §3) — only the one-time startup poll,
  which already gates `STARTING → RUNNING` and is unrelated to restart policy. Introducing
  an ongoing liveness-vs-readiness poll is a larger, separable decision (it needs its own
  interval, its own distinct-from-crash failure semantics, and arguably its own contract
  doc) that P2's brief scope (crash/restart) does not require solving to close G1/G2. It is
  recorded as an explicit **open item**, not silently dropped (§19's "document, don't
  expand scope").
- **Temporary failure retried before process restart?** N/A given the above — no ongoing
  poll exists yet to have a "temporary vs. sustained failure" distinction.

### 6.5 Restart exhaustion

`RESTARTING → FAILED` (in the synthesized-status sense of §5/§13, not a new core-FSM
transition) occurs when the bounded attempt counter (§7.4) is exhausted within the
crash-loop window. At that point the `Lifecycle` FSM is left in its already-correct
terminal `CRASHED` (or `FAILED`/`TIMEOUT`) state — no further automatic `reset()` is called
— and the synthesized external status becomes a permanent, user-visible "sidecar
unavailable" (§13/§15), not silently retried forever. **There is no infinite restart loop**
by construction: the counter is a hard, finite bound (§7.4), not a heuristic.

---

## 7. Restart Policy

### 7.1 Decision

**Bounded automatic restart on both startup failure and runtime crash, with capped
exponential backoff and a hard attempt ceiling.** This directly answers the decision
`PHASE4E_ARCHITECTURE.md` §8 named as still open ("decide whether Rust retries `start()`
automatically or whether recovery is frontend-poll-only") — the answer is **Rust retries
automatically**, bounded, inside the existing supervisor (§4), not left to frontend
polling. Frontend polling (`getSidecarOrigin()` rejection handling, 4E-P3) remains the
correct mechanism for the UI to *observe* the outcome, not to *drive* the retry itself —
per §6's rule that only one component may decide, and per the existing GUI/frontend having
no lifecycle authority today (§4).

### 7.2 New component (not a core-FSM change)

A small, `sidecar-core`-resident, still-framework-independent module — pure decision logic,
no I/O, no timing, matching every other module in the crate's existing "caller supplies the
clock" boundary (`supervisor.rs`'s own doc: "this crate performs no real process spawning,
no real I/O, and no real timing"):

```
RestartPolicy {
    max_attempts: u32,          // hard ceiling within one crash-loop window
    base_delay: Duration,       // first backoff delay
    max_delay: Duration,        // backoff cap
    reset_after_stable: Duration, // sustained RUNNING duration that resets the counter
}

RestartTracker {
    attempts: u32,
    // decide(): given "now" and the tracker's own state (both supplied by the caller,
    // never read from a real clock internally — same boundary as
    // Supervisor::startup_timed_out already documents), returns one of:
    //   Retry { after: Duration }
    //   Exhausted
}
```

This lives in `sidecar-core` (testable with fake/literal time exactly like the existing 49
tests do) but is a **new, separate module**, not an addition to `Lifecycle`/`Supervisor`'s
existing transition table (§5). The actual timer that waits `after` and then calls
`Supervisor::reset()` + `request_start()` again is driven by `src-tauri/src/sidecar.rs`/
`lib.rs`, exactly where all real timing already lives today (`start()`'s own poll loop,
`shutdown()`'s own poll loop) — consistent with the crate's existing, explicit dependency
direction ("sidecar-core → abstract contracts; Tauri adapter → depends on this crate, never
the reverse").

### 7.3 Maximum restart attempts

**5**, within one crash-loop window (§7.4). Chosen, not arbitrary: it matches the
well-established default in both reference systems researched for this decision (§18) —
systemd's `DefaultStartLimitBurst=5` and Kubernetes' kubelet backoff, which most commonly
cited configurations also cap around 5 attempts before surfacing a persistent failure state
to the operator. SOC-IQ has exactly one sidecar instance per desktop session (not a fleet),
so there is no reason to pick a larger number than the systems this document researched
default to for a single failing unit.

### 7.4 Backoff

**Capped exponential backoff**, not fixed delay: `base_delay = 1s`, doubling each attempt,
capped at `max_delay = 30s` (1s, 2s, 4s, 8s, 16s, 30s, 30s, …). A fixed delay was
considered and rejected: per §10's research, both systemd and Kubernetes converged
independently on exponential rather than fixed backoff specifically because a process that
crashes near-instantly on every launch (the worst case, and the most likely real one for a
packaging/dependency misconfiguration) would otherwise restart at the fixed interval
indefinitely until the attempt cap is hit, generating the same log/CPU/log-file churn the
backoff exists to prevent — a fixed delay only bounds *frequency*, not the *total* work
done before the cap is reached, whereas exponential backoff bounds both. This is still the
"simplest strategy that is reliable and appropriate" the brief asks for: it is one
multiply-and-clamp per attempt, no jitter, no per-failure-type tuning — SOC-IQ's single
local process does not need the jitter Kubernetes/systemd add for *many concurrent*
services avoiding a synchronized thundering herd, which does not apply here.

### 7.5 Restart counter

- **Increments**: on every `RUNNING → CRASHED` or a failed startup attempt (§6.2) that the
  policy decides to retry.
- **Resets**: after the sidecar has been continuously `RUNNING` for `reset_after_stable`
  (**60 seconds**, chosen much shorter than Kubernetes' 10-minute default specifically
  because this is one interactively-launched desktop process a user is actively waiting on,
  not a fleet-managed backend service — a sidecar that crashed once, restarted, and then
  ran cleanly for a full minute is reasonably considered recovered, not still "in" the same
  crash episode). This mirrors both researched references' shared pattern of "a sustained
  healthy period clears the backoff state" (§18), scaled to this application's own
  single-user, single-process context rather than copied verbatim.
- **After repeated rapid crashes**: once `max_attempts` (5) is reached without an
  intervening `reset_after_stable` period, the policy returns `Exhausted` (§7.2) and no
  further automatic attempt is made (§6.5).

### 7.6 Crash-loop protection

The combination of §7.3 (hard ceiling) + §7.4 (growing delay) + §7.5 (counter that only
resets on genuine stability, not merely on the next attempt) is the complete protection —
there is no code path that calls `request_start()` without first consulting
`RestartTracker::decide()`, and `decide()` is a pure function that always terminates in
`Exhausted` once the ceiling is reached, never loops indefinitely by construction (no
recursive/self-rescheduling call exists in the design — the *caller* schedules exactly one
timer per `Retry` result, per §7.2).

---

## 8. Shutdown Semantics

Unchanged mechanism (§6.1), with one required addition once a restart loop exists: the
background restart-scheduling logic (§7.2's timer, owned by the same component as §4) must
check an explicit "shutdown was requested" signal — already implicitly available as
"is the current `Lifecycle` state `STOPPING`/`STOPPED` rather than `CRASHED`" — **before**
acting on a pending `Retry`. Concretely: if `request_shutdown()` has been called (state is
now `STOPPING`), any pending backoff timer must be cancelled rather than allowed to fire and
call `request_start()` on a sidecar the application is in the middle of intentionally
stopping. This is the same requirement task brief §11 states directly, and it is addressed
mechanically in §12 (Race B), not left as a note — both must hold the same
`Mutex<SidecarProcess>` (§4), which already prevents the two code paths from running
concurrently; the remaining requirement is that the scheduled-retry closure re-checks state
*after* acquiring that mutex, immediately before calling `request_start()`, not only at the
time the timer was originally scheduled.

---

## 9. Race/Concurrency Protection

All six races named in the task brief, addressed against the existing architecture:

| Race | Scenario | Protection |
|---|---|---|
| A | Crash occurs while a restart is already scheduled | Cannot occur under this design: a crash is only observed by the same single poll loop that also owns scheduling a retry (§4/§7.2) — there is exactly one path from "crash observed" to "retry scheduled," so a second crash cannot be observed until the first's handling (including scheduling) has completed, because both hold the one `Mutex<SidecarProcess>` (§4) for their duration. |
| B | Application shutdown occurs while a restart is scheduled | §8: the retry closure re-checks `Lifecycle` state for `STOPPING`/`STOPPED` immediately before calling `request_start()`, under the same mutex `shutdown()` also acquires — whichever of the two actually runs first under the mutex determines the outcome, and the loser observes the already-updated state and no-ops (matches `Supervisor::request_shutdown`'s existing documented no-op-success contract). |
| C | Multiple crash/exit notifications arrive | `poll_for_crash()`'s existing implementation already takes `self.child` via `.as_mut()`/sets it to `None` on the first observed exit (`sidecar.rs`); a second poll after that sees `child = None` and returns `None` (no-op) — already race-safe by construction, unchanged by P2. |
| D | Health check reports failure while a restart is already underway | Not reachable under this decision (§6.4): P2 introduces no *ongoing* health poll, only the one-time startup poll, which cannot itself be "underway" concurrently with a restart because both `start()` calls (initial and retried) already run sequentially under the one mutex. Recorded as a real future race to design explicitly *if* ongoing health polling (the §6.4 open item) is ever added. |
| E | A stale callback from an old process arrives after a new process starts | `SidecarProcess` already holds exactly one `Option<Child>` at a time, replaced (not merged) on each `start()` — a "callback" here is really just `poll_for_crash()`'s `try_wait()` on whatever `Child` is currently stored, so there is no separate async callback identity that could outlive a generation change to begin with. If a future increment moves crash detection to an OS-level async notification (rather than synchronous polling), a generation counter (incremented once per `start()` call, compared before acting on any exit notification) would be the mechanism — noted as a forward-compatible extension point, not built speculatively now (§19: "no speculative dependencies"). |
| F | Two components request restart simultaneously | Cannot occur under this decision: only one component (§4) is ever capable of calling `request_start()`/scheduling a retry at all — there is no second caller to race against, by the ownership decision itself, not by a lock alone. |

The unifying mechanism across A/B/C/F is **structural, not incidental**: because §4 keeps
exactly one owner and that owner already serializes every access through
`Mutex<SidecarProcess>`, most of the classic supervisor races collapse to "which of two
close-in-time operations acquires the mutex first," which is a property Rust's `Mutex`
already guarantees has *some* well-defined single answer — the design work in §8/§B above
is ensuring the *loser* of that race always no-ops correctly rather than corrupting state,
not building new synchronization primitives.

---

## 10. Event Contract

**Decision: no new event bus. Sidecar lifecycle events are emitted as native Tauri events
(`app.emit(...)`), not routed through the Python-backend SSE stream
(`docs/contracts/event-model.md`).** This is a deliberate, load-bearing distinction, not an
oversight: the existing event-model document defines `GET /events`, published *by the
Python sidecar process itself*. A sidecar that has crashed or has not yet started **cannot
publish an event about its own crash or absence** over a channel that only exists once it
is already running — the two are architecturally incompatible for exactly the failure cases
this document is about. Tauri's own native event system (already a dependency, already used
for nothing lifecycle-related today) is the correct channel precisely because it is emitted
by the Rust process, which is alive and supervising throughout the sidecar's entire
lifecycle including the states where the sidecar itself cannot speak for itself.

Proposed events (all new — none of these exist today; `lib.rs` currently emits nothing):

| Event | Producer | Payload | Transition represented |
|---|---|---|---|
| `sidecar:starting` | `lib.rs` background thread | `{ attempt: u32 }` | `NOT_STARTED → STARTING` |
| `sidecar:started` | same | `{ port: u16 }` | `STARTING → RUNNING` |
| `sidecar:stopping` | same | `{}` | `RUNNING → STOPPING` |
| `sidecar:stopped` | same | `{}` | `STOPPING → STOPPED` (intentional) |
| `sidecar:crashed` | same | `{ exit_code: Option<i32> }` | `RUNNING → CRASHED` |
| `sidecar:restart_scheduled` | same | `{ attempt: u32, delay_ms: u64 }` | synthesized (§5) — backoff timer started |
| `sidecar:restart_exhausted` | same | `{ attempts: u32 }` | synthesized — `RestartTracker::Exhausted` reached, no further auto-retry |
| `sidecar:startup_failed` | same | `{ code: string, message: string }` | `STARTING → FAILED` / `STARTING → TIMEOUT` |

Every payload reuses `SidecarError::code()` (§2.1, already implemented) where applicable —
no second error-code vocabulary is introduced (§14). `sidecar:recovered`/`SIDECAR_RECOVERED`
(named in the task brief's example catalog) is intentionally **not** a separate event: a
recovery is fully represented by a later `sidecar:started` after one or more
`sidecar:crashed`/`sidecar:restart_scheduled` events — adding a distinct "recovered" event
would require the emitter to track "was this a fresh start or a recovery," which is
information the frontend can already derive itself from the sequence it already receives
(no duplicate signal, per §13's "avoid duplicate signals" instruction).

This event contract is a **design-time specification for Part 2/3 to implement**, not
implemented here (§19).

---

## 11. Error Contract

**Decision: sidecar-unavailable is represented by the existing `SidecarNotConnectedError`
(`frontend/src/shared/api/client.ts`), extended to carry a structured reason rather than a
free-text string.** No second, parallel error model is introduced — this directly reuses
`docs/contracts/error-model.md`'s existing `{ code, message }` convention, and reuses
`sidecar-core`'s already-implemented `SidecarError::code()` values (`SIDECAR_SPAWN_FAILURE`,
`SIDECAR_STARTUP_TIMEOUT`, `SIDECAR_UNEXPECTED_EXIT`, `SIDECAR_SHUTDOWN_FAILURE`, …) as the
`code` vocabulary Rust already produces. One new code is needed for the new outcome this
document introduces: `SIDECAR_RESTART_EXHAUSTED` (raised once, when `RestartTracker`
reaches `Exhausted` — §6.5/§7.6), to be added to `sidecar-core/src/error.rs`'s existing enum
in Part 2, alongside the other seven variants already there — not a separately-modeled
error family.

`get_sidecar_origin`'s existing return type (`Result<String, String>`) already distinguishes
"not ready" from success; P2 only needs its `Err` string to be built from
`{ code, message }` rather than the current ad hoc `format!("sidecar is not ready yet
(state: {:?})", ...)`, so the frontend can branch on `code` (per `error-model.md`'s own
rule: "the frontend branches on `code`, never on parsing `message` text") instead of the
`Debug`-formatted `LifecycleState` it would otherwise have to string-match today. This
distinguishes:

- **Sidecar unavailable** (this document's scope): `SIDECAR_*` codes above.
- **Provider error** (`app/threat_intel/exceptions.py`'s existing codes, e.g.
  `TI_RATE_LIMITED`): unrelated, already flows through the `{success:false,error}` command
  envelope (`response-model.md`) once the sidecar *is* reachable — untouched by this
  document.
- **Invalid request** (`INVALID_COMMAND_PAYLOAD`, `error-model.md`'s existing proposed
  code): also unrelated, also only reachable once the sidecar is up.
- **Database/application error**: same — a concern of the command layer once connected,
  not of this document.

No fake-success path exists or is proposed anywhere in this chain — `get_sidecar_origin`
already only ever returns `Ok` once `state() == Running` *and* a port was actually
captured; nothing in this decision weakens that.

---

## 12. GUI/Application Contract

Per §19, this document does not touch the GUI or the frontend's presentation layer. It only
specifies what a consumer (either the legacy PySide6 GUI, if it is ever wired to the Tauri
shell, or — realistically — the React frontend) should be able to observe, derived entirely
from §10's event stream plus the existing `LifecycleState`:

| Consumer-facing label | Derived from |
|---|---|
| Healthy | `sidecar:started` most recently seen (no `sidecar:crashed`/`stopping` since) |
| Starting | `sidecar:starting` seen, `sidecar:started` not yet seen |
| Restarting | `sidecar:restart_scheduled` seen, matching `sidecar:started`/`restart_exhausted` not yet seen |
| Unavailable | transient: between `sidecar:crashed` and the next `sidecar:starting`, or `getSidecarOrigin()` rejected for any reason not yet classified as `Failed` |
| Failed | `sidecar:restart_exhausted` or `sidecar:startup_failed` with no attempts remaining — permanent until a user-initiated action (out of scope, §19) |
| Stopping | `sidecar:stopping` seen, `sidecar:stopped` not yet seen |

This table is the contract; no visual/component design is proposed (§19 — "do not implement
visual redesign"). It directly informs, but does not implement, 4E-P3's frontend
origin-retry loop (`PHASE4E_ARCHITECTURE.md`'s own listed next slice) — P3 can now build
its retry/backoff UI against a defined set of states instead of only "resolved" vs.
"rejected".

---

## 13. Logging/Observability

Reuses the existing `logging.getLogger("SOC-IQ")` infrastructure (`app/logger.py`) **on the
Python side only** — this is unaffected by P2, since P2's entire scope is Rust-side process
supervision that happens partly *before* the Python process exists. On the Rust side, no
logging framework exists today (`lib.rs` uses a bare `eprintln!` for the one case it already
logs); P2 does not introduce a new Rust logging framework either — the brief's own
instruction ("do not introduce a new logging framework") is satisfied by continuing to use
whatever minimal stderr logging already exists, extended to cover the required lifecycle
points, since no `log`/`tracing` crate dependency exists in `src-tauri/Cargo.toml` today and
adding one is out of this document's scope (§19 — "no speculative dependencies").

Required lifecycle log points (each corresponds 1:1 to an event in §10, so a future
increment can trivially log exactly what it emits):

```
sidecar starting               (attempt N)
sidecar ready                  (port P)
sidecar startup failure        (code, message)
sidecar crash                  (exit code)
restart scheduled              (attempt N, delay Dms)
restart attempt                (N of MAX)
sidecar recovered              (implicit: "sidecar ready" after attempt > 1 — no separate log line, matching §10's "no sidecar:recovered event" decision)
restart limit exhausted        (attempts MAX)
intentional shutdown           (already logged today implicitly via shutdown()'s own path)
```

No secrets, API keys, tokens, or request content are ever in scope for this logging — none
of it exists at the process-supervision layer this document covers (the sidecar's API keys
live in `app/settings/`, several layers above where P2 operates).

---

## 14. Implementation Plan (for Parts 2–3)

1. **`sidecar-core`**: add the `RestartPolicy`/`RestartTracker` module (§7.2) and the
   `SIDECAR_RESTART_EXHAUSTED` error variant (§11). No change to `state.rs`'s transition
   table (§5). Extend `sidecar-core/tests/supervisor_tests.rs` (or a new
   `restart_policy_tests.rs`) with fake-clock tests for: attempt counting, exponential
   backoff values, the stable-period reset, and exhaustion — mirroring the existing
   fake-time-supplied-by-caller pattern already used throughout the crate.
2. **`src-tauri/src/sidecar.rs`**: wire a real caller of the existing `poll_for_crash()`
   (currently dead code in the running application, §3 G1) into a periodic check, and add
   the shutdown-requested guard (§8/§12 Race B) immediately before any automatic
   `request_start()` retry.
3. **`src-tauri/src/lib.rs`**: replace the current `eprintln!`-only failure path and the
   currently-nonexistent crash-poll loop with the restart-scheduling logic driven by
   `RestartTracker`; add the `app.emit(...)` calls for each event in §10 at the
   corresponding existing (or newly added) transition point; update `get_sidecar_origin`'s
   error string to the `{code, message}` shape (§11).
4. **`frontend/src/shared/api/client.ts`**: extend `SidecarNotConnectedError` to carry the
   structured `code`/`message` §11 now provides, without changing its existing external
   shape/callers beyond that.
5. **`frontend/src/shared/events/`**: add a Tauri-native listener (separate from the
   existing SSE `eventSourceManager.ts`, per §10's explicit "not the same channel"
   decision) for the `sidecar:*` events, feeding the §12 status derivation.

None of the above is implemented by this document (§19/§21).

---

## 15. Verification Plan (for Part 4)

- All six races in §9 have a corresponding test (extending `sidecar-core/tests/`,
  following the existing `supervisor_tests.rs::crash_does_not_auto_restart`-style naming
  already present).
- `RestartTracker` unit tests confirm: attempt count increments only on retry-eligible
  failures; backoff values match §7.4's formula exactly (1s/2s/4s/8s/16s/30s/30s…);
  `Exhausted` is returned exactly at attempt 6 (i.e., after 5 retries), never later, never
  earlier; the counter resets only after a full `reset_after_stable` (60s, simulated)
  window of continuous `RUNNING`.
- An integration-level test (or manual verification, given the Rust toolchain limitation —
  §20) that a real killed-mid-run process is observed via `poll_for_crash()`, restarted, and
  reaches `RUNNING` again with a fresh port.
- Confirm `RunEvent::Exit` during an active backoff wait does **not** result in a
  subsequent `request_start()` call (§8/§12 Race B) — the concrete regression this whole
  document exists to prevent.
- Re-run the full existing baseline (Python `pytest`, `sidecar-core cargo test`, frontend
  `vitest`) to confirm no regression outside the touched files.
- Confirm no `sidecar-core` transition table change (`git diff` on `state.rs` should be
  empty per §5's decision) once Part 2 actually lands.

---

## 16. Research (§18 of the task brief)

Two authoritative, high-quality references were consulted for the restart-policy decision
(§7); no source's design was copied blindly — both were adapted, not ported.

1. **systemd service restart/rate-limiting** (`RestartSec`, `StartLimitIntervalSec`,
   `StartLimitBurst`). Observed: systemd's defaults are a 5-attempt burst limit within a
   10-second sliding window, with a per-restart delay (`RestartSec`, commonly configured
   around 1–10s in the reference material reviewed), and exceeding the burst limit puts the
   unit into a permanent failed state requiring manual intervention rather than continuing
   to retry silently. **Applied to SOC-IQ**: the "hard ceiling + permanent failure state,
   no silent infinite retry" shape is exactly §6.5/§7.6's design; the specific
   attempt-count default (5) is carried over directly (§7.3) as a reasonable,
   widely-precedented default for a single supervised process.
2. **Kubernetes kubelet container restart backoff** (`CrashLoopBackOff`). Observed:
   Kubernetes uses capped exponential backoff (commonly cited as 10s/20s/40s/80s/160s,
   capped at 300s) rather than a fixed delay, specifically to bound total restart work done
   before intervention, and resets the backoff after a sustained period of healthy running
   (commonly cited as 10 minutes). **Applied to SOC-IQ**: the *shape* (exponential, capped,
   with a stability-based reset) is adopted directly (§7.4/§7.5); the specific *numbers*
   are deliberately scaled down (1s base, 30s cap, 60s stability window vs. Kubernetes'
   10s/300s/600s) because Kubernetes' numbers are tuned for a cluster-managed, possibly
   large/slow-starting containerized service being supervised on the operator's behalf,
   whereas SOC-IQ's sidecar is one lightweight local Python process a single interactive
   desktop user is waiting on — a multi-minute cap or a ten-minute stability window would
   make the desktop application feel unresponsive to the exact failure class (fast
   crash-on-launch) this policy is meant to recover from quickly.

Neither reference's *implementation mechanism* (systemd unit files; the Kubernetes kubelet
control loop) is applicable to SOC-IQ's architecture at all — only the *policy shape* was
taken, which is what §18 asks for ("Do not add external complexity merely because another
project uses it"). No dependency was added to obtain either behavior; §7.2's design is a
pure function `sidecar-core` already has the tooling (fake-time-supplied tests) to verify
without adopting any part of either reference project's actual code or configuration
surface.

---

## 17. P1 Protection

**Phase 4E-P1 source was not reopened or modified.** This session touched exactly one file:
this document itself (`docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`, new).
No file under `frontend/src/shared/api/`, `app/application/`, `app/api/`, or any other path
`PHASE4E_P1_PART2_IMPLEMENTATION.md` §15 lists as P1's own changed-files set was read for
the purpose of modification (only for the inspection this document required, per §2/§19),
and none was written to.

---

## 18. Source Changes

```text
Production source changes: 0
```

No file under `app/`, `src-tauri/`, `sidecar-core/`, or `frontend/` was modified. This
document (§21 "Final Directive": "Do not implement the actual crash/restart supervisor in
Part 1") is the only artifact produced.

---

## 19. Verification (this session)

```text
$ find . -maxdepth 3            # repository structure inspected
$ grep -ril sidecar .            # sidecar lifecycle traced across Python/Rust/TS
$ view sidecar-core/src/{lib,state,supervisor,error,timeout}.rs   # core crate read in full
$ view src-tauri/src/{lib,sidecar}.rs                              # real adapter read in full
$ grep -n restart docs/                                            # existing decisions/gaps located
$ python3 -m pytest tests/ -q --ignore=tests/gui
  600 passed   (matches the documented P1/4D-era baseline exactly — confirms the frozen
                baseline is intact; this session added pytest/requirements.txt packages to
                a scratch environment to run this, no project file was changed to make it
                pass)
$ cd sidecar-core && cargo test
  cargo: not found  — no Rust toolchain is available in this sandbox (this is the same
                       "toolchain-version blocker" `IMPLEMENTATION_STATUS.md`'s addendum
                       already documents for `cargo check`/`src-tauri`; this session could
                       not independently re-run the 49 previously-reported `sidecar-core`
                       tests, and does not claim to have)
```

- Repository structure inspected — yes (§2.1).
- Sidecar lifecycle traced — yes, startup and failure paths (§2.4), both languages.
- Existing lifecycle mechanisms identified — yes (§2).
- Existing events/signals identified — yes; found **none** exist yet for lifecycle (§3 G3),
  informing §10's from-scratch (but reused-vocabulary) design.
- Existing health/readiness mechanism identified — yes (§2.4.3, §6.4).
- Existing error/response mechanisms identified — yes (§11, reused directly).
- Lifecycle owner selected — yes, unchanged from today (§4).
- State machine defined — yes, unchanged from today (§5).
- Restart policy defined — yes (§7).
- Shutdown semantics defined — yes, extended (§8).
- Race protections defined — yes, all six (§9/§12).
- Implementation boundaries defined — yes (§14/§19 scope guard).
- Documentation created — yes (this file).

---

## 20. Git

```text
$ git status
fatal: not a git repository (or any of the parent directories): .git
```

No `.git` directory exists in the extracted archive (this is an extracted ZIP checkpoint,
not a git checkout — consistent with every prior phase document in this project, which are
themselves delivered and re-verified via fresh ZIP extraction rather than git history, per
e.g. `PHASE4E_P1_PART2_IMPLEMENTATION.md` §17). No commit was made or attempted.

---

## 21. Final Report Summary

**Architecture findings**: a real, tested sidecar lifecycle core and process adapter
already exist (§2) and are more complete than "inspect first" implied might be needed —
the actual gap is narrow and specific (crash detection has no caller, no restart of any
kind exists, no lifecycle event is ever emitted — §3), not a missing architecture.

**Decisions**: single existing owner retained (§4); existing 8-state FSM reused unchanged
(§5); bounded automatic restart — 5 attempts, capped exponential backoff (1s→30s), 60s
stability reset (§7) — for both startup failure and runtime crash (§6.2/§6.3); intentional
shutdown always wins races against a pending retry (§8/§12); lifecycle events go over
Tauri-native events, not the Python SSE stream (§10); sidecar-unavailable errors reuse the
existing `{code,message}`/`SidecarNotConnectedError` model plus one new error code (§11).

**Documentation**: `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md` (this
file, new). No other file created or modified.

**Source changes**: `Production source changes: 0` (§18).

**Verification**: see §19 — Python baseline (600 passed) re-confirmed live; Rust baseline
could not be re-run in this sandbox (no toolchain), unchanged from the last
independently-verified count (49 passed, per `PHASE4_2A_PART1_SIDECAR_CORE.md`/
`IMPLEMENTATION_STATUS.md`) since no `sidecar-core` source was touched.

**P1 protection**: Phase 4E-P1 source was not reopened or modified (§17).

**Git**: no repository present; no commit made (§20).

**Next checkpoint:**

```text
Next target:
Phase 4E-P2 Part 2 — Sidecar Lifecycle Supervisor Implementation
```
