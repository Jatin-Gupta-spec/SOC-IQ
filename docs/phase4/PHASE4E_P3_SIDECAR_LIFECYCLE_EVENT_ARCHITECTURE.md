# Phase 4E-P3, Part 1 — Sidecar Lifecycle Observability + Frontend Integration Architecture

**Status:** Architecture/design/documentation checkpoint only. No source code was written
by this document. Builds on, and treats as frozen, `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`
(the P2 design) and the P2A→P2B-5 implementation it produced. See §3 for the exact frozen
boundary and §32 for the zero-source-changes confirmation.

---

## 1. Executive Summary

Phase 4E-P2 (Architecture through Part 2B-5, all frozen) built a real, tested Rust-side
crash/runtime-restart supervisor: bounded automatic restart, capped exponential backoff, a
stability-window attempt-counter reset, and complete shutdown/exhaustion race protection —
all verified against actual source, not inferred. What P2 explicitly did **not** build,
and explicitly deferred to this phase (confirmed by direct source read, §4 below), is any
way for that backend truth to reach the frontend: **zero `app.emit`/`.emit(` call sites
exist anywhere in the repository**, and `get_sidecar_origin`'s error path is still an
unstructured, ad hoc string.

This document designs the smallest architecture that closes that gap: a canonical
Tauri-native lifecycle event, two small synthesized (non-FSM) events for information the
canonical event cannot itself carry, a monotonic-sequence staleness/ordering guarantee, a
frontend projection type that is explicitly documented as a *view*, not a second authority,
and a `{code, message}` error contract that extends (never replaces) the existing
`SidecarNotConnectedError`/`error-model.md` convention.

A second, load-bearing finding from this checkpoint's own inspection (§6): **the React
frontend has no application shell yet.** `App.tsx` and `router.tsx` are both explicitly
documented placeholders (Phase 4G is the navigation shell); `frontend/src/shared/state/`
and `frontend/src/shared/components/` are both empty; there is no status bar, no toast/
notification system, no global store (no Redux/Zustand/etc. in `package.json`), and
`useEventStreamStatus.ts`'s own doc comment already states "no existing UI consumes
connection status yet... confirmed by inspection." This changes the shape of §19/§22 below
materially from what the task brief's illustrative UI-integration list assumes: there is
nothing to "integrate into" today. This document defines where the projection *will* live
and how a future UI *will* consume it, and is explicit that no such UI exists yet to wire
up — building one is out of scope (§33).

**Final classification: PASS / COMPLETE.** The architecture is internally consistent,
grounded entirely in source actually read this session, and implementation-ready. No
ambiguity required reopening P2.

---

## 2. Current Architecture (verified findings)

Everything below was confirmed by reading the actual extracted archive
(`SOC-IQ-Phase4E-P2-Part2B-5-COMPLETE.zip`) this session — nothing is inferred from
filenames or from the P2 documents' own prose alone.

| Layer | File | Confirmed responsibility |
|---|---|---|
| Framework-independent FSM | `sidecar-core/src/state.rs` | `LifecycleState` — **8** states (`NotStarted, Starting, Running, Stopping, Stopped, Failed, Timeout, Crashed`), explicit `can_transition_to` table, no `Restarting` variant |
| Typed errors | `sidecar-core/src/error.rs` | `SidecarError`, 9 variants incl. `RestartExhausted { attempts }`, each with a stable `.code()` (e.g. `SIDECAR_RESTART_EXHAUSTED`) |
| Restart policy/accounting | `sidecar-core/src/restart.rs` | `RestartPolicy` (config), `RestartTracker` (the one attempt counter), `RestartDecision::{Retry{attempt,after}, Exhausted{attempts}}`, `RestartSchedule`/`RestartToken` (pure at-most-one-pending bookkeeping) |
| Real timer | `src-tauri/src/restart_scheduler.rs` | `RestartScheduler`/`StabilityScheduler` — real `std::thread`-based delay runners, single-flight via `RestartToken`, never block the Tauri main thread or hold `SidecarState`'s mutex across a sleep |
| Real process adapter | `src-tauri/src/sidecar.rs` | `SidecarProcess` — spawns, handshakes, polls `/health`, `poll_for_crash()` |
| Application wiring / lifecycle owner | `src-tauri/src/lib.rs` | One `SidecarState` (`Mutex<SidecarProcess>` + `Mutex<RestartTracker>` + `RestartPolicy` + `RestartScheduler` + `StabilityScheduler`), constructed once in `run()`. Every mutating access goes through `lock_process()`. `run_crash_poll_loop`, `handle_retry_eligible_failure`, `attempt_restart`, `begin_stability_window`/`confirm_stability_if_still_running` are the only functions that touch lifecycle state. **Zero `.emit(` calls anywhere in this file or the crate (grep-confirmed, this session).** |
| Tauri command surface | `src-tauri/src/lib.rs` | Exactly one command, `get_sidecar_origin`, `Result<String, String>`, `Err` built from `format!("sidecar is not ready yet (state: {:?})", ...)` — still the pre-P2 ad hoc shape |
| Python sidecar | `app/api/entrypoint.py`, `app/api/app.py` | `GET /health`, `GET /events` (SSE, domain events only), `POST /commands/{name}` |
| Frontend origin/command bridge | `frontend/src/shared/api/client.ts` | `getSidecarOrigin()` (wraps `invoke`), `runCommand<K>()`, `SidecarNotConnectedError` (free-text reason today), 4 `CommandClientError` subclasses for the command envelope (unrelated to lifecycle) |
| Frontend domain-event bus | `frontend/src/shared/events/eventSourceManager.ts` | Module-level, ref-counted `EventSource` singleton to `GET /events`. Own `EventStreamStatus`: `idle/connecting/open/unavailable/closed`. **This is a connection-status signal for the SSE transport, not a sidecar-lifecycle signal** — see §7 for why the two must not be conflated. |
| Frontend application shell | `frontend/src/app/App.tsx`, `router.tsx` | Both explicitly documented placeholders. No navigation shell, no status/notification UI, no global store. Confirmed empty: `frontend/src/shared/state/`, `frontend/src/shared/components/`, `frontend/src/features/`. |

### 2.1 What P2 built vs. what it explicitly deferred

Read directly from `src-tauri/src/lib.rs`'s own module doc and
`docs/phase4/PHASE4E_P2_FINAL_CRASH_RESTART_AUDIT.md` §C.2/§H/I1 (the frozen Part 4
audit/freeze gate):

- **Built, tested, frozen:** crash detection (`run_crash_poll_loop`), bounded automatic
  restart with capped exponential backoff (`handle_retry_eligible_failure`/
  `attempt_restart`), the `reset_after_stable` stability window
  (`begin_stability_window`/`confirm_stability_if_still_running`), all six races named in
  the P2 architecture doc §9, and `SIDECAR_RESTART_EXHAUSTED`.
- **Explicitly deferred, in P2's own words** (`lib.rs` module doc, Part 2B-3 note): "The
  *frontend*-facing `{code, message}` contract for `get_sidecar_origin`/Tauri events...
  remains out of this checkpoint's scope... that is Part 3." The Final Audit's own I1
  finding: **"Frontend event/error contract intentionally deferred."**

This confirms the mission statement in the task brief exactly: P3's job is the boundary
from an already-correct backend to an as-yet-nonexistent frontend signal, not a redesign of
anything upstream.

---

## 3. Frozen P2 Boundary

Per the task brief §1, the following are treated as complete and are **not reopened**:
Phase 4E-P1; Phase 4E-P2 Parts 1, 2A, 2B-1 through 2B-5 (the exact status table the task
brief itself supplies). This document adds exactly one new file
(`docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md`, this one) and reads,
without modifying, `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`,
`PHASE4E_P2_PART2B2_IMPLEMENTATION.md`, `PART2B3_IMPLEMENTATION.md`,
`PART2B4_VERIFICATION.md`, `PHASE4E_P2_FINAL_CRASH_RESTART_AUDIT.md`, plus the actual
source listed in §2. **No genuine P2 defect was found this session** (§34) — the only gap
is the deferred event/error contract §2.1 already documents as an intentional, on-purpose
deferral, not a bug.

One inventory note, not a defect: the task brief's own file list (its §4) names
`src-tauri/src/state.rs` and `src-tauri/src/error.rs`. Neither exists in this archive —
`src-tauri/src/` contains exactly `lib.rs`, `main.rs`, `restart_scheduler.rs`, `sidecar.rs`
(confirmed by directory listing, this session). The equivalent responsibilities
(`LifecycleState`/`Lifecycle` and `SidecarError`) live in `sidecar-core/src/state.rs` and
`sidecar-core/src/error.rs` instead, which this document reads and cites throughout. This
is recorded as an **INFORMATIONAL** brief/reality mismatch (§34), not acted on further.

---

## 4. Problem Statement

How does `src-tauri`'s already-correct, already-frozen `SidecarState` communicate lifecycle
truth to a React frontend that currently has:

1. no Tauri event listener for anything lifecycle-related (zero exist),
2. a structurally *different*, pre-existing event channel (`eventSourceManager.ts`) that is
   architecturally the wrong channel for this purpose (§7), and
3. no application shell to display the result in yet (§2, §19)?

— without creating a second lifecycle authority, without conflating the SSE
connection-status signal with sidecar lifecycle truth, and without over-building a UI this
phase does not need.

## 5. Goals

- Exactly one new, canonical, Tauri-native event boundary; exactly one emitter.
- A frontend projection type explicitly documented as a view of backend truth.
- Ordering/staleness correctness that does not depend on Tauri's own delivery-order
  guarantees (§13 — a real gap the research in §30 surfaced).
- A `{code, message}` error contract for `get_sidecar_origin` that finally uses the
  `SidecarError::code()` vocabulary `sidecar-core` already exposes for exactly this.
- A late-mounting-listener story (a component that starts observing after several
  transitions have already happened) that does not require replaying history.

## 6. Non-Goals

- No frontend navigation shell, status bar, toast system, or any visual design (§33 — this
  does not exist yet; building it is a different phase's scope).
- No change to `sidecar-core`'s transition table, `RestartPolicy`/`RestartTracker`, or
  `restart_scheduler.rs`'s timer mechanics.
- No new state added to `LifecycleState`. No `RESTARTING` core-FSM variant (P2 §5 already
  rejected this for a documented reason; this document does not re-litigate it, only
  re-confirms it still holds given the actual current source, §8).
- No WebSockets, no Redux/Zustand/any state library (none exists today; §33/§18 forbid
  introducing one speculatively).
- No polling loop added to the frontend (§24).
- No implementation. Part 2 (a future checkpoint) implements this.

---

## 7. Existing Frontend Event Architecture (§6/§22 of the task brief)

**One** frontend-observable event mechanism exists today: `eventSourceManager.ts`'s
ref-counted `EventSource` singleton against `GET /events`. It is:

- **Owned by**: the singleton module itself (`source`/`status`/`subscribers` module-level
  state); consumed via `subscribe()`/`useEventStream`/`useEventStreamStatus`.
- **Emitted by**: the Python sidecar process (`app/api/app.py`'s SSE route), relayed
  unmodified.
- **Vocabulary**: `domain.action` (`analysis.*`, `investigation.*`, `ti.enrichment.*`),
  defined once in `docs/contracts/event-model.md` and mirrored in
  `frontend/src/shared/events/types.ts`'s `EventName` union.
- **Status model**: `idle | connecting | open | unavailable | closed` — this is *connection*
  status for the browser's `EventSource` object, derived indirectly from
  `getSidecarOrigin()` succeeding/failing, not a direct signal of Rust-side lifecycle state.

**Is there already a sidecar/application status event? No** (confirmed: `EventName` has no
sidecar-prefixed member; no Tauri `.emit(` call exists anywhere). **Is there an existing
status model that should be extended?** No — and it should specifically **not** be
extended, for a structural reason: `EventStreamStatus` answers "is the browser's
`EventSource` object connected," which conflates two independent failure causes an operator
needs to distinguish — (a) the sidecar is unreachable/crashed (Rust-side truth, this
document's whole subject) vs. (b) the sidecar is healthy but the *SSE stream specifically*
had a transient hiccup the browser's native reconnect is already handling. Collapsing both
into one enum is exactly the kind of "two lifecycle authorities that can disagree" the task
brief's hard-stop conditions warn against — `EventStreamStatus` would have to either lag
Rust-side truth (still says `"open"` for seconds after a crash, until the *next* SSE
send/heartbeat fails) or be driven by two unrelated emitters. **No naming collision exists**
today (`domain.action` vs. this document's `sidecar:` colon-prefixed names, §10, are
already visually and structurally distinct) — but a collision is exactly what reusing the
same `EventName`/status enum would risk introducing, so this document deliberately keeps
them separate channels, matching the frozen P2 §10 decision (§9 below).

A separate, unrelated PySide6 desktop GUI (`app/gui/`) has its own
`status_badge.py`/`toast_notification.py`/`system_status_section.py` components — these are
part of a different application entirely (confirmed unwired to Tauri, per P2 §2.2: "the GUI...
[has] no sidecar lifecycle authority today and none is proposed"), not a frontend
integration point. Noted for completeness (§34, INFORMATIONAL); not used as a design input
because it is not the same application `src-tauri`/`frontend/src` ship together.

---

## 8. Lifecycle Vocabulary

**Decision: reuse the existing 8-state `LifecycleState` enum unchanged. No new backend
state.** Directly re-verified against `sidecar-core/src/state.rs` this session (§2): the
enum is exactly `NotStarted, Starting, Running, Stopping, Stopped, Failed, Timeout,
Crashed`. `RESTARTING` is **not** a real backend state — it does not appear in the enum, in
`can_transition_to`'s table, or anywhere in `sidecar-core`. This is the exact
"`RESTARTING` derived from `CRASHED` + restart scheduled" case the task brief §8
anticipates: confirmed by reading `src-tauri/src/lib.rs`'s `handle_retry_eligible_failure`,
a restart-eligible failure leaves the FSM in `Crashed`/`Failed`/`Timeout` (whichever the
failure actually was) and schedules a *separate*, policy-layer timer
(`RestartScheduler`/`StabilityScheduler`) — it never touches `Lifecycle` again until the
timer fires and calls `reset()` (→ `NotStarted`) immediately followed by `request_start()`
(→ `Starting`). "Restarting" is therefore a synthesized frontend-observable concept spanning
the interval between a `Crashed`/`Failed`/`Timeout` transition and the next `Starting`
transition, exactly as P2 §5/§12 already concluded and this document re-confirms against
the actual current implementation rather than assuming the P2 doc's prose is still accurate.

### 8.1 Backend → frontend-observable mapping

| Backend `LifecycleState` | Frontend-observable status | Why |
|---|---|---|
| `NotStarted` | `Idle` | Pre-launch; only ever observed instantaneously before the first `Starting` |
| `Starting` | `Starting` | 1:1 |
| `Running` | `Healthy` | 1:1 — named `Healthy` not `Running` because "is the sidecar reachable" is what a consumer cares about, matching P2 §12's own consumer-facing label |
| `Stopping` | `Stopping` | 1:1 |
| `Stopped` | `Stopped` | 1:1 (intentional shutdown only — this state is unreachable any other way, per the transition table) |
| `Crashed` **and** a `sidecar:restart_scheduled` event has been seen for this crash with no terminal event since | `Restarting` | Synthesized, not 1:1 (§8, §12) |
| `Crashed` **and** `sidecar:restart_exhausted` has been seen, **or** `Crashed`/`Failed`/`Timeout` with no restart scheduled (initial startup exhausted immediately, or restart is not eligible) | `Failed` | Synthesized — permanent, terminal, user-visible |
| `Failed`, `Timeout` (not yet exhausted — a retry is still pending or about to be scheduled) | `Restarting` (transiently) → `Failed` (once exhausted) | Same synthesis as `Crashed`; `Failed`/`Timeout` are retry-eligible exactly like `Crashed` per P2 §6.2 |

No backend state is hidden from the frontend; two backend states (`Crashed`/`Failed`/
`Timeout`) each map to **two different** frontend statuses depending on which
policy-layer event has also been seen — this is documented explicitly, per the task brief
§8's own requirement, rather than left as an implicit frontend inference.

---

## 9. Event Architecture

### 9.1 Channel: Tauri-native events, not the SSE stream (reaffirmed, not reopened)

**Reaffirmed from P2 §10, and reverified against current source, not merely copied**: a
sidecar that has crashed or never started cannot publish an event about its own absence
over a channel (`GET /events`) that only exists once it is already running and reachable.
This is still true today — `eventSourceManager.ts`'s own connect() only even attempts to
open once `getSidecarOrigin()` resolves, i.e. only once the sidecar is already `Running`.
Tauri's native event system (`app.emit`/`listen`, already a `tauri` dependency, currently
unused for anything) is emitted by the Rust process, which supervises the sidecar's entire
lifecycle including every state where the sidecar cannot speak for itself. No new event bus
or dependency is introduced (§33).

### 9.2 Taxonomy: Model C (hybrid) — evaluated, not assumed

The task brief's own framing (§10 of the brief) requires evaluating Model A (one canonical
event), Model B (many semantic events), and Model C (hybrid) rather than accepting the P2
doc's illustrative 8-event list uncritically. This document performs that evaluation fresh
against the *current* backend implementation (not the pre-implementation architecture
sketch), and reaches a **narrower** hybrid than P2 §10 sketched:

- **Model A alone (pure canonical `state_changed`) is insufficient**: two of the events
  P2 §10 catalogued are not represented by *any* `Lifecycle` transition at all —
  `restart_scheduled` (attempt/delay is prospective information about a future action, not
  a past-tense transition) and `restart_exhausted` (§6.5 of the P2 doc, reverified against
  `handle_retry_eligible_failure`'s `Exhausted` arm this session: "the lifecycle is left in
  its already-correct terminal state... no further `reset()` is called" — i.e. **no new FSM
  transition occurs at the moment of exhaustion**, so there is nothing for a pure
  state-event model to emit). A consumer using only `state_changed` could not distinguish
  "just crashed, retry imminent" from "just crashed, permanently" — both are the same
  `Crashed` state with no subsequent transition in the exhausted case.
- **Model B (P2 §10's full 8-event list) is more than the current implementation actually
  produces distinct information for.** Re-reading `lib.rs` directly: `sidecar:starting`,
  `sidecar:started`, `sidecar:stopping`, `sidecar:stopped`, `sidecar:crashed`, and
  `sidecar:startup_failed` are each exactly one `Lifecycle::transition` call with no
  additional information beyond `{state, previous_state, timestamp}` (`SidecarError` from
  `process.start()`'s `Err` arm, when present, is already representable as a `reason` field
  on that same transition rather than a separate event) — six separate event *names* for
  six cases that are otherwise structurally identical payloads is exactly the "event spam"
  §9 of the task brief warns against, and reopens the naming-surface P2 §10 itself argued
  against for `sidecar:recovered` ("no duplicate signal... the frontend can already derive
  it").
- **Selected: Model C, three events** — one canonical `state_changed` covering every real
  `Lifecycle` transition, plus exactly the two synthesized events that carry information no
  transition payload could otherwise carry (§9.3). This is a **reduction** from P2 §10's
  catalog, made possible by moving `reason`/`error_code` onto the canonical payload
  instead of encoding it in the event name — the P2 doc's own §11 already put `SidecarError`
  in scope for this reuse; this document just applies that reuse to collapse
  `sidecar:crashed`/`sidecar:startup_failed`/`sidecar:started`/`sidecar:stopping`/
  `sidecar:stopped`/`sidecar:starting` into one event name instead of six.

### 9.3 The three events

| Event | Producer (single site each) | Represents | Why it exists as its own event |
|---|---|---|---|
| `sidecar:state_changed` | `lib.rs` — every call site that currently drives `Lifecycle::transition` (the `setup` thread's `start()`, `run_crash_poll_loop`'s `poll_for_crash()`, `attempt_restart`'s `reset()`/`start()`, `RunEvent::Exit`'s `shutdown()`) | Every real backend transition: `NotStarted→Starting→Running→Stopping→Stopped`, plus `→Crashed`/`→Failed`/`→Timeout` | Canonical — the backbone every projection state derives from |
| `sidecar:restart_scheduled` | `lib.rs::handle_retry_eligible_failure`, the `Retry` arm only | Policy-layer decision, not an FSM transition | Carries `attempt`/`max_attempts`/`delay_ms` — information that does not exist anywhere on the `Lifecycle` FSM and cannot be derived from a `state_changed` payload |
| `sidecar:restart_exhausted` | `lib.rs::handle_retry_eligible_failure`, the `Exhausted` arm only | Policy-layer terminal decision, not an FSM transition (§9.2) | The one case with genuinely no corresponding `Lifecycle::transition` to attach a `reason` to |

`sidecar:recovered` is, again, deliberately **not** a fourth event, for the identical
reason P2 §10 already gave and this document re-confirms still holds against current
source: a recovery is fully derivable as a later `state_changed{state: Running}` following
one or more `state_changed{state: Crashed}`/`restart_scheduled` events.

---

## 10. Payload Contracts

### 10.1 `sidecar:state_changed`

```text
{
  state: "NOT_STARTED" | "STARTING" | "RUNNING" | "STOPPING" | "STOPPED"
       | "CRASHED" | "FAILED" | "TIMEOUT",
  previous_state: <same union>,
  reason: { code: string, message: string } | null,
  sequence: u64,
  generation: u32,
  timestamp: string (RFC 3339, matches the existing SSE envelope's `timestamp` shape
             in `docs/contracts/event-model.md` for consistency, even though this is a
             different channel),
}
```

- **Required**: `state`, `previous_state`, `sequence`, `generation`, `timestamp`.
- **Optional**: `reason` — present exactly when the transition's origin was a
  `SidecarError` (`Starting→Failed`, `Starting→Timeout`, `Running→Crashed`,
  `Stopping→Failed`); `null` for every clean transition (`→Starting`, `→Running` on
  success, `→Stopping`, `→Stopped`). `reason.code` reuses `SidecarError::code()`
  (`sidecar-core/src/error.rs`) verbatim — no second error-code vocabulary (§11).
- **Forbidden**: any field derived from `SidecarError`'s `Debug` output, the raw OS error,
  the child PID, the resolved working directory, the launch command line, or any
  environment variable — none of these are in scope for a lifecycle-status consumer, and
  `SidecarLaunchConfig`'s working directory in particular could reveal filesystem layout
  the frontend has no legitimate use for. `SidecarError`'s existing `Display` impls
  (`error.rs`, reviewed this session) already avoid raw OS internals in every variant's
  message string, so reusing `.to_string()` for `reason.message` is safe as-is with no
  additional filtering needed.

### 10.2 `sidecar:restart_scheduled`

```text
{
  attempt: u32,        // 1-indexed; matches RestartDecision::Retry's own field
  max_attempts: u32,   // RestartPolicy::max_attempts, so the frontend never hardcodes 5
  delay_ms: u64,
  sequence: u64,
  generation: u32,
  timestamp: string,
}
```

### 10.3 `sidecar:restart_exhausted`

```text
{
  attempts: u32,       // matches RestartDecision::Exhausted's own field
  code: "SIDECAR_RESTART_EXHAUSTED",  // SidecarError::RestartExhausted{attempts}.code(),
                                       // included as a literal for symmetry with
                                       // state_changed's reason.code, not because a second
                                       // outcome is possible here
  message: string,     // SidecarError::RestartExhausted{attempts}.to_string()
  sequence: u64,
  generation: u32,
  timestamp: string,
}
```

### 10.4 `sequence` and `generation` (§13/§14/§15 below)

- **`sequence`**: one process-lifetime `AtomicU64` (or equivalent, owned by `SidecarState`
  alongside the existing `restart_tracker`/`scheduler`/`stability` fields — same single
  owner, §25), incremented immediately before every emission of any of the three events
  above, from any of their single call sites. Strictly increasing for the life of the
  application; never reset, never reused. This is the field the frontend projection
  actually uses for staleness/ordering (§13).
- **`generation`**: increments by exactly one on every `NotStarted → Starting` transition
  (i.e., once per real launch/restart attempt of the underlying process). Purely
  informational/diagnostic for a human or the projection's own `attempt` display — `sequence`
  alone is sufficient for correctness (§13), so `generation` carries no safety burden; it
  exists because a raw sequence number is not human-legible for "which restart episode was
  this."

---

## 11. Error Contract

**Decision: extend `SidecarNotConnectedError` (`frontend/src/shared/api/client.ts`) to
carry a structured `{code, message}` reason, exactly as P2 §11 specified and the Final
Audit's I1 confirmed was never implemented.** No second, parallel error model.

`get_sidecar_origin`'s current `Err(String)` (built from an ad hoc `format!`, confirmed by
direct read, §2) becomes `Err({code, message})`, serialized the same way every other
`{success:false, error:{code,message}}` envelope in this codebase already is
(`app/application/responses.py::Envelope`, `docs/contracts/error-model.md`,
`docs/contracts/response-model.md`) — Tauri commands can return any `Serialize` error type,
so this is a type change to the command's `Result` error variant, not a new transport.

Code mapping (every `get_sidecar_origin` rejection reason, exhaustively, from the actual
current match arms in `lib.rs`):

| Current situation (`lib.rs`, confirmed) | New `code` | `message` source |
|---|---|---|
| `try_lock()` fails (a mutating call is in progress) | `SIDECAR_BUSY` | Static string — this is not a `SidecarError` variant; it is a transient lock-contention case with no `sidecar-core` equivalent, so one small, new, non-`SidecarError` code is needed here (the only new code this document adds beyond `SidecarError::code()`'s existing set) |
| `state() != Running` and state is `NotStarted`/`Starting` | `SIDECAR_NOT_READY` | Static string + the actual state name — another small new code; "still starting" is not itself an error condition `sidecar-core` models, it is the normal pre-`Running` window |
| `state() != Running` and state is `Crashed`/`Failed`/`Timeout` | the `SidecarError` code already recorded for that failure (via the same `reason` `state_changed` carried, §10.1) — reused, not reinvented | `SidecarError::to_string()` |
| `state() != Running` and state is `Stopping`/`Stopped` | `SIDECAR_STOPPED` | Static string — intentional shutdown, not a failure |
| `port()` returns `None` despite `Running` | `SIDECAR_PORT_UNAVAILABLE` | Static string — matches the existing `"sidecar is running but has no captured port"` case verbatim, just restructured |

This distinguishes exactly what P2 §11 already laid out and this document reconfirms
unchanged: sidecar-unavailable (`SIDECAR_*`, this document's scope) vs. provider error
(`TI_*`, `app/threat_intel/exceptions.py`, untouched) vs. invalid request
(`INVALID_COMMAND_PAYLOAD`, untouched) vs. database/application error (untouched) — all
four families already coexist in `error-model.md`'s one `{code,message}` convention; this
document adds exactly the `SIDECAR_BUSY`/`SIDECAR_NOT_READY`/`SIDECAR_STOPPED`/
`SIDECAR_PORT_UNAVAILABLE` members needed to make the *non-error*, "still starting"/"
intentionally stopped" cases distinguishable from genuine `SidecarError` failures, since
`sidecar-core`'s error enum was never meant to model "not yet started" (a normal state, not
a fault) in the first place.

---

## 12. Ordering / Duplicate / Stale-Event Strategy

### 12.1 Research finding this decision rests on (§30)

Tauri's own documentation (`Calling the Frontend from Rust`, `v2.tauri.app`) states
directly: <cite index="4-1">event listeners are called in the order they are registered, but if a listener is async and the event emitter sends multiple events in rapid succession, the listeners may process events out of order</cite>, and recommends its Channels API instead of the event system for
ordered, high-throughput delivery. **This means ordering cannot be assumed from the
transport alone** — the task brief's own §13 ("is ordering strictly guaranteed, best
effort, or eventually consistent") has a concrete, sourced answer: **best effort at the
Tauri transport layer.** Given `CRASH_POLL_INTERVAL` (1s) and the backoff schedule's own
minimum (1s, per `RestartPolicy`'s documented default), back-to-back emissions inside one
second are a real, not merely theoretical, possibility during a fast crash-loop — exactly
the scenario this document's staleness protection must hold up under.

Channels were evaluated and rejected for this use case: they solve high-throughput ordered
streaming, which sidecar lifecycle transitions are not (at most a handful of events per
crash episode) — adopting a second Tauri primitive for a low-frequency signal is exactly
the "no speculative dependencies" (§18/§33) the frozen P2 boundary already avoided for its
own restart-timer design.

### 12.2 Decision: payload-level monotonic `sequence`, not transport-level ordering

Given §12.1, the architecture does not rely on Tauri delivering events in emission order.
Instead:

- **Ordering guarantee: application-enforced, not transport-guaranteed.** The frontend
  projection tracks `lastAppliedSequence` (initialized to `0`) and applies an incoming
  event **only if** `event.sequence > lastAppliedSequence`; otherwise the event is dropped
  (§12.3/§12.4/§12.5 below all reduce to this one rule).
- **Duplicate events**: naturally idempotent under the same rule — a `sequence` value can
  only ever be applied once, since applying it moves `lastAppliedSequence` past it.
  Confirms the task brief §14's own question ("or whether the existing architecture already
  provides sufficient ordering") the direct way: it does not, so `sequence` is introduced
  specifically to provide it — not added without justification (§14 of the brief).
- **Stale events (task brief §15's own worked example — Lifecycle A crash+restart,
  Lifecycle B reaches `Running`, a late event from A arrives)**: because `sequence` is
  assigned at the single emitter (§10.4, one `AtomicU64` owned by the one `SidecarState`),
  and because that emitter is serialized by the same `Mutex<SidecarProcess>` that already
  serializes every real transition (§4 of the P2 doc, unchanged, §25 below), `sequence`
  values are assigned in true chronological order regardless of what order Tauri happens to
  *deliver* them in. A stale `CRASHED` event from episode A necessarily has a lower
  `sequence` than the already-applied `RUNNING` event from episode B — the drop rule above
  rejects it unconditionally. `RUNNING → CRASHED` regression by a stale event is therefore
  structurally impossible, not merely unlikely.
- **Shutdown race (task brief §16)**: `state.scheduler.cancel()` (already existing,
  confirmed in `lib.rs`'s `RunEvent::Exit` handler) runs before `shutdown()`'s own
  `state_changed{Stopping}`/`state_changed{Stopped}` emissions, under the same mutex — so
  even in the narrow window where a `restart_scheduled` event was already handed to Tauri
  before cancellation, the subsequent `Stopping`/`Stopped` event is assigned a strictly
  higher `sequence` and, once applied, makes any UI state derived from the stale
  `restart_scheduled` (a "Restarting..." label, §18) immediately superseded the moment
  `Stopping` is applied — no separate shutdown-specific mechanism is needed beyond the one
  general rule.
- **Exhaustion race (task brief §17)**: identical reasoning — `restart_exhausted` is the
  last event `handle_retry_eligible_failure`'s `Exhausted` arm ever emits for a given crash
  episode (confirmed: no further `schedule()` call exists on that path), so no
  `restart_scheduled`/`state_changed{Starting}` bearing a *higher* sequence can ever follow
  it for the same episode; the drop rule alone prevents "Restarting..." from displaying
  after "Failed" once `restart_exhausted` has been applied.

### 12.3 Why not `generation` alone, and why not neither

A pure per-restart-episode `generation` counter (without `sequence`) was considered and
rejected as the sole mechanism: two events within the *same* generation (e.g. `Starting`
then, moments later on the same launch, `Running`) still need relative ordering, which
`generation` alone cannot provide. `sequence` alone is sufficient and strictly simpler;
`generation` is retained anyway (§10.4) purely for human/UI legibility ("attempt 3 of 5"),
not for correctness — this is explicit so a future implementer does not mistakenly treat
`generation` as load-bearing for the ordering guarantee.

### 12.4 Late-mounting listener (§30 research finding, applied)

A frontend component that starts listening only after several transitions have already
occurred (e.g. a status indicator mounted well after app launch) would, under a pure
event-stream model, have no way to know current state without waiting for the next
transition. A research pattern surfaced for exactly this shape — a "snapshot + stream"
design where a late subscriber requests an authoritative current snapshot on connect and
then applies the stream from there, rather than reconstructing history from events alone —
maps directly here: <cite index="9-1">the frontend requests a snapshot containing the materialized... state... This provides an authoritative starting view without requiring the client to reconstruct history from incremental messages... If a client reconnects, the snapshot re-establishes the authoritative state and the stream resumes from there</cite>. **Applied to SOC-IQ**: a small,
new, read-only Tauri command — `get_sidecar_status`, returning the identical shape as
`state_changed`'s payload (§10.1) plus the current `sequence` — gives any newly-mounted
projection an authoritative starting point, after which it applies the event stream exactly
as §12.2 describes (any event with `sequence` already `<=` the snapshot's own `sequence` is
naturally dropped by the same rule). This is the one small addition this document makes
beyond the three events themselves; it is a command (frontend asks), not an event, per §23's
own commands/events distinction.

---

## 13. Frontend Projection Architecture

```ts
interface SidecarStatus {
  status: "Idle" | "Starting" | "Healthy" | "Restarting" | "Failed" | "Stopping" | "Stopped";
  backendState: LifecycleState;   // the raw §8.1 value, for callers that need it
  reason: { code: string; message: string } | null;
  attempt: number | null;         // from the most recent restart_scheduled/exhausted, else null
  maxAttempts: number | null;
  retrying: boolean;              // status === "Restarting"
  recoverable: boolean;           // false only once status === "Failed"
  terminal: boolean;              // status is "Failed" or "Stopped"
  sequence: number;                // last-applied sequence, for the caller's own diagnostics
}
```

This type, and the reducer that produces it from `get_sidecar_status` + the three events
(§12.4), is explicitly documented in its own module doc as **"a projection/cache/view-model
of backend truth — this module never decides whether the sidecar restarts, and never calls
any Tauri command that mutates sidecar state; it only observes."** This is not a stylistic
note — it is the direct implementation of §4/§18 of the task brief ("the frontend must never
become responsible for deciding whether the sidecar should restart") and of this document's
own Non-Goals (§6): no second lifecycle authority, ever, by construction of what this module
is permitted to import (no access to `invoke("get_sidecar_origin")`'s sibling command
surface beyond the two read-only calls this document defines).

The reducer's transition table is exactly §8.1 plus the `restart_scheduled`/
`restart_exhausted` synthesis already described — restated here as the literal decision
function, not left implicit:

1. On `sidecar:state_changed`: set `backendState`/`reason` from the payload; map through
   §8.1's table. A `Crashed`/`Failed`/`Timeout` value defaults to `Failed` **unless** a
   `restart_scheduled` for the *current* (higher-or-equal `generation`) episode has already
   been applied and no terminal (`restart_exhausted`, or a newer `state_changed`) event has
   superseded it — in which case it is `Restarting`.
2. On `sidecar:restart_scheduled`: set `attempt`/`maxAttempts`/`retrying = true`; force
   `status = "Restarting"` regardless of what the last `state_changed` said (this event is,
   by construction, always chronologically after the `Crashed`/`Failed`/`Timeout` transition
   it responds to, per §12.2).
3. On `sidecar:restart_exhausted`: set `status = "Failed"`, `retrying = false`,
   `recoverable = false`, `terminal = true`; `reason` becomes `{code: "SIDECAR_RESTART_EXHAUSTED", message}`.
4. Every rule above is gated by the §12.2 `sequence` drop rule *before* any of the above
   runs — an event that fails the sequence check never reaches this table at all.

---

## 14. UI Ownership

Per §6/§19/§33, no navigation shell exists to assign ownership *within* today. What this
document specifies instead is the **layer** the projection belongs to once one exists, so a
future phase does not have to re-derive this: **application-level state, owned alongside
(not inside) the existing `eventSourceManager.ts`-style singleton pattern** —
i.e., a new `frontend/src/shared/sidecar/` module (mirroring `shared/events/`'s own
shape: a singleton reducer + `useSidecarStatus()` hook), not a page/controller-local
`useState`. This directly follows the same reasoning P2 §4 already applied one layer down
(one owner, no page-local restart logic) and the task brief §19's own instruction ("do not
put lifecycle logic directly into individual pages — pages should consume application-level
status"). When Phase 4G's navigation shell lands, its status bar/connection-indicator
component becomes a *consumer* of `useSidecarStatus()`, exactly as a future feature's
`useEventStream("analysis.progress", ...)` call is already a consumer of
`eventSourceManager.ts` today — same pattern, parallel module, no shared internal state
between the two (§7).

---

## 15. UI Behavior Matrix (contract only, no visual design — §20/§33)

| Backend condition | Frontend `status` | User-visible behavior (contract, not styling) |
|---|---|---|
| `NotStarted` | `Idle` | No sidecar-dependent UI shown as unavailable yet; too early to say anything meaningful |
| `Starting` | `Starting` | Indicate "starting up," non-error affordance |
| `Running` | `Healthy` | No lifecycle-specific UI; sidecar-dependent features enabled |
| `Crashed`/`Failed`/`Timeout`, restart pending | `Restarting` | Indicate "reconnecting" with `attempt`/`maxAttempts` available to display; sidecar-dependent features disabled but framed as transient |
| `Crashed`/`Failed`/`Timeout`, exhausted | `Failed` | Persistent, user-visible "sidecar unavailable" affordance; sidecar-dependent features disabled and framed as needing user action (§16's notification policy) |
| `Stopping` | `Stopping` | Brief, low-emphasis "shutting down" — typically only visible during app exit, so no persistent UI is warranted |
| `Stopped` | `Stopped` | Same as `Failed` in effect (sidecar-dependent features unavailable) but not framed as an error — this was intentional |

## 16. Notifications

**Policy: state-level persistent status, not per-event notifications, with exactly one
exception.** Repeated restart attempts (task brief §21's own example) must **not** produce
one toast per attempt — the `Restarting` status with a live `attempt`/`maxAttempts` counter
(§13) is itself the ongoing notification; a five-toast burst during a crash loop is
precisely the spam §21 warns against. The one event that **does** warrant a one-shot,
explicit notification (toast or banner, deferred to the eventual UI phase to choose which)
is the `Failed` transition itself (i.e., `restart_exhausted`, or an immediate,
non-retry-eligible terminal failure) — this is the one moment the user needs to be told
something requires their attention, exactly once, not repeatedly. A persistent log entry
(mirroring P2 §13's already-defined Rust-side `eprintln!` lifecycle log points) is
appropriate for every transition, since it costs nothing and aids diagnosis — this is a
logging decision, not a UI-notification one, and does not conflict with the "no
notification spam" policy above.

## 17. Existing UI Integration Points

None exist today (§2, §7, §14) beyond the pattern this document defines for a future
consumer to plug into. This is stated explicitly rather than left implicit, per the task
brief's own §22 instruction to "document integration points only" — there is nothing to
document beyond "there is currently nothing here."

---

## 18. API / Event Boundary

- **Commands** (frontend asks): `get_sidecar_origin` (existing, error contract updated,
  §11) and `get_sidecar_status` (new, §12.4) — both read-only, neither mutates anything.
- **Events** (backend tells): the three in §9.3, backend-originated only, matching §23 of
  the task brief's own instruction ("backend-originated events, not frontend polling")
  directly — this is a restatement of P2 §7's own already-decided "Rust retries
  automatically... frontend polling remains the correct mechanism to *observe*... not to
  *drive*" principle, applied one layer further out to the frontend's own relationship to
  the event stream.
- No command the frontend can call ever mutates sidecar lifecycle state (no
  "request restart" command is introduced — one is not needed by anything in this
  document's scope, and per §4/§6 the frontend has, and should continue to have, no
  lifecycle authority at all).

## 19. Polling Question

**Audited and rejected**, per §24 of the task brief. The only polling-shaped thing in this
architecture is `get_sidecar_status` (§12.4), and it is explicitly **not** a repeating
timer — it is called exactly once, when a projection consumer first mounts (or, mirroring
`eventSourceManager.ts`'s own "first subscriber" pattern, once per app session the first
time anything subscribes), to establish the starting snapshot before the event stream takes
over. No `setInterval`/timer-driven re-poll of `get_sidecar_origin` or `get_sidecar_status`
is introduced anywhere — the three events (§9.3) are the only ongoing source of updates,
matching `eventSourceManager.ts`'s own existing "connect() is not a timer-driven retry
loop... only retries when a new subscriber actually shows up" precedent this document
follows deliberately, not coincidentally.

## 20. Event Source Ownership

**Exactly one authoritative emitter for each of the three events, all inside
`src-tauri/src/lib.rs`** — the same single file §4 of the P2 doc already established as the
one lifecycle owner, unchanged by this document:

| Event | Single call site |
|---|---|
| `sidecar:state_changed` | Every existing point `lib.rs` already drives a `Lifecycle` transition: the `setup` closure's `process.start()`, `run_crash_poll_loop`'s `poll_for_crash()` branch, `attempt_restart`'s `reset()`/`start()` branches, `RunEvent::Exit`'s `process.shutdown()` |
| `sidecar:restart_scheduled` | `handle_retry_eligible_failure`'s `Retry` arm, exactly once |
| `sidecar:restart_exhausted` | `handle_retry_eligible_failure`'s `Exhausted` arm, exactly once |

No `.emit(` call is proposed anywhere in `sidecar-core`, `sidecar.rs`, or
`restart_scheduler.rs` — those crates/modules remain exactly as framework-independent as
their own module docs already require (`sidecar-core`: "no real I/O"; `restart_scheduler.rs`:
depends on `sidecar-core`, never emits itself). The emission calls are a thin adapter layer
added at the existing call sites in `lib.rs` only, per the task brief §25's own instruction
to prefer "a clearly defined boundary/adapter" over scattering `.emit()` through unrelated
paths.

## 21. Test Architecture (design only — §26)

| Area | Test shape |
|---|---|
| Event emission per transition | For each of the 8 `LifecycleState` transitions already covered by `sidecar-core`'s 49+ existing tests, a corresponding `src-tauri`-level test (using a fake `AppHandle`/emit-capturing harness, mirroring `restart_scheduler.rs`'s own existing `DelayRunner` fake-injection pattern) asserts exactly one `state_changed` with the correct `state`/`previous_state`/`reason` |
| `restart_scheduled`/`restart_exhausted` | Exercise `handle_retry_eligible_failure`'s two arms directly (already unit-testable in isolation, per its existing signature) and assert the corresponding event's payload matches `RestartDecision`'s own fields exactly |
| Sequence monotonicity | A test that drives several transitions in sequence and asserts every emitted `sequence` is strictly increasing, with no gaps unaccounted for by intentionally-skipped emissions |
| Duplicate delivery | Feed the frontend reducer (§13) the same event object twice; assert the second application is a no-op (state unchanged, `lastAppliedSequence` unchanged) |
| Stale events | Feed the reducer an out-of-order sequence (a lower-`sequence` event arriving after a higher one was already applied); assert it is dropped and does not regress `status` |
| Shutdown race | Reproduce the existing `sidecar-core`/`src-tauri` race-B-style test (already named `crash_does_not_auto_restart`-style in the existing suite, per the P2 doc's own §15) at the event layer: assert no `state_changed{Starting}`/`restart_scheduled` is ever emitted after a `state_changed{Stopping}` for the same shutdown |
| Exhaustion | Assert `restart_exhausted` is emitted exactly once per crash-loop window, at attempt `max_attempts + 1`'s decision point, never earlier/later — mirrors the existing `RestartTracker` unit tests' own assertion shape |
| Frontend projection | Table-driven tests over §13's reducer covering every row of §8.1/§15's matrices |
| Error mapping | One test per row of §11's table, asserting `get_sidecar_origin`'s `Err` shape matches |

## 22. Backward Compatibility

- `get_sidecar_origin`'s **success** path (`Ok(String)`) is completely unchanged — only its
  `Err` variant's shape changes (`String` → `{code, message}`). Its one current caller
  (`client.ts`'s `getSidecarOrigin()`) already only inspects the error to build a
  `SidecarNotConnectedError` message string — extending that constructor to prefer
  structured `code`/`message` when present, and fall back to `String(error)` otherwise,
  keeps every existing call site (`eventSourceManager.ts`'s `connect()`,
  `runCommand()`) working unmodified, since neither currently branches on the error's
  internal shape at all (confirmed by direct read, §2).
- No existing SSE event name, envelope field, or `EventName` union member changes.
- No existing Tauri command signature is removed; `get_sidecar_status` is additive.
- `eventSourceManager.ts`'s own `EventStreamStatus` type and behavior are completely
  untouched (§7) — this document adds a parallel, independent signal, not a replacement.

## 23. Security/Privacy Audit (§28)

Reusing `SidecarError`'s existing `Display` implementations for every `reason.message`
(§10.1) was specifically checked against this document's own forbidden-field list: every
variant in `sidecar-core/src/error.rs` (reviewed in full, §2) already reports only a
category, a duration, an exit code, or a short caller-supplied `String` (e.g.
`HandshakeFailure { detail }`) — none construct their message from a raw OS error struct,
an environment variable, or the launch command line. `SidecarLaunchConfig`'s working
directory and the sidecar's actual launch arguments are **never** placed in any event
payload defined by this document (§10.1's explicit forbidden-fields list). No API
keys/tokens are reachable from this layer at all — they live in `app/settings/`, several
layers above where `SidecarState` operates, unchanged from P2 §13's own identical finding.

## 24. Performance Audit (§29)

- The `CRASH_POLL_INTERVAL` 1-second loop (existing, unchanged by this document) does not
  itself emit anything — it only calls `poll_for_crash()`, which returns `None` on every
  tick where nothing happened. An event is only ever emitted on an actual transition or
  policy decision, never per-poll-tick — so an idle, healthy sidecar produces zero ongoing
  event traffic, and a crash-looping sidecar produces at most one `state_changed` +
  one `restart_scheduled` per attempt (bounded by `max_attempts`, §7 of the P2 doc,
  unchanged) — never unbounded.
- `sequence`'s `AtomicU64` increment is a single non-blocking atomic operation, performed on
  whichever thread already holds `SidecarState`'s existing mutex/is already about to call
  `.emit()` — no new lock, no new thread, no work added to the Tauri lifecycle thread beyond
  the `.emit()` call itself (which Tauri's own event system is designed to make cheap and
  non-blocking for the emitting side, per §30's research).
- `get_sidecar_status` (§12.4) is a single synchronous, `try_lock`-guarded read, identical
  in cost/shape to the existing `get_sidecar_origin` — no new expensive work.

---

## 25. Web Research and Adaptation Decisions (§30)

| Source | Observed | Applied to SOC-IQ | Rejected |
|---|---|---|---|
| Tauri `Calling the Frontend from Rust` (v2.tauri.app, official docs) | <cite index="4-1">Event listeners are called in the order they are registered, but if a listener is async and the event emitter sends multiple events in rapid succession, the listeners may process events out of order. For ordered, high-throughput data delivery, consider using Channels instead of the event system.</cite> | Directly drove §12's core decision: ordering is not assumed from the transport; a payload-level monotonic `sequence` is introduced specifically because this citation shows the transport alone does not guarantee it. | Channels — evaluated and rejected (§12.1) as solving a higher-throughput problem than this low-frequency signal has; adopting a second Tauri primitive would be an unjustified new dependency surface (§18/§33). |
| Tauri `event` JS API reference (v2.tauri.app) | <cite index="2-1">Note that removing the listener is required if your listener goes out of scope e.g. the component is unmounted.</cite> | Confirms the frontend projection module (§13/§14) must call its `unlisten` in a cleanup path, mirroring `eventSourceManager.ts`'s own existing `subscribe()`/unsubscribe symmetry (§2) — no new pattern needed, the codebase already has the right precedent. | N/A |
| "Snapshot-Stream Runtime State Model" (research-harness architecture writeup, arXiv) | <cite index="9-1">the frontend requests a snapshot containing the materialized topic state... This provides an authoritative starting view without requiring the client to reconstruct history from incremental messages... the snapshot re-establishes the authoritative state and the stream resumes from there</cite> | Directly justified `get_sidecar_status` (§12.4) as the answer to the late-mounting-listener problem, instead of either (a) requiring every consumer to have been mounted since app launch, or (b) building an event-replay/history buffer on the Rust side. | A Rust-side event-history ring buffer (so a late listener could "catch up" by replay) — rejected as unnecessary complexity: a single current-state snapshot is sufficient because the projection (§13) only ever needs *current* status, never the full transition history, and this avoids adding any new persistent state to `SidecarState` beyond the one `sequence` counter already introduced. |
| P2's own restart-timer research (`RestartToken`/single-flight pattern, `sidecar-core/src/restart.rs`, this codebase's own existing code, re-read this session rather than external) | The codebase already solves an analogous "reject a stale/duplicate callback" problem internally, via a consume-once token compared before acting. | Confirmed the *shape* of this document's `sequence`-based staleness check is consistent with a pattern this codebase already trusts for the identical class of problem one layer down — not copied verbatim (that mechanism is Rust-internal single-flight bookkeeping; this document's `sequence` is a wire-format field for a different, frontend-facing consumer), but validated as the right kind of solution for this codebase specifically, not merely "a good idea in general." | N/A |

No source's design was adopted wholesale; each contributed one specific, cited, applicable
finding, consistent with §30's own "do not blindly copy another project's architecture"
instruction.

---

## 26. Alternatives Rejected

- **A fourth event, `sidecar:recovered`** — rejected twice now (P2 §10, reaffirmed here
  §9.3) for the same reason: fully derivable from the existing sequence, no new information.
- **Reusing/extending `EventStreamStatus`/`eventSourceManager.ts` for sidecar lifecycle**
  (§7) — rejected: conflates two independently-failing signals into one enum, the exact
  "two lifecycle authorities" shape the task brief's hard-stop conditions name.
- **A `RESTARTING` core-FSM state** — rejected (P2 §5, reaffirmed §8): no behavioral gain,
  would touch a transition table 49+ tests already guard, for information the policy layer
  already carries separately.
- **Tauri Channels instead of events** (§12.1/§25) — rejected: solves a higher-throughput
  problem than this signal has; an unjustified new primitive for this volume of traffic.
- **A Rust-side event-history/replay buffer** (§25) — rejected in favor of a single current
  snapshot command; the projection only ever needs current status, never full history.
- **`generation` alone as the ordering/staleness mechanism** (§12.3) — rejected: cannot
  order two events within the same generation; `sequence` is necessary regardless, at which
  point `generation` is redundant for correctness (retained only as a legibility aid).
- **Frontend timer-driven polling of `get_sidecar_origin`/`get_sidecar_status`** (§19/§24 of
  the task brief) — rejected: the three events are a complete, sufficient, backend-driven
  source of updates; polling would duplicate that for no benefit and reintroduce exactly the
  pattern `eventSourceManager.ts` already avoids today.
- **Building the Phase 4G navigation shell / a status-bar component now** — rejected as
  scope creep (§6/§33): no shell exists to build against yet, and doing so here would be
  exactly the "redesign the frontend" the task brief's own scope-discipline section forbids.

---

## 27. Implementation Scope for Part 2 (not implemented by this document)

**Backend changes:**
1. `sidecar-core`: no changes (confirmed sufficient as-is, §8/§9 — `SidecarError`/
   `LifecycleState` are reused verbatim).
2. `src-tauri/src/lib.rs`: add the `sequence: AtomicU64` and `generation: AtomicU32` fields
   to `SidecarState`; add `.emit("sidecar:state_changed", ...)` /
   `.emit("sidecar:restart_scheduled", ...)` / `.emit("sidecar:restart_exhausted", ...)`
   calls at exactly the call sites in §20's table; change `get_sidecar_origin`'s `Err` type
   per §11's table; add the new `get_sidecar_status` command (§12.4).
3. No change to `src-tauri/src/sidecar.rs` or `restart_scheduler.rs`'s own internal logic —
   only `lib.rs` gains new call-site code, per §20's single-adapter decision.

**Frontend changes:**
4. `frontend/src/shared/api/client.ts`: extend `SidecarNotConnectedError` to carry
   `code`/`message` when present (§22 — additive, backward compatible).
5. New `frontend/src/shared/sidecar/` module (mirroring `shared/events/`'s shape, §14):
   the `SidecarStatus` type (§13), the reducer, `get_sidecar_status` call wrapper, three
   `listen("sidecar:*", ...)` registrations, and a `useSidecarStatus()` hook.

**Shared contract changes:**
6. A new `docs/contracts/sidecar-event-model.md` (or an added section in the existing
   `event-model.md`, if a future implementer judges that a better fit) documenting exactly
   §9–§11 of this document as the wire contract, mirroring how `event-model.md`/
   `error-model.md` already document the SSE/command contracts.

**Tests:**
7. Per §21, at both the `src-tauri` level (emission correctness, ordering, races) and a new
   frontend test suite for the reducer (staleness, duplicates, the full §8.1/§15 matrix).

**Documentation:**
8. A Part 2 implementation report and a Part 3 final audit, following the same
   two-checkpoint pattern P2 itself used (architecture → implementation → audit/freeze).

None of the above is implemented by this document.

---

## 28. Required Audit Findings (§34)

| Finding | Classification |
|---|---|
| Zero `.emit(`/Tauri-event call sites exist anywhere in the repo; this is the entire gap P3 closes | INFORMATIONAL (confirms mission scope, not a defect) |
| `get_sidecar_origin`'s `Err` is still an unstructured string, exactly as P2's own Final Audit (I1) already disclosed | INFORMATIONAL (already-disclosed, already-frozen deferral) |
| No frontend application shell, global store, or any status/notification UI exists yet (`App.tsx`/`router.tsx` are documented placeholders; `shared/state/`, `shared/components/`, `features/` are empty) | **MEDIUM** — materially narrows what "UI integration points" (§17/§22) can mean this phase; addressed by defining the ownership *pattern* (§14) rather than assuming an integration target that does not exist |
| Tauri's own documentation states event delivery order is not guaranteed under rapid/async listener conditions | **HIGH** — this is exactly the kind of ambiguity the task brief's hard-stop conditions flag ("event ordering cannot be guaranteed... stale events cannot be safely rejected"); resolved architecturally via the payload-level `sequence` mechanism (§12), not left unresolved |
| The task brief's own file inventory (`src-tauri/src/state.rs`, `src-tauri/src/error.rs`) does not match the actual repository layout (`sidecar-core/src/{state,error}.rs` instead) | INFORMATIONAL — noted, both files were located and read under their real paths; no ambiguity resulted |
| No genuine P2 defect was found; the only gap is the already-documented, already-frozen deferral | INFORMATIONAL |
| Current architecture strengths | Single lifecycle owner already structurally enforced by one `Mutex`; all six P2 races already closed; `SidecarError::code()` already exists and is directly reusable, avoiding a second error vocabulary |
| Current architecture gaps | Exactly the one this document closes — no frontend-observable signal of any of the already-correct backend behavior |
| Rejected alternatives | §26, in full |

No unresolved architectural ambiguity was hidden — the HIGH item above (event ordering) is
the one genuine open technical risk this document identified, and it is the one this
document spends the most design effort resolving (§12), not deferred further.

---

## 29. Final Classification

**PASS / COMPLETE.**

The P3 architecture is internally consistent: one canonical event plus two justified
synthesized events, one monotonic sequence field that makes ordering/duplicate/staleness
correctness independent of Tauri's own (documented, not guaranteed) delivery order, one
snapshot command for late listeners, one extended error contract reusing the existing
`SidecarError` vocabulary, and one explicitly-named "projection, not authority" frontend
module. Every decision traces to source actually read this session (backend) or to a cited,
applicable piece of external research (ordering, snapshot pattern). No hard-stop condition
from the task brief was triggered: the frontend's SSE state does not conflict with this
design (§7 keeps them deliberately separate), P2 lifecycle ownership is unambiguous
(§4/§20), event ordering *can* be made safe (§12, was the one real risk, now resolved), the
error contract extends rather than breaks existing consumers (§22), and nothing here
requires reopening frozen P2 code.

---

## 30. Files Created/Changed

```text
Created:
  docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md   (this file)

Changed: none.
Production source changes: 0.
```

No file under `app/`, `src-tauri/`, `sidecar-core/`, or `frontend/` was modified this
session. Every source file cited above (§2 and throughout) was read for inspection only.

## 31. Git

```text
$ git status
fatal: not a git repository (or any of the parent directories): .git
```

No `.git` directory exists in the extracted archive — consistent with every prior phase
document in this project (P2's own architecture doc, §20, records the identical finding).
No commit was made or attempted; none is fabricated.

## 32. P1/P2 Protection

Phase 4E-P1 and every Phase 4E-P2 checkpoint (Architecture, 2A, 2B-1 through 2B-5) were
read only, for the inspection this document required, and never modified. §30 confirms zero
production source changes. No genuine P2 defect was discovered that would warrant reopening
it (§28); the one deferred item P2 itself flagged (the frontend event/error contract) is
exactly what this document designs, not a defect being patched.

---

## 33. Final Recommendation

Proceed to **Phase 4E-P3 Part 2 — Sidecar Lifecycle Event Implementation**, scoped exactly
per §27 above: the `.emit()` adapter code and `sequence`/`generation` counters in
`src-tauri/src/lib.rs`, the `get_sidecar_status` command, the extended
`SidecarNotConnectedError`, and the new `frontend/src/shared/sidecar/` projection module —
in that order, backend before frontend, so the frontend implementation has a real event
stream to test against rather than a mocked one. Building the Phase 4G navigation shell
this document has no visual-integration target for is correctly a separate, later phase's
scope, not a blocker for Part 2.

```text
Next target:
Phase 4E-P3 Part 2 — Sidecar Lifecycle Event Implementation
```
