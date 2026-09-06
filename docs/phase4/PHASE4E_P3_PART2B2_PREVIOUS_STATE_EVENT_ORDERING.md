# Phase 4E-P3, Part 2B-2 — Previous-State Integrity + Event Ordering

**Status:** Implementation checkpoint. Builds on, and treats as frozen,
`docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md`, Part 2A's
`docs/phase4/PHASE4E_P3_PART2A_EVENT_ADAPTER_IMPLEMENTATION.md`, and Part
2B-1's `docs/phase4/PHASE4E_P3_PART2B1_SEQUENCE_AUTHORITY_IMPLEMENTATION.md`.

---

## A. Scope

Make `sidecar:state_changed` authoritatively describe the actual
transition it reports, and establish/verify the correct relationship
between `previous_state`, `state`, and `sequence`: both state values
must come from the same real transition, captured before any later
mutation, with the sequence allocated for that specific event and the
resulting payload immutable once built.

## B. Frozen Baseline

Not reopened: Phase 4E-P1; Phase 4E-P2 Parts 1, 2A, 2B-1 through 2B-5;
Phase 4E-P3 Part 1; Phase 4E-P3 Part 2A; Phase 4E-P3 Part 2B-1.

## C. A second load-bearing finding: the invariant already held

As with Part 2B-1's own discovery about the sequence authority, this
checkpoint's mandatory first step (re-reading `lib.rs` directly rather
than trusting prior reports, task brief §1) found that the
previous-state/current-state/sequence relationship this checkpoint is
asked to "make" correct **was already correct in every one of the four
real call sites**, since Part 2A:

| Call site | Pattern (re-verified this session) |
|---|---|
| Initial launch (`run()`'s `setup` closure) | `let previous = process.state();` (before `start()`), `let current = process.state();` (after, still locked), `drop(process);`, then `emit_state_changed(..., previous, ..., current, ...)` — both values are owned `Copy` `LifecycleState`s captured under the mutex, never re-read after unlock |
| Crash detection (`run_crash_poll_loop`) | `let current = process.state();` captured immediately after `poll_for_crash()` returns `Some(Err(_))`, `drop(process);`, then emitted with a hard-coded `previous = LifecycleState::Running` — correct by construction, since the loop's own preceding guard (`if process.state() != Running { break; }`) means this branch is only reachable when the state actually was `Running` on entry to this tick |
| Restart (`attempt_restart`) | `let previous = process.state();` before `reset()`, `let after_reset = process.state();` after — then the same owned-value pattern repeats for the subsequent `start()` call |
| Shutdown (`RunEvent::Exit` handler) | `let previous = process.state();` before `shutdown()`, `let current = process.state();` after, `drop(process);`, emitted only `if previous != current` (so a no-op shutdown, correctly, emits nothing) |

No code path derives `previous_state` from poll history, frontend
state, timestamps, event history, or cached assumptions (task brief
§6) — every one reads it directly from `process.state()` at the
correct moment, under the same mutex the transition itself was
performed under. No code path retains a reference into
`SidecarProcess`/`Mutex<SidecarProcess>`/`Supervisor` in the
constructed payload (task brief §10) — `StateChangedPayload` is fully
owned (`String`/`Option<StateChangeReason>`/`u64`/`u32`), and every
value passed into `build_state_changed_payload` is a `Copy`
`LifecycleState`, not a reference.

**Conclusion:** no source change was required to satisfy scope items
A–F. This is recorded as an **INFORMATIONAL** finding, exactly
analogous to Part 2B-1's own finding about the sequence authority —
Part 2A's original design already implemented the "lock → read
authoritative transition → capture as owned values → unlock → build →
emit" pattern this checkpoint's own §9/§10/§11 describe, because the P3
architecture document specified that pattern (§19) before either
checkpoint existed. This checkpoint's actual work is closing the
specific test gaps (Test 5, Test 6, and a full-FSM transition-coverage
test) Part 2A/2B-1 had not yet added, and formally documenting/
verifying the already-correct invariant.

## D. Previous-State Authority

`previous_state` always originates from a `process.state()` read
performed **before** the mutating call (`start()`/`reset()`/
`shutdown()`) or, for the crash-poll site, from the loop's own
just-verified precondition (`Running`, re-confirmed on entry to the
tick that detected the crash). Never inferred, never cached across
calls, never derived from anything but the live FSM at the correct
instant.

## E. Event Construction

`StateChangedPayload` is built once, after the transition is already
complete and both `previous`/`current` have been captured as owned
`Copy` values and the lock has been dropped (task brief §9's exact
ordering: transition → capture → sequence → immutable payload →
emit). No field of the payload is a reference; `state`/`previous_state`
are converted to owned `String`s at construction time
(`state_name`/`LifecycleState`'s `Display` impl), so the payload holds
no live connection to `SidecarProcess`/`Mutex`/`Supervisor` that a
later mutation could reach through. This is now covered by an explicit
test (`already_built_payload_is_unaffected_by_later_lifecycle_mutation`,
§I) that drives a real `Lifecycle` five further transitions past the
point a payload was built from it and confirms the payload is
byte-for-byte unchanged.

## F. Sequence Integration

Unchanged from Part 2B-1: one `EventSequencer`, one `next_sequence()`
call per `build_state_changed_payload` call, i.e. per event — not
replaced, not duplicated. The sequence is allocated as the last step
before the payload is finalized (`build_state_changed_payload`'s own
body: capture `reason`/`state`/`previous_state` fields, allocate
`sequence`, allocate/read `generation`, stamp `timestamp` — all in one
synchronous function call, so no other emission can be interleaved
between "transition captured" and "sequence allocated" for the same
event).

## G. Ordering Semantics

`sequence` is the sole application-level ordering signal a future
consumer should use — not Tauri transport order, not JS callback
order, not arrival time, and not `timestamp` (task brief §12/§14). This
was already true structurally (nothing in this crate treats
`timestamp` as an ordering key), and is unchanged. The FSM remains
authoritative for *which transition happens first*; `sequence` is
assigned strictly after a transition is already accepted, never before
and never as a gate on whether a transition is allowed (task brief
§13) — `build_state_changed_payload` has no path back into
`Lifecycle::transition` or any lifecycle-mutating call.

Two events may share the same `timestamp` (second-precision RFC 3339)
while still having strictly distinct `sequence` values — already
demonstrated by the existing `sequence_is_strictly_increasing_across_emissions`
test, which calls `build_state_changed_payload` three times in
immediate succession.

## H. Crash / Restart / Shutdown Event Representation

- **Crash:** exactly `previous_state = RUNNING`, `state = CRASHED`
  (§C table, row 2) — matches task brief §15 exactly.
- **Restart:** exactly `previous_state = CRASHED` (or `FAILED`/
  `TIMEOUT`), `state = NOT_STARTED` (from `reset()`), immediately
  followed by a second event `previous_state = NOT_STARTED`,
  `state = STARTING`. **No synthetic `RESTARTING` state is emitted** —
  confirmed by re-reading `attempt_restart` in full this session; every
  emitted `state` value is one of the real 8 `LifecycleState` variants
  (task brief §16's explicit prohibition, honored).
- **Shutdown:** exactly `previous_state = RUNNING`, `state = STOPPING`,
  then `previous_state = STOPPING`, `state = STOPPED` (or `FAILED` on a
  shutdown timeout) — §C table, row 4. A later event can never mutate
  an earlier one's payload (task brief §17's explicit prohibition):
  each `state_changed` emission constructs and emits its own
  independent `StateChangedPayload`; there is no shared mutable payload
  object any call site holds onto across emissions.

## I. Tests

**Preserved, unchanged:** all Part 2A and Part 2B-1 tests (payload
construction, event name, transition mapping, sequence/generation
behavior, forbidden-fields, RFC 3339 formatting, the `sidecar-core`
Tauri-purity check, the four Part 2B-1 sequence-authority tests). None
was weakened, deleted, or rewritten.

**Added this checkpoint:**

| # | Test | What it verifies |
|---|---|---|
| 5 | `already_built_payload_is_unaffected_by_later_lifecycle_mutation` | Builds a payload from a real `Lifecycle` transition, then drives that same `Lifecycle` through five further real transitions, and asserts the already-built payload (compared via a `.clone()` snapshot) is completely unchanged — the immutability requirement (task brief §10), exercised against the real FSM rather than asserted only by code inspection |
| 6 | `invalid_transition_is_rejected_by_the_fsm_and_never_reaches_an_event` | Attempts a real invalid transition (`NotStarted -> Running`) against the actual, unmodified `sidecar_core::Lifecycle`; asserts it is rejected and the FSM's state is unchanged, so no `current` value exists for a caller to (mis)report. Also explicitly confirms the task brief's own two illustrative transitions (`STOPPED -> STARTING`, `CRASHED -> STARTING`) are **not** legal single-step edges in this frozen FSM — see §J's discrepancy note — while their real two-step equivalents (via `NotStarted`) are legal |
| 2 (extended) | `every_real_lib_rs_transition_is_legal_and_produces_a_matching_payload` | Every transition `lib.rs`'s real call sites actually drive (12 edges: the full `can_transition_to` table) is checked against the live FSM and produces a payload whose `previous_state`/`state` exactly match, superseding reliance on the task brief's own illustrative list where it diverges from the real FSM |

No test for deduplication, concurrency/race hardening, shutdown-race
hardening, stale-callback protection, `restart_scheduled`,
`restart_exhausted`, `get_sidecar_status`, or frontend projection was
added — all explicitly out of scope (task brief §4).

**Executed tests:** none this session (§K).

## J. Discrepancy Note (task brief §2's own STOP-and-report condition, evaluated)

The task brief's own illustrative transition list (§8/§20) names
`STOPPED -> STARTING` and `CRASHED -> STARTING` as representative legal
transitions. Direct inspection of `sidecar-core/src/state.rs`'s
`can_transition_to` table (re-read this session, unchanged since
Part 1) shows neither is a legal **single-step** edge — only
`Stopped -> NotStarted`, `Crashed -> NotStarted`, and separately
`NotStarted -> Starting` are. This is **not** a Part 2B-1 defect and
**not** a frozen-architecture conflict requiring a STOP: it is the
task brief's own illustrative shorthand for the real two-step sequence
`lib.rs`'s `attempt_restart` already performs (`reset()` then
`start()`, exactly as documented in Part 2A §5.1 and re-confirmed in
§H above). Classified **INFORMATIONAL**, matching the same pattern
Part 2A's own §3 used for an analogous brief/reality file-path
mismatch. No test was written asserting the illegal single-step edges
as if they were legal; `invalid_transition_is_rejected_by_the_fsm_and_never_reaches_an_event`
explicitly asserts the opposite.

## K. Static Verification (tooling unavailable)

- **Every event-producing transition has access to authoritative
  previous/current state:** confirmed by re-reading all four call
  sites in full this session (§C table).
- **No event reads mutable state after finalization:** confirmed —
  `StateChangedPayload` is fully owned; no call site passes a
  reference into `build_state_changed_payload`, only `Copy` values.
- **Only one sequence authority exists:** re-confirmed via the same
  repository-wide search Part 2B-1 performed (`EventSequencer`, one
  instance, one owner) — no new counter was added this checkpoint.
- **No sequence reset was introduced:** no change to `EventSequencer`
  at all this checkpoint (only new tests were added to the file).
- **No new lifecycle state was introduced:** `LifecycleState` (8
  variants) untouched; no `RESTARTING`/`RECOVERING`/`RESURRECTING`/
  `DEGRADED` anywhere in the diff.
- **No restart event was introduced:** no `sidecar:restart_scheduled`/
  `sidecar:restart_exhausted` anywhere in the diff; `EVENT_STATE_CHANGED`
  remains the only event constant.
- **No frontend source was changed:** confirmed by the full recursive
  diff (§L) — `frontend/` is byte-identical to the Part 2B-1 baseline.
- **No new lifecycle mutex/thread/channel/async runtime/event queue**
  was introduced (task brief §19) — the diff touches only test code in
  `events.rs`; no structural concurrency change was necessary, so
  nothing required a STOP-and-report here either.

## L. Environment Limitations

Unchanged from Part 2B-1: `cargo`/`rustc` are not available in this
sandboxed environment, and it has no network access to fetch them.

**Rust toolchain unavailable. cargo/rustc could not be executed.
Runtime compilation/test execution was not independently verified
this session.** This applies to the three new tests added this
checkpoint and to every pre-existing test (Part 2A's five, Part
2B-1's four) — none were re-executed; all were re-read for correctness
(brace/paren-balance scan plus manual type/borrow review, matching the
same method Part 2B-1 used).

## M. Files Changed

```text
Modified:
  src-tauri/src/events.rs
    - added three tests: already_built_payload_is_unaffected_by_later_lifecycle_mutation,
      invalid_transition_is_rejected_by_the_fsm_and_never_reaches_an_event,
      every_real_lib_rs_transition_is_legal_and_produces_a_matching_payload
    - no change to EventSequencer, StateChangedPayload,
      build_state_changed_payload, emit_state_changed, or any
      existing test

Created:
  docs/phase4/PHASE4E_P3_PART2B2_PREVIOUS_STATE_EVENT_ORDERING.md
    - this document

Unchanged (confirmed by full recursive diff against the uploaded
Part 2B-1 archive): src-tauri/src/lib.rs, src-tauri/src/sidecar.rs,
src-tauri/src/restart_scheduler.rs, src-tauri/src/main.rs,
src-tauri/Cargo.toml, src-tauri/Cargo.lock, sidecar-core/ in its
entirety, frontend/ in its entirety, app/ in its entirety, every
other docs/ file including all three prior P3 documents.

Implementation source changes: 1 file (modified, tests only).
Documentation changes: 1 file (created).
Packaging source changes: 0.
```

## N. Frozen Checkpoint Verification

Confirmed intact this session by full recursive diff against the
uploaded `SOC-IQ-Phase4E-P3-Part2B-1-COMPLETE-FULL-PROJECT.zip`:

```text
P1                 unchanged
P2                 unchanged
P3 Part 1          unchanged
P3 Part 2A         unchanged
P3 Part 2B-1       unchanged (only src-tauri/src/events.rs differs,
                   and only its test module)
```

## O. Git

```text
$ git status
fatal: not a git repository (or any of the parent directories): .git
```

`.git` not present — not fabricated.

## P. Final Classification

**PASS WITH DOCUMENTED LIMITATION.**

The previous-state/current-state/sequence relationship this checkpoint
was asked to establish was found, on inspection, to already be correct
in every real call site since Part 2A — this checkpoint's actual
contribution is closing the remaining test gaps (immutability under
real mutation, invalid-transition rejection, full-FSM transition
coverage) and formally documenting/verifying the invariant, plus
recording one INFORMATIONAL discrepancy between the task brief's
illustrative transition examples and the real FSM (§J). Runtime
compilation/test execution could not be independently verified this
session because `cargo`/`rustc` are unavailable and unreachable (§L) —
an environment limitation, not an implementation defect.

## Q. Final Recommendation

Ready to proceed to **P3 Part 2B-3 — Deduplication + Concurrency +
Race Hardening**. The previous-state/sequence relationship this
checkpoint verified is exactly what Part 2B-3's dedup/race work will
build on (a `sequence`-keyed, immutable, per-event payload); no further
previous-state/ordering work is needed before that checkpoint begins.
