# Phase 4E-P3 Part 2C — Restart Events + `get_sidecar_status`
## Implementation & Audit Report — Part 2 of 2 (Independent Final Audit + Freeze Gate)

This document replaces Part 1's report in place. Part 1's content is
preserved below the `---` divider (§A) for traceability; everything
above it is this Part 2 audit's own findings, independently derived
by reading source and, where possible, executing tests — not by
trusting Part 1's report.

## A. Final classification

**PASS WITH DOCUMENTED LIMITATION.**

Every requirement in the task brief that can be checked by reading
source was independently re-verified against the actual code, not
against Part 1's report, and holds. `sidecar-core`'s 132 tests were
actually compiled and executed in this environment (a first for any
Phase 4 Rust checkpoint in this project's history) and all pass.
`src-tauri` still cannot be compiled or its 61 written tests executed
in this sandbox — the same `edition2024`-via-transitive-dependency
blocker every prior Phase 4 session hit, re-confirmed independently
below, not merely repeated from memory.

## B. Executive summary

- The three required additions — `sidecar:restart_scheduled`,
  `sidecar:restart_exhausted`, `get_sidecar_status` — are present,
  correctly named, and match their documented contracts on direct
  source inspection.
- Exactly one `EventSequencer`, one `SidecarState`, one
  `RestartScheduler`, one `RestartPolicy`/`RestartTracker`, one
  `RestartSchedule`, and one shutdown guard (`shutting_down`) exist in
  the tree. No forbidden duplicate type (`RestartEventSequencer`,
  `SnapshotSequencer`, `FrontendLifecycleState`, a second
  pending-restart registry, etc.) was found anywhere.
- `get_sidecar_status` is read-only: it calls `EventSequencer::
  current_sequence()`, never `next_sequence()`, and performs no
  lifecycle mutation.
- The exhaustion boundary (`attempts >= max_attempts`) was independently
  re-derived from `sidecar-core/src/restart.rs` line 239, not taken on
  faith from documentation: with `max_attempts = 5` (the default),
  exhaustion is reported starting from the failure observed *after*
  5 retries have already been recorded — i.e. the 6th failure
  observation in a window.
- **New in this Part 2 session**: a real `rustc`/`cargo` 1.75
  toolchain was installed and, with live registry access, the entire
  `sidecar-core` crate was compiled and its full test suite executed:
  **132 passed, 0 failed**. This is a genuine upgrade over Part 1's
  "no toolchain available, nothing executed" — Part 1's own §23
  explicitly asked for exactly this before freezing.
- `src-tauri` still cannot compile: `cargo check` fails downloading
  `time v0.3.55` (a transitive dependency of `tauri`) with `feature
  'edition2024' is required`, unsupported by cargo/rustc 1.75. This
  matches every previous Phase 4 session's finding and is an
  environment limitation, not a code defect.
- No unrelated frontend, UI, or architectural changes were introduced.
  `frontend/src/shared/events/*` exists but is the pre-existing Phase
  4D SSE (`analysis.*`/`ti.enrichment.*`) event-boundary code, an
  unrelated Python-backend event system predating this checkpoint —
  not `sidecar:*` Tauri events, and not touched by Part 2C.
- No `.git` directory is present anywhere in the archive; no git
  history is available or fabricated.

## C. Frozen baseline

Confirmed intact and unmodified by this checkpoint (structurally
verified by direct read, not assumed):

- `sidecar_core::state::Lifecycle`/`LifecycleState` — single FSM.
- `RestartPolicy`/`RestartTracker::decide` — the `attempts >=
  max_attempts` comparison is byte-for-byte what Part 1 described.
- `RestartSchedule`/`RestartToken`/`RestartScheduler` — the sole
  at-most-one-pending restart mechanism; no second registry exists.
- `SidecarState::shutting_down` (Part 2B-3's no-resurrection guard) —
  present, unmodified, still checked in `handle_retry_eligible_failure`
  and consulted (via `restart_still_eligible`) in `attempt_restart`.

## D. Architecture audit

`SidecarState` (lib.rs) owns exactly one instance each of: `process`
(`Mutex<SidecarProcess>`), `restart_tracker`, `restart_policy`,
`scheduler` (`RestartScheduler`), `stability` (`StabilityScheduler`),
`events` (`EventSequencer`), and `shutting_down` (`AtomicBool`). A
tree-wide grep for `RestartEventSequencer`, `SnapshotSequencer`,
`FrontendSequence`, `FrontendLifecycleState`, `SidecarLifecycle`, and
`RestartLifecycle` across every `.rs` file returned zero matches.
`next_sequence()` has exactly 3 call sites, all inside `events.rs`
payload builders (`build_state_changed_payload`,
`build_restart_scheduled_payload`, `build_restart_exhausted_payload`);
`get_sidecar_status` uses only `current_sequence()`, which reads the
atomic without incrementing it.

## E. `restart_scheduled` audit

Call graph traced directly in `lib.rs::handle_retry_eligible_failure`:
`RestartTracker::decide` → `Retry{attempt, after}` → `tracker.
record_attempt()` → `state.scheduler.schedule(attempt, after, ...)` →
**only if `schedule()` returns `true`** → `emit_restart_scheduled`. The
`false` branch (timer thread could not be created) emits only an
`eprintln!`, never the event — matches the task brief's requirement
that the event correspond to an actually-accepted schedule. No second
call site to `schedule()` exists in the tree.

## F. `restart_exhausted` audit

Emitted from the same function's `Exhausted{attempts}` arm, using the
`attempts` value carried by that enum variant (never re-derived).
`status_restart_exhausted` (used by `get_sidecar_status`) applies the
identical `attempts >= policy.max_attempts` comparison, confirmed by
direct comparison against `RestartTracker::decide` line 239 — the two
cannot disagree by construction, not merely by test coverage. One-shot
argument: `handle_retry_eligible_failure` is the only call site that
observes `RestartDecision::Exhausted`, and `attempt_restart`'s
`restart_still_eligible` check means no automatic restart — and
therefore no further failure observation — can occur once exhausted.
This is a call-graph argument (static), not exercised by a dedicated
integration test; Part 1's own §21 already flagged this same gap
honestly and this audit found no way to close it without modifying
frozen control flow, which is out of scope.

## G. `get_sidecar_status` audit

Read-only, confirmed by direct read of the function body: locks
`process` only long enough to read `state()` then drops the guard,
reads `scheduler.is_pending()`/`pending_attempt()`, locks
`restart_tracker` only to read `attempts()`, and reads
`events.current_sequence()`. No `start`/`stop`/`restart`/`cancel`/
`reset` call anywhere in the function. `SidecarStatus` is a plain,
owned, `Clone`/`PartialEq`/`Serialize` struct with no method that
could perform a transition — a projection, not a second lifecycle
authority.

## H. Payload contracts

`RestartScheduledPayload{attempt, delay_ms, sequence, timestamp}` and
`RestartExhaustedPayload{attempts, code, sequence, timestamp}` both
build from `Copy` values and a freshly-allocated `String` only —
confirmed by direct read of both builder functions. No PID, process
handle, launch argument, environment variable, secret, or OS internal
appears in either payload or in `SidecarStatus`. A tree-wide grep for
PID/command/args/env/handle/secret/token near payload construction
found no matches beyond doc comments explicitly listing them as
forbidden.

## I. Sequence/order guarantees

`EventSequencer.sequence` is a bare `AtomicU64` with `fetch_add`
(`next_sequence`) as its only mutator besides construction — no
`reset`/`set` method exists on the type, so the sequence cannot be
reset by crash, restart, exhaustion, or shutdown by construction.
`current_generation()`/`current_sequence()` are read-only.

## J. Duplicate/race protection

No second pending-restart registry exists (§D). The Part 2B-3 shutdown
race protection is unmodified: `shutting_down` is set once, checked
both defensively before `schedule()` in `handle_retry_eligible_failure`
and authoritatively in `restart_still_eligible` before `attempt_restart`
proceeds. No `tokio::spawn` or other new async-spawn primitive was
introduced anywhere in the tree.

## K. Shutdown/no-resurrection verification

Traced directly: `shutting_down` is set to `true` at the very start of
the `RunEvent::Exit` handler, before `scheduler.cancel()`/`stability.
cancel()`. A stale restart callback that has already passed
`RestartSchedule::consume`'s one-shot gate is still caught by
`restart_still_eligible`'s explicit `if shutting_down { return false;
}` check before `attempt_restart` would spawn anything. This
mechanism is unmodified by Part 2C.

## L. Tests

### Executed (this Part 2 session)

A real `rustc`/`cargo` 1.75.0 toolchain (Ubuntu `noble-updates`) was
installed via `apt-get`, and this environment had live network access
to `static.crates.io`/`index.crates.io` (unlike every prior Phase 4
Rust session). `cargo test` was run against the standalone
`sidecar-core` crate (no Tauri dependency, `edition = "2021"`,
`rust-version = "1.75"`):

```
error_tests.rs             8 passed
lifecycle_tests.rs        22 passed
restart_policy_tests.rs   25 passed
restart_schedule_tests.rs 15 passed
shutdown_tests.rs         13 passed
stability_window_tests.rs 13 passed
startup_tests.rs          23 passed
supervisor_tests.rs       13 passed
-------------------------------------
Total                    132 passed, 0 failed
```

`src-tauri` (`cargo check`) was also attempted with the same
toolchain. It failed during dependency resolution:

```
error: failed to download replaced source registry `crates-io`
Caused by: failed to parse manifest at .../time-0.3.55/Cargo.toml
Caused by: feature `edition2024` is required
The package requires the Cargo feature called `edition2024`, but that
feature is not stabilized in this version of Cargo (1.75.0).
```

`time v0.3.55` is a transitive dependency pulled in by `tauri = "2"`.
This is the identical blocker documented in every earlier Phase 4
checkpoint (`PHASE4-Part1`, `Phase2A-Part2B`); it is re-confirmed here
independently rather than assumed from memory. src-tauri's 61 written
`#[test]` functions (21 in `events.rs`, 6 in `lib.rs`, 27 in
`restart_scheduler.rs`, 7 in `sidecar.rs`) remain unexecuted.

The Python test suite (`pytest tests/`, unrelated to this checkpoint's
scope but re-run as a baseline sanity check) was also actually
executed: **754 passed**, no failures.

### Static / structural verification

- Every claim in §D–§K above was checked against the actual current
  source text in this session, not carried forward from Part 1.
- Brace/structure and call-graph tracing for `handle_retry_eligible_
  failure`, `get_sidecar_status`, `restart_still_eligible`, and
  `EventSequencer` — done by direct reading, not by compiling
  `src-tauri` (which the toolchain cannot do here).
- Tree-wide greps for forbidden type names, forbidden event-name
  variants, duplicate pending-restart registries, `tokio::spawn`, and
  literal `RESTARTING`/`RESTART_EXHAUSTED` `LifecycleState` variants —
  all zero matches.

## M. Findings

```
Critical: 0
High:     0
Medium:   0
Low:      0
Info:     2
```

- **Info**: `src-tauri` remains genuinely unbuildable in every sandboxed
  environment used across this project's Phase 4 history (edition2024
  transitive requirement via `tauri`'s dependency graph vs. cargo/rustc
  1.75). Not a code defect; needs a newer toolchain (cargo ≥ 1.85) to
  close.
- **Info**: `restart_exhausted`'s one-shot guarantee (§F) rests on a
  call-graph argument, not a dedicated integration test, because the
  existing, frozen control flow provides no way to re-invoke the
  relevant function against an already-exhausted tracker without
  modifying out-of-scope code. Documented, not fabricated around.

No defect affecting lifecycle authority, restart correctness, shutdown
safety, event ordering, or snapshot authority was found.

## N. Corrections

None required. No concrete defect was found in Part 2C's own scope
during this independent audit.

## O. Files changed (Part 2C scope, as found)

Production: `sidecar-core/src/{error.rs, lib.rs, restart.rs}`,
`src-tauri/src/{events.rs, lib.rs, restart_scheduler.rs}`.
Tests: `sidecar-core/tests/{error_tests.rs, restart_schedule_tests.rs,
stability_window_tests.rs}` plus new `#[test]` functions inside the
four `src-tauri/src/*.rs` files above.
Documentation: this file.
Packaging: none (no build-script/config changes).

`app/api/`, `app/application/`, `app/threat_intel/`, and several
`docs/phase4/PHASE4D_*` files also carry timestamps after the Part
2B-3 baseline reference point used for this diff, but their content
is the pre-existing Phase 4D SSE work (a different, already-frozen
checkpoint) — not part of, and not touched by, this Part 2C session.

## P. Frozen checkpoint verification

`sidecar-core/src/state.rs` and `sidecar-core/src/process.rs`
(Part 2A Part 1 baseline) are byte-identical in content to their
documented frozen contracts — unmodified. `shutting_down`'s
Part 2B-3 semantics (§K) are intact.

## Q. Git status

`.git` not present anywhere in the extracted archive — Git metadata
was not available and was not fabricated.

## R. Environment limitations

- `src-tauri` cannot be built or tested in this sandbox: cargo/rustc
  1.75 (the newest available via this environment's package mirror)
  cannot resolve `tauri = "2"`'s dependency graph, which requires
  `edition2024` (cargo ≥ 1.85) via the transitive `time` crate.
- `sidecar-core` **can** now be built and tested here, and was: 132/132
  tests passing, a genuine first for this project's Phase 4 Rust work.
- Frontend (`npm`/`vite`/`vitest`) was not re-verified in this session
  — out of scope for Part 2C, which makes no frontend changes.

## S. Documentation

This file, in place of Part 1's report (Part 1's content preserved
below as §A record).

## T. Full project ZIP

See the final chat message for the actual file-count/checksum
verification output produced after packaging (this document is
written before packaging so it can be included inside the archive).

Note: `sidecar-core/target/` (274 MB of this session's own `cargo
test` build output) was deleted before packaging — it is build cache,
not source, and was never part of the frozen baseline's file
inventory.

## U. Final recommendation

Phase 4E-P3 Part 2C's own scope (the three required additions) is
correct and ready to freeze on its merits: every static/structural
requirement holds, and `sidecar-core`'s tests now have real, executed,
passing confirmation for the first time.

The one open gate — actually compiling and running `src-tauri`'s 61
tests — still cannot be closed in any sandbox this project has had
access to. Consistent with Part 1's own recommendation, this
checkpoint should **not** be declared a full, unconditional freeze
until that happens in an environment with cargo ≥ 1.85. Recommend:
freeze Part 2C's design/implementation as **PASS WITH DOCUMENTED
LIMITATION**, and treat "`cargo test` on `src-tauri` actually runs and
passes" as the standing gate for the *next* session, exactly as Part 1
already asked.

---

# Appendix: Part 1's original report (preserved verbatim for record)

# Phase 4E-P3 Part 2C — Restart Events + `get_sidecar_status`
## Implementation & Audit Report — Part 1 of 2

## 1. Scope

This checkpoint implements exactly the three items Part 2A's own module
doc listed as explicitly out of scope:

1. `sidecar:restart_scheduled`
2. `sidecar:restart_exhausted`
3. `get_sidecar_status` (read-only status-snapshot command)

Nothing else. No new `LifecycleState` variant, no second lifecycle
owner, no second event sequencer, no second restart-pending registry,
no change to `RestartPolicy`/`RestartTracker` semantics, no change to
the Part 2B-3 `shutting_down`/no-resurrection protection, no frontend
(React) code.

## 2. Frozen baseline

Starting point: `SOC-IQ-Phase4E-P3-Part2B-3-COMPLETE-FULL-PROJECT.zip`.
Read in full before any change:

- `docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md`
- `docs/phase4/PHASE4E_P3_PART2A_EVENT_ADAPTER_IMPLEMENTATION.md`
- `docs/phase4/PHASE4E_P3_PART2B1_SEQUENCE_AUTHORITY_IMPLEMENTATION.md`
- `docs/phase4/PHASE4E_P3_PART2B2_PREVIOUS_STATE_EVENT_ORDERING.md`
- `docs/phase4/PHASE4E_P3_PART2B3_DEDUP_CONCURRENCY_RACE_AUDIT.md`

And the source: `src-tauri/src/{lib,events,sidecar,restart_scheduler}.rs`,
`sidecar-core/src/{state,restart,error,lib}.rs`, and every existing test
module in those files.

## 3. Existing architecture (as found, not as assumed)

- **Lifecycle authority**: `sidecar_core::state::Lifecycle` /
  `LifecycleState` — a single FSM, owned by one `Mutex<SidecarProcess>`
  inside `SidecarState`. Unchanged.
- **Restart decision authority**: `sidecar_core::restart::RestartPolicy`
  (pure config + backoff calc) and `RestartTracker` (the one attempt
  counter). `RestartTracker::decide` returns `Retry { attempt, after }`
  or `Exhausted { attempts }`. Unchanged.
- **Restart scheduling authority**: `sidecar_core::restart::RestartSchedule`
  (pure, at-most-one-pending bookkeeping via `RestartToken`), composed
  by `src-tauri`'s `restart_scheduler::RestartScheduler` with a real
  `DelayRunner` timer. Unchanged except one additive passthrough
  method (§6 below).
- **Event authority**: `src-tauri::events::EventSequencer` — one
  process-lifetime `AtomicU64` sequence + `AtomicU32` generation,
  owned by `SidecarState`. `sidecar:state_changed` was the only event
  it emitted before this checkpoint.
- **Single call site for restart decisions**:
  `lib.rs::handle_retry_eligible_failure`, reached from the crash-poll
  loop and from a failed restart attempt. This is the one place
  `RestartDecision::Retry`/`Exhausted` is ever observed — confirmed by
  reading every call site of `RestartTracker::decide` in the tree
  (exactly one).

## 4. `restart_scheduled` contract

Emitted from `handle_retry_eligible_failure`'s `Retry` arm, **after**
`state.scheduler.schedule(attempt, after, ...)` returns `true`. If
`schedule()` returns `false` (timer thread could not be created, or —
structurally impossible under the single-owner model — a restart was
already pending), no event is emitted; only the existing `eprintln!`
diagnostic fires, unchanged in spirit from Part 2B-2.

Event name: `sidecar:restart_scheduled` (`events::EVENT_RESTART_SCHEDULED`).

## 5. `restart_exhausted` contract

Emitted from the same function's `Exhausted` arm, using the `attempts`
value `RestartDecision::Exhausted` itself carries (always
`policy.max_attempts` by that type's own invariant — never
re-derived). No new exhaustion condition; no new comparison; reuses
`RestartTracker::decide`'s existing `attempts >= max_attempts` test
unmodified.

Event name: `sidecar:restart_exhausted` (`events::EVENT_RESTART_EXHAUSTED`).

## 6. Payload definitions

`events::RestartScheduledPayload`:

| field        | type   | meaning                                                        |
|--------------|--------|------------------------------------------------------------------|
| `attempt`    | u32    | the accepted attempt number (`RestartDecision::Retry::attempt`)  |
| `delay_ms`   | u64    | the accepted backoff delay, milliseconds (`Retry::after`, never recomputed) |
| `sequence`   | u64    | allocated from the one `EventSequencer`                          |
| `timestamp`  | String | RFC 3339 UTC, the moment `schedule()` was confirmed accepted      |

`events::RestartExhaustedPayload`:

| field       | type   | meaning                                                    |
|-------------|--------|-------------------------------------------------------------|
| `attempts`  | u32    | final attempt count (`RestartDecision::Exhausted::attempts`) |
| `code`      | String | `SidecarError::RestartExhausted{..}.code()` — `"SIDECAR_RESTART_EXHAUSTED"`, reused verbatim |
| `sequence`  | u64    | allocated from the one `EventSequencer`                      |
| `timestamp` | String | RFC 3339 UTC, the moment exhaustion was observed             |

Neither payload contains a PID, process handle, command line, launch
argument, environment variable, secret, thread id, mutex internal, OS
internal, or filesystem path — both are built entirely from `Copy`
values (`u32`/`u64`/`Duration`) and one freshly allocated `String`
(`rfc3339_now()`), never a reference into `Mutex`/`SidecarProcess`/
`Supervisor`/`RestartScheduler`. Verified by direct inspection of both
`build_restart_scheduled_payload`/`build_restart_exhausted_payload` —
neither takes nor stores any such reference — and by
`restart_scheduled_payload_is_owned_and_stable_once_built` (events.rs
tests), which proves a built payload is unaffected by later sequencer
activity.

`events::SidecarStatus` (the `get_sidecar_status` return type — see §10):

| field                     | type           | source authority                                   |
|---------------------------|----------------|-----------------------------------------------------|
| `state`                   | String         | `state.process` (`LifecycleState::to_string()`)      |
| `restart_pending`         | bool           | `state.scheduler.is_pending()`                       |
| `restart_pending_attempt` | Option\<u32\>  | `state.scheduler.pending_attempt()`                  |
| `restart_attempts`        | u32            | `state.restart_tracker`                              |
| `restart_exhausted`       | bool           | `status_restart_exhausted(attempts, &policy)` — identical `attempts >= max_attempts` test |
| `sequence`                | u64            | `state.events.current_sequence()` (peek, no allocation) |

## 7. Sequence behavior

Every emitted event (all three kinds) draws from the one
`EventSequencer::next_sequence()` already used by `state_changed` —
no second counter, no reset, no reuse. `get_sidecar_status` calls only
`current_sequence()`, a plain atomic load with **no** side effect —
confirmed by direct inspection (the method body is `self.sequence.load(Ordering::SeqCst)`,
nothing else) and by
`current_sequence_never_allocates_and_only_reflects_real_emissions`
(events.rs tests), which calls it twice with no intervening event and
asserts the value is unchanged both times.

`sequence_is_unique_and_strictly_increasing_across_every_event_kind`
(events.rs tests) drives `state_changed` → `restart_scheduled` →
`state_changed` → `restart_exhausted` through one shared sequencer and
asserts the four resulting values are `[1, 2, 3, 4]` — unique and
strictly increasing across every mixed kind, not just within one kind.

## 8. Duplicate/exhaustion protection

**Duplicate scheduling**: unchanged from Part 2B-2 —
`RestartSchedule::try_begin` refuses a second pending restart
(`RestartScheduler::schedule` returns `false`); this checkpoint's
`restart_scheduled` emission is gated on that same `true`/`false`
return, so a rejected duplicate schedule produces no event. No new
pending-restart registry was added; `pending_attempt()` (the one new
method on `RestartScheduler`, §restart_scheduler.rs) is a thin
passthrough to the existing `RestartSchedule::pending_attempt`.

**Exhaustion, single emission**: `handle_retry_eligible_failure` is
reached at most once per real crash-loop-window exhaustion in the
*existing, unmodified* call graph:
- `run_crash_poll_loop` calls it exactly once per crash and then
  `break`s its own loop — it is not resumed except by a *successful*
  restart (which calls `begin_stability_window` and re-enters
  `run_crash_poll_loop` on a fresh `RUNNING` episode, not by
  re-invoking this function).
- `attempt_restart`'s own `restart_still_eligible` re-check means no
  further automatic restart — and therefore no further failure
  observation reaching this function — can occur once the sidecar is
  in a state that would otherwise require a fresh `RestartDecision`.
- `RestartTracker::record_attempt` is only ever called from the
  `Retry` arm, never from `Exhausted`, so `attempts` cannot climb past
  `max_attempts` between one exhaustion observation and a hypothetical
  next one.

No new one-shot/dedup flag was added to enforce this a second time —
doing so was considered and rejected, per the task brief's own
guidance to prefer existing state (§14) and to only add a new
flag/token mechanism when *genuinely* necessary (§25 of the Part 2B-3
brief, same principle applied here). See §21 "Environment limitations"
below for the honest caveat this implies for the "repeated exhaustion"
test.

## 9. Exhaustion boundary

Untouched: `max_attempts`, the `>=` comparison, and
`RestartTracker`/`RestartPolicy`'s public API are byte-for-byte
identical to the frozen Part 2B-1 baseline. `status_restart_exhausted`
(lib.rs) is a *new*, additive, pure function that mirrors the same
comparison for `get_sidecar_status`'s benefit — it does not replace or
shadow `RestartTracker::decide`, and
`status_restart_exhausted_agrees_with_the_real_restart_tracker_decision`
(lib.rs tests) proves the two never disagree, for every attempt count
from `0` through `max_attempts` inclusive (default policy: 0..=5).

## 10. `get_sidecar_status`

New `#[tauri::command] fn get_sidecar_status(state: tauri::State<'_, SidecarState>) -> SidecarStatus`,
registered in `run()`'s `invoke_handler(tauri::generate_handler![get_sidecar_origin, get_sidecar_status])`.
Purely additive: `get_sidecar_origin`'s registration and behavior are
untouched.

Read-only: the function body contains no call to `process.start()`,
`process.reset()`, `process.shutdown()`, `scheduler.schedule()`,
`scheduler.cancel()`, `stability.begin()`, `stability.cancel()`,
`restart_tracker.record_attempt()`/`.reset()`, or
`events.next_sequence()` — confirmed by direct inspection of the full
function body (§10 payload table above lists every field it reads,
and every read is a getter: `.state()`, `.is_pending()`,
`.pending_attempt()`, `.attempts()`, `.current_sequence()`).

## 11. Snapshot authority

Every field is read from the same existing authority every other call
site in `lib.rs` already treats as authoritative — `state.process` for
`LifecycleState` (the same mutex `run_crash_poll_loop`/`attempt_restart`
lock before acting), `state.scheduler` for pending-restart status
(never a second `frontend_restart_pending` flag), `state.restart_tracker`/
`state.restart_policy` for the attempt count and exhaustion condition,
`state.events` for the latest sequence. No frontend cache, no event
history, no duplicated lifecycle cache of any kind exists anywhere in
this diff.

## 12. Snapshot consistency

`get_sidecar_status` acquires and releases three independent locks in
sequence — `state.process`, `state.scheduler`'s internal
`RestartSchedule` mutex (via `is_pending()`/`pending_attempt()`), and
`state.restart_tracker` — each held only long enough to read its own
field, per the task brief's "lock, read, construct, release" guidance.
There is **no single combined lock** spanning all of them in the
existing architecture (`SidecarState`'s own doc describes one `Mutex`
per independently-accessed piece of state, not one coarse lock
protecting everything), and introducing one purely for this read-only
snapshot would itself be new synchronization architecture the task
brief instructs against (§1: "do not redesign the architecture"). This
is documented in the function's own doc comment in `lib.rs`, not
silently relied upon.

## 13. Snapshot/event race

Practical consequence of §12: in the narrow window between two of
`get_sidecar_status`'s internal reads, a real transition (a crash, a
completed restart, a freshly accepted schedule) could in principle
land, producing a snapshot whose fields were not all true at exactly
the same instant (e.g. `state` observed as `Crashed` a few
microseconds before `restart_pending` flips to `true` once the retry
is scheduled). This is the same class of cross-lock race that already
existed before this checkpoint wherever two different pieces of
`SidecarState` are read in sequence (e.g.
`confirm_stability_if_still_running` reads `state.process` then,
separately, `state.restart_tracker`) — this checkpoint neither
introduces a new instance of the pattern nor claims to close it; it is
called out explicitly rather than left implicit.

## 14. Shutdown interaction

`get_sidecar_status` performs no special-casing for `shutting_down` —
it simply reports whatever `state.process.state()` currently is. Once
`RunEvent::Exit`'s handler has run, that is authoritatively `Stopping`
then `Stopped` (the same states `attempt_restart`'s `restart_still_eligible`
re-check already treats as non-eligible once `shutting_down` is set).
A stale restart callback that fires after shutdown has begun is
already prevented, by the unmodified Part 2B-3 protection, from ever
reaching `Running`/spawning a process again — so it cannot change what
`get_sidecar_status` reports either. No code in this diff touches
`SidecarState::shutting_down`, `restart_still_eligible`, or the
`RunEvent::Exit` handler.

## 15. Security review

Grepped every new struct field against the forbidden list (PID,
process handle, command line, launch arguments, environment variables,
secrets, thread ids, mutex internals, OS internals, private filesystem
paths): none present in `RestartScheduledPayload`, `RestartExhaustedPayload`,
or `SidecarStatus`. `SidecarStatus.state` reuses the exact same
uppercase wire-format string `state_changed` already exposes
(`LifecycleState::to_string()`); no additional information is leaked
via that field beyond what `state_changed` events already broadcast.

## 16. Tests

Added (all in the existing frozen test-module style — `#[cfg(test)] mod tests` at
the bottom of each file, `use super::*;`):

**`src-tauri/src/events.rs`** (pure payload-construction/sequencer
tests — no `AppHandle` required, same testability boundary Part 2A's
own tests already established for `build_state_changed_payload`):
- `restart_scheduled_payload_reflects_the_accepted_attempt_and_delay`
- `restart_scheduled_payload_is_owned_and_stable_once_built`
- `restart_exhausted_payload_reflects_the_final_attempt_count`
- `sequence_is_unique_and_strictly_increasing_across_every_event_kind`
- `current_sequence_never_allocates_and_only_reflects_real_emissions`

**`src-tauri/src/lib.rs`** (pure decision-table tests — same boundary
Part 2B-3's own `restart_still_eligible` tests already established):
- `status_restart_exhausted_agrees_with_the_real_restart_tracker_decision`
- `status_restart_exhausted_is_false_below_max_attempts`

### Executed tests

**None.** See §21 — no Rust toolchain is available in this
environment (`cargo`/`rustc` not found on `PATH`, no network access to
install one). Every test above was written and manually re-read
against the exact function signatures it calls, but has not been
compiled or run. This is stated plainly, not glossed over: **no test
result in this report should be read as "passed" — only "written and
reviewed."**

### Static verification

- Manual brace-balance check across all three modified files
  (`lib.rs`, `events.rs`, `restart_scheduler.rs`): balanced (0 net
  depth) in all three.
- Full manual re-read of every new/modified function against the
  actual (not assumed) signatures of `RestartScheduler::schedule`,
  `RestartSchedule::pending_attempt`, `RestartTracker::decide`,
  `SidecarError::RestartExhausted`/`.code()`, `tauri::State`/`AppHandle::emit`
  usage patterns already established elsewhere in the same files.
- §46's required grep sweep: see §17.

## 17. Static verification (grep sweep)

```
sidecar:state_changed        — unchanged occurrences + 0 new emitters beyond events.rs
sidecar:restart_scheduled    — 1 const definition (events.rs), 1 emit call site (lib.rs), tests
sidecar:restart_exhausted    — 1 const definition (events.rs), 1 emit call site (lib.rs), tests
get_sidecar_status           — 1 fn definition (lib.rs), 1 registration site, doc references
next_sequence                — 3 call sites, all inside events.rs payload builders; 0 inside
                                get_sidecar_status or any status-path code
RestartPolicy / RestartTracker / RestartSchedule / RestartToken / RestartScheduler
                              — 0 new struct/type definitions; only new passthrough method
                                (RestartScheduler::pending_attempt) and pure reads
shutting_down                 — 0 new occurrences; untouched
RESTARTING / RESTART_EXHAUSTED (as LifecycleState variants) — 0 occurrences anywhere in the tree
```

Confirmed:
- exactly one lifecycle authority (`sidecar_core::state::Lifecycle`, untouched)
- exactly one sequence authority (`events::EventSequencer`, one counter, one new
  non-allocating peek method)
- no new FSM state
- no duplicate restart registry (`pending_attempt` is a passthrough, not a new store)
- no stale resurrection path added or weakened (`shutting_down`/`restart_still_eligible` untouched)
- no unbounded event history (no event is buffered or retained anywhere in this diff)
- `get_sidecar_status` is read-only (§10)

## 18. Findings

| Severity | Count | Notes |
|----------|-------|-------|
| Critical | 0 | |
| High | 0 | |
| Medium | 1 | No Rust toolchain available in this environment — nothing in this checkpoint (or any prior one packaged with it) has been compiled or test-executed here. This is an environment limitation, not a defect in the change itself, but it means "PASS" below is a static/review-level pass only. See §21. |
| Low | 1 | `get_sidecar_status` reads three independent locks with no combined synchronization boundary (§12/§13) — a pre-existing pattern in this codebase, not introduced by this checkpoint, but worth a future phase's attention if snapshot atomicity across fields ever becomes load-bearing (it is not, today: the frontend only needs "a recent, self-consistent-enough" snapshot for a late-mounting listener, not a linearizable one). |
| Info | 1 | `RestartScheduledPayload`/`RestartExhaustedPayload`/`SidecarStatus` use RFC 3339 string timestamps for consistency with the existing `StateChangedPayload.timestamp` field, rather than a raw Unix integer — a deliberate consistency choice, not dictated by the architecture doc, called out here for visibility. |

No architectural inconsistency was found between the architecture
document and the actual implementation beyond the one Part 2B-3's own
module doc already recorded (the `CRASHED -> FAILED` diagram
discrepancy, pre-existing, not touched by this checkpoint).

## 19. Files changed

Production source:
- `src-tauri/src/events.rs` — new consts, payloads, builders, emitters, `SidecarStatus`, `current_sequence()`
- `src-tauri/src/lib.rs` — new emission call sites in `handle_retry_eligible_failure`, new `status_restart_exhausted`, new `get_sidecar_status` command + registration, updated module-doc header
- `src-tauri/src/restart_scheduler.rs` — new `RestartScheduler::pending_attempt()` passthrough

Documentation:
- `docs/phase4/PHASE4E_P3_PART2C_RESTART_EVENTS_STATUS_SNAPSHOT_AUDIT.md` (this file)

Tests: included inline in the two production files above (§16) — no
separate test files added.

Packaging: 0 source changes (the ZIP itself is not a source artifact).

## 20. Frozen checkpoint verification

`diff -rq` between the extracted P3-Part2B-3 baseline and this
checkpoint's working tree reports exactly three differing files:
`src-tauri/src/events.rs`, `src-tauri/src/lib.rs`,
`src-tauri/src/restart_scheduler.rs` — the three files listed in §19.
No other file in the tree (including every file under `app/`,
`frontend/`, `sidecar-core/`, `database/`, `config/`, `docs/` other
than the one new doc, `samples/`, `tests/`) differs from the frozen
baseline.

## 21. Environment limitations

- **No Rust toolchain**: `which cargo` / `which rustc` both report not
  found; no network egress is available to this environment to install
  one. Every claim about this code's runtime behavior in this report
  is therefore a claim about what was *written and manually reviewed
  against the actual existing signatures*, not what was *observed to
  execute*. No test in §16 was run; none is claimed to have passed.
- **Test 36 ("repeated exhaustion") specifically**: the task brief
  asks to "repeat the relevant failure observation if the existing
  architecture allows it" and verify no repeated `restart_exhausted`.
  As documented in §8, the existing, unmodified call graph does not
  provide a way to re-invoke `handle_retry_eligible_failure` a second
  time against an already-exhausted tracker without either (a)
  fabricating a second, independent `RestartTracker`/call (which would
  test the pure `RestartTracker::decide` idempotence already covered
  by `status_restart_exhausted_agrees_with_the_real_restart_tracker_decision`,
  not the real single-call-site guarantee), or (b) modifying
  `run_crash_poll_loop`/`attempt_restart`'s control flow to allow a
  second call (explicitly out of scope — "do not redesign the
  architecture"). This report states that gap directly rather than
  fabricating a test that exercises a code path the real application
  cannot reach.
- **Tauri command/event integration tests**: `get_sidecar_status`,
  `emit_restart_scheduled`, and `emit_restart_exhausted` all require a
  real `tauri::AppHandle`/`State`, which this crate has never had a
  mock/test harness for (confirmed absent in the frozen baseline too —
  `grep`-verified, §16 of the events.rs module doc already documents
  this same limitation for `emit_state_changed`). This is a pre-existing
  gap in the project's test infrastructure, not something this
  checkpoint introduces or could close without adding new test-harness
  dependencies (out of scope).

## 22. Final classification

**PASS WITH DOCUMENTED LIMITATION.**

Every static/structural requirement in the task brief (§1-§58) that
does not require executing `cargo test` was verified directly against
the actual source. The one thing that could not be done is running
the code — because this environment has no Rust toolchain and no
network access to obtain one — and that limitation is stated plainly
above rather than worked around with a fabricated result.

## 23. Freeze recommendation

Do **not** freeze this checkpoint until an environment with a working
Rust/Cargo toolchain has actually run:

```
cargo test -p sidecar-core
cargo test -p soc-iq-tauri   # (or the actual src-tauri package name)
```

and confirmed a clean build plus all tests above passing for real. A
Part 2 pass (independent audit/verification, per the task brief's own
two-part structure) should start from this Part 1 archive, but should
treat "compiles and tests actually pass" as its first, not-yet-crossed
checkpoint gate — everything in this report up to that point is a
careful static review, not a substitute for it.
