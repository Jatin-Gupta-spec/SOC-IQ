# Phase 4E-P3, Part 2A — Event Contract & Backend Event Adapter Foundation

**Status:** Implementation checkpoint. Builds on, and treats as frozen,
`docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md` (the P3
architecture) and every P1/P2 checkpoint it in turn treats as frozen.

---

## 1. Scope

Implements exactly the checkpoint 1-of-3 scope requested:

- The canonical lifecycle event `sidecar:state_changed`.
- Its backend payload contract (architecture doc §10.1).
- One narrow application-boundary event adapter (`src-tauri/src/events.rs`).
- Real emission wired to the four existing real lifecycle call sites in
  `src-tauri/src/lib.rs`.
- Focused tests for what is safely testable at this checkpoint (no Tauri
  runtime harness required).

**Not implemented** (explicitly out of scope, per the architecture doc
§9.3/§27 and the task brief itself): `sidecar:restart_scheduled`,
`sidecar:restart_exhausted`, `get_sidecar_status`, `SidecarStatus`, any
frontend code, full `sequence` dedup/reconciliation/ordering semantics.

## 2. P3 Part 1 Architecture Used

- §8/§8.1 — the frozen 8-state `LifecycleState` enum, used unchanged; no
  new state introduced.
- §9.3 — Model C (hybrid), this checkpoint implements the one canonical
  event only.
- §10.1 — the exact `state_changed` payload shape (`state`,
  `previous_state`, `reason`, `sequence`, `generation`, `timestamp`).
  This checkpoint follows the architecture document's own field
  contract; the task brief's own illustrative field list (which
  additionally names `attempt`/`max_attempts`/`error_code` at the
  top level) describes fields that architecture doc §9.3/§10.2/§10.3
  assign to `restart_scheduled`/`restart_exhausted` instead — those two
  events, and therefore those fields, are out of scope for Part 2A. No
  field was invented beyond §10.1's list.
- §10.4 — `sequence`/`generation` semantics: implemented as the
  "minimal foundation" the task brief §14 asked for (a real, monotonic,
  process-lifetime counter), not the full frontend drop/reconciliation
  rule (§12.2), which has no consumer yet (frontend is entirely out of
  scope this checkpoint).
- §20 — one adapter, one file, one call site enumeration; followed
  exactly (`events.rs`, called from `lib.rs`'s four real transition
  sites and nowhere else).
- §23 — the forbidden-fields list, re-verified against
  `sidecar-core/src/error.rs`'s current `Display` impls this session
  (unchanged since the architecture doc's own review — the file was
  read, not assumed).

## 3. Existing Lifecycle Authority

Unchanged. `sidecar-core::{Lifecycle, LifecycleState, Supervisor}` remain
the sole owner of lifecycle *state*; `SidecarProcess`
(`src-tauri/src/sidecar.rs`) remains the sole process adapter;
`RestartPolicy`/`RestartTracker`/`RestartScheduler`/`StabilityScheduler`
remain the sole restart/stability policy layer. None of these files were
modified. The event adapter added this checkpoint only *observes*
outcomes these already-frozen components produce — see §5 below for the
exact mechanism.

## 4. Event Adapter Ownership

One new file, `src-tauri/src/events.rs`:

- `EventSequencer` — the one `sequence`/`generation` counter pair,
  owned as a new field (`events`) on the existing single `SidecarState`
  struct (no second owner).
- `StateChangedPayload` / `StateChangeReason` — the payload contract.
- `build_state_changed_payload` — pure payload construction (testable
  without a Tauri runtime).
- `emit_state_changed` — the one adapter entry point. Every call site
  in `lib.rs` goes through this function; nothing calls
  `AppHandle::emit` directly anywhere else in the crate, and
  `sidecar-core` has zero Tauri dependency (verified: its `Cargo.toml`
  lists only `thiserror`; also asserted by this checkpoint's own Test
  5, §9 below).

## 5. `sidecar:state_changed`

Event name: `sidecar:state_changed` (the `EVENT_STATE_CHANGED` constant).
No per-transition event names were introduced.

### 5.1 A real, load-bearing implementation constraint (read before extending this)

`SidecarProcess::start()` and `SidecarProcess::shutdown()`
(`src-tauri/src/sidecar.rs`, frozen — not modified this checkpoint, per
the task brief's explicit "no change to `sidecar.rs`" instruction) are
each **synchronous, blocking calls that perform two real FSM
transitions internally** before returning control to the caller:

- `start()`: `NotStarted -> Starting` (its very first action, via
  `Supervisor::request_start()`), then, after spawn/handshake/health-poll
  completes, `Starting -> Running` **or** `Starting -> Failed` **or**
  `Starting -> Timeout`.
- `shutdown()`: `Running -> Stopping` (via `Supervisor::request_shutdown()`),
  then, after the kill/wait loop completes, `Stopping -> Stopped` **or**
  `Stopping -> Failed`.

`sidecar.rs` exposes no intermediate hook between these two internal
transitions, and this checkpoint does not add one (that would be a
change to a frozen file, out of scope for Part 2A). Two options were
available:

1. Emit only one event per call, covering the net
   `NotStarted -> Running` / `Running -> Stopped` change directly.
   **Rejected**: this is not a real edge in
   `LifecycleState::can_transition_to`'s table
   (`sidecar-core/src/state.rs`) — it would fabricate a transition that
   never happened, which architecture doc §12/§13 and the task brief's
   own rules ("do not invent transitions") both forbid.
2. Read `process.state()` immediately before and immediately after the
   call, and emit **two** `state_changed` events back-to-back once the
   call returns: `previous -> Starting` (or `Running -> Stopping`),
   then `Starting -> <resolved state>` (or `Stopping -> <resolved
   state>`). Both events are constructed from state the frozen
   `sidecar-core` transition table *guarantees* was actually entered
   given the documented precondition of each call site (e.g. `start()`
   is only ever called when `process.state() == NotStarted`, and
   `NotStarted -> Starting` is the only transition `request_start()`
   can produce from `NotStarted`) — so no transition is invented, only
   reconstructed from already-authoritative, already-frozen behavior.
   **Selected.**

The one accepted cost of option 2: both events are emitted together,
immediately after the blocking call returns, rather than the first one
at the literal instant `Starting`/`Stopping` was entered. `timestamp`
therefore reflects emission time, not the literal transition instant,
for the reconstructed first event of each pair. This is documented here
explicitly per the task brief's own "if you discover a genuine defect,
stop and report" instruction — this is not a defect in frozen code, it
is an inherent consequence of `sidecar.rs`'s synchronous design that
Part 2A's own scope (no change to `sidecar.rs`) makes unavoidable. A
future checkpoint that wants literal-instant `Starting`/`Stopping`
timestamps would need to add an intermediate hook to `sidecar.rs`
itself — a decision for whoever owns that file's next revision, not
made unilaterally here.

`poll_for_crash()` (`Running -> Crashed`) and `reset()`
(`<terminal> -> NotStarted`) are each a single real transition with no
such internal splitting, and are each reported as exactly one event.

### 5.2 Call sites (architecture doc §20's table, as actually implemented)

| Site in `lib.rs` | Transition(s) emitted |
|---|---|
| `run()`'s `setup` closure (initial launch) | `NotStarted -> Starting`, then `Starting -> Running` / `Starting -> Failed` / `Starting -> Timeout` |
| `run_crash_poll_loop` | `Running -> Crashed` (only place `previous` is asserted to be `Running` by the loop's own preceding guard) |
| `attempt_restart` (`Retry` path) | `<terminal> -> NotStarted` (from `reset()`, standalone), then `NotStarted -> Starting`, then `Starting -> Running` / `Starting -> Failed` / `Starting -> Timeout` |
| `RunEvent::Exit` handler (intentional shutdown) | `Running -> Stopping`, then `Stopping -> Stopped` / `Stopping -> Failed` — **only** if `shutdown()` was not a no-op (`previous != current` guards this; a no-op `ShutdownOutcome::NotRunning` emits nothing, since nothing real transitioned) |

No fake timer or polling-based event generator was created; every
emission above is a direct consequence of an already-existing,
already-frozen call already present in `lib.rs`/`sidecar.rs`.

## 6. Payload Contract (as implemented)

```rust
pub struct StateChangedPayload {
    pub state: String,            // "NOT_STARTED" | "STARTING" | "RUNNING" | ...
    pub previous_state: String,   // same union
    pub reason: Option<StateChangeReason>,  // { code, message }, present only on a failure transition
    pub sequence: u64,
    pub generation: u32,
    pub timestamp: String,        // RFC 3339 UTC, second precision
}
```

`state`/`previous_state` reuse `LifecycleState`'s own `Display` impl
verbatim (already exactly the required upper-snake-case shape — no
duplicate mapping table). `reason.code` reuses `SidecarError::code()`
verbatim. `reason.message` reuses `SidecarError::to_string()` — safe
as-is per §23's forbidden-field audit (re-verified this session against
the actual current `error.rs`; every variant's message is a category, a
duration, an exit code, or a short caller string, never a raw OS error,
PID, command line, or environment variable).

`timestamp` uses a small, dependency-free RFC 3339 formatter
(`format_rfc3339`, Howard Hinnant's `civil_from_days` algorithm against
`std::time::SystemTime` alone) rather than adding a `chrono`/`time`
crate dependency — consistent with this codebase's existing "no
speculative dependency" discipline (`src-tauri/Cargo.toml`'s own comment
re: no async runtime until an actual caller needs one).

## 7. Lifecycle Integration

Every emission happens strictly after the real transition it reports
has already occurred and been confirmed via `process.state()` — never
before, per architecture doc §4/§9.1 ("the event system is an observer
of lifecycle truth, not a lifecycle authority"). `emit_state_changed`
itself performs no lifecycle mutation, makes no restart decision, and
is never on the path that decides *whether* the sidecar restarts
(`handle_retry_eligible_failure`/`RestartTracker`/`RestartScheduler`
are completely unchanged and unaware this module exists).

`poll_for_crash()` itself was **not** modified — it remains a detector
only, called once per poll tick from the existing loop; the loop still
only emits when an actual crash was detected (`Some(Err(err))`), never
on a poll tick that found nothing (task brief §15: "must not emit
`state_changed` on every polling iteration" — satisfied, since the
`None` case never reaches `emit_state_changed` at all).

## 8. Tauri Boundary

`Cargo.toml` pins `tauri = { version = "2", features = [] }`; the
installed/resolved major version (confirmed by the one partial
dependency-resolution pass that completed before the environment
limitation in §12 below, and by direct inspection of `Cargo.lock`) is
`tauri v2.11.5`. The `Emitter` trait (`tauri::Emitter`, providing
`AppHandle::emit`) is the correct v2 API for this — confirmed against
Tauri's own current documentation (`docs.rs/tauri/latest/tauri/trait.Emitter.html`,
`v2.tauri.app`'s "Calling the Frontend from Rust" guide) this session,
not assumed or copied from a v1 example. `events.rs` is the only file
in the crate with a `use tauri::Emitter;` import.

## 9. Sequence Boundary (deferred Part 2B work)

Implemented: one `AtomicU64` (`sequence`) incremented on every emission
from the one `EventSequencer` owned by `SidecarState`; strictly
increasing, never reset, never reused; one `AtomicU32` (`generation`)
incremented exactly once per real `NotStarted -> Starting` transition.

**Not implemented** (Part 2B, architecture doc §12.2): the
frontend-side `lastAppliedSequence`/drop-stale-events rule. There is no
frontend consumer this checkpoint, so there is nothing to apply that
rule to yet; implementing it now would be building ahead of a
non-existent caller, which the task brief's own §14 explicitly warns
against ("do not prematurely implement Part 2B").

## 10. Duplicate Protection Boundary (deferred Part 2B work)

Not implemented, per the same reasoning as §9. `poll_for_crash()`'s own
detector behavior is unchanged (§7) — the one structural protection
this checkpoint does provide (no emission on a no-op poll tick) was
already true of the frozen code and is preserved, not newly added.

## 11. Concurrency/Locking Considerations

No new lock was introduced. Every call site already held
`state.process`'s existing `Mutex<SidecarProcess>` for exactly the
duration needed to read `process.state()`; every `emit_state_changed`
call happens **after** `drop(process)`, matching architecture doc §19's
"lock → perform/read authoritative transition → capture event data →
unlock → emit event" pattern exactly. `EventSequencer`'s two atomics
need no separate lock (lock-free, `AtomicU64`/`AtomicU32` with
`Ordering::SeqCst`) and are never touched while `state.process` is
held.

## 12. Shutdown Interaction

`RunEvent::Exit`'s existing cancellation discipline
(`state.scheduler.cancel()`, `state.stability.cancel()`, both already
present and unchanged) still runs first, exactly as before. The new
code only reads `process.state()` before/after the existing
`process.shutdown()` call and emits accordingly; it does not initiate,
prevent, or otherwise influence shutdown (architecture doc §18's own
constraint, re-confirmed by inspection of the diff: `shutdown()`'s
call site and return value are untouched, only observed).

## 13. Tests

All five requested test categories are implemented in
`src-tauri/src/events.rs`'s `#[cfg(test)] mod tests`, using only the
pure `build_state_changed_payload` function (no `AppHandle`/webview
harness needed — Tauri v2's `tauri::test` mock-app utilities were not
required for this checkpoint's scope):

1. **Payload construction** — `payload_reflects_a_clean_transition_with_no_reason`,
   `payload_carries_reason_from_a_sidecar_error`.
2. **State event name** — `canonical_event_name_is_exact`.
3. **Transition mapping** — `representative_real_transitions_map_correctly`
   (also asserts each transition is real via
   `LifecycleState::can_transition_to`), plus
   `sequence_is_strictly_increasing_across_emissions` and
   `generation_bumps_only_on_not_started_to_starting`.
4. **Forbidden data** — `payload_never_exposes_forbidden_internals`
   (serializes a payload and asserts none of the forbidden-field
   keywords appear).
5. **Framework boundary** — `sidecar_core_cargo_toml_has_no_tauri_dependency`
   (reads `sidecar-core/Cargo.toml` via `include_str!` and asserts no
   `tauri` mention).

Plus one dependency-free formatter test,
`timestamp_is_well_formed_rfc3339`, against a fixed known Unix
timestamp.

## 14. Static Verification

Performed this session, in lieu of a full `cargo test` run of the
`src-tauri` crate (see §15 for why):

- **`sidecar-core`'s existing 49-test suite was executed for real**
  (see §15) — confirms the frozen baseline this checkpoint builds on is
  intact and untouched, independent of anything in `src-tauri`.
- **Full recursive diff** of the extracted project against the original
  uploaded archive: exactly two files differ —
  `src-tauri/src/lib.rs` (modified) and `src-tauri/src/events.rs` (new).
  No other file, in any directory, was touched.
- **The pure, dependency-free subset of `events.rs`'s logic**
  (`EventSequencer`'s atomics, `format_rfc3339`) was extracted into a
  standalone `.rs` file with no external crate dependencies and
  compiled + executed directly with `rustc --edition 2021` (the
  toolchain available in this environment, see §15) — all assertions,
  including the fixed-timestamp case and monotonic-sequence/
  generation-bump cases, passed. This is a genuine execution of the
  actual algorithm, not a code-reading exercise, for the one part of
  `events.rs` that has no external-crate dependency.
- **Manual, line-by-line review** of every new/changed line in
  `lib.rs`/`events.rs` for type and borrow correctness (`Copy`/
  `PartialEq` derives on `LifecycleState`, lock/drop ordering, the
  `Option<&SidecarError>` argument shape, `state.events` field access
  lifetime relative to `handle`/`app_handle` clones) — documented
  inline in this report's §5.1/§11 rather than merely asserted.
- **Tauri v2 API surface** (`tauri::Emitter`, `AppHandle::emit`) was
  confirmed against Tauri's own current published documentation this
  session (§8), not assumed from training data or copied from a v1
  example.

## 15. Environment Limitations

`cargo`/`rustc` **are** available in this environment (installed via
`apt` this session: `rustc`/`cargo` 1.75.0, since neither was
pre-installed). `sidecar-core`'s full test suite (49 tests, 3 files)
was executed for real with this toolchain and passed completely — see
the raw output captured this session.

`src-tauri` could **not** be fully compiled or its tests executed: its
pinned `tauri = "2"` dependency resolves to `tauri v2.11.5`, whose
transitive dependency graph requires `indexmap >= 2.13`, which in turn
requires Cargo's `edition2024` feature — unavailable in Cargo 1.75.0
(the newest version obtainable via `apt` in this sandboxed
environment; `rustup`'s and `static.rust-lang.org`'s installer/release
domains are not on this environment's network allowlist, so a newer
toolchain could not be fetched). Pinning `indexmap` to an
edition2021-compatible version was attempted and also failed, one level
further up the same dependency chain (`toml` itself, pulled in by
`tauri-utils`, requires `indexmap ^2.13`). No source file was changed
in an attempt to work around this — `Cargo.toml`'s `tauri = "2"`
constraint is exactly as frozen as every other file this checkpoint did
not touch.

**Executed this session:** `sidecar-core`'s full test suite (`cargo
test`, real, 49/49 passing); the dependency-free subset of `events.rs`'s
own logic (standalone `rustc` compile + run, all assertions passing).

**Not executed this session:** `src-tauri`'s test suite, including this
checkpoint's own five new tests in `events.rs` — blocked by the
toolchain/dependency-graph limitation above, not by anything in this
checkpoint's own code. Static/structural verification (§14) was
performed in its place, and is reported separately from execution, per
the task brief's own instruction not to conflate the two.

## 16. Files Changed

```text
Modified:
  src-tauri/src/lib.rs
    - added `mod events;` and its imports
    - added `events: EventSequencer` field to `SidecarState`
    - added `EventSequencer::new()` to the `SidecarState` constructor
    - added emit_state_changed(...) calls at the four real transition
      call sites (initial launch, crash-poll loop, restart, shutdown)
    - no change to any function's decision logic, restart policy,
      locking discipline, or lifecycle transition itself

Created:
  src-tauri/src/events.rs
    - EVENT_STATE_CHANGED constant
    - EventSequencer (sequence/generation counters)
    - StateChangeReason / StateChangedPayload (payload contract)
    - build_state_changed_payload / emit_state_changed (the adapter)
    - format_rfc3339 (dependency-free timestamp formatter)
    - #[cfg(test)] mod tests (the five requested test categories)

  docs/phase4/PHASE4E_P3_PART2A_EVENT_ADAPTER_IMPLEMENTATION.md
    - this document

Unchanged (verified by full recursive diff against the uploaded
archive, §14): sidecar-core/ in its entirety, src-tauri/src/sidecar.rs,
src-tauri/src/restart_scheduler.rs, src-tauri/src/main.rs,
src-tauri/Cargo.toml, src-tauri/Cargo.lock, frontend/ in its entirety,
app/ in its entirety, every other docs/ file including the frozen P3
architecture document itself.

Implementation source changes: 2 files (1 modified, 1 created).
Packaging source changes: 0.
```

## 17. Frozen Checkpoint Verification

Confirmed intact, this session, by full recursive diff against the
uploaded `SOC-IQ-Phase4E-P3-Part1-COMPLETE-FULL-PROJECT.zip`:

```text
P1                    unchanged
P2 Part 1             unchanged
P2 Part 2A            unchanged
P2 Part 2B-1          unchanged
P2 Part 2B-2          unchanged
P2 Part 2B-3          unchanged
P2 Part 2B-4          unchanged
P2 Part 2B-5          unchanged
P3 Part 1             unchanged
```

No genuine defect was found in any frozen checkpoint this session. The
one real constraint discovered (§5.1 — `sidecar.rs`'s synchronous
`start()`/`shutdown()` offering no intermediate transition hook) is not
a defect: it is a correct, intentional consequence of that file's own
documented design (see `sidecar.rs`'s own module doc, "deliberately
dependency-free... a synchronous std-only implementation is sufficient
here"), and this checkpoint works within it rather than reopening it.

## 18. Final Classification

**PASS WITH DOCUMENTED LIMITATION.**

Implementation is complete for the exact Part 2A scope requested.
Runtime compilation/test execution of the `src-tauri` crate specifically
(as opposed to `sidecar-core`, which was fully executed) is blocked by
an environment toolchain limitation unrelated to this checkpoint's own
code (§15), not by a frozen-architecture conflict and not by a defect
in the new code. Static/structural verification was performed in its
place and is reported separately from executed tests throughout this
document, per the task brief's own requirement.

## 19. Recommendation

The event contract and adapter foundation are in place and, per the
static verification in §14, believed correct against the frozen
architecture and the frozen `sidecar-core`/`sidecar.rs` transition
behavior. Recommend proceeding to **Phase 4E-P3 Part 2B — Sequence +
Deduplication + Concurrency**, with one open item worth carrying
forward explicitly: whoever picks up Part 2B (or a later checkpoint)
should decide, deliberately, whether the `Starting`/`Stopping`
reconstructed-timestamp limitation in §5.1 is acceptable long-term or
warrants a small, explicit hook added to `sidecar.rs` at that time — not
a decision this checkpoint makes unilaterally, since it would touch a
file Part 2A's own scope rules this checkpoint out of touching.
Recommend also that whichever checkpoint next has real `cargo`/`rustc`
access with a newer toolchain (or network access to a newer Rust
release) perform the actual `cargo test -p soc-iq` run this checkpoint
could not, to convert this document's static verification into executed
verification for `src-tauri` specifically.
