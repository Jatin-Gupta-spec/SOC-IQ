# Phase 4E-P3, Part 2B-1 — Sequence Authority + Sequence Lifecycle

**Status:** Implementation checkpoint. Builds on, and treats as frozen,
`docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md` (the P3
architecture), `docs/phase4/PHASE4E_P3_PART2A_EVENT_ADAPTER_IMPLEMENTATION.md`
(Part 2A), and every P1/P2 checkpoint both of those in turn treat as frozen.

---

## A. Scope

This checkpoint's mandate (task brief, Part 2B-1) is: establish a
single, backend-owned, monotonic sequence authority for
`sidecar:state_changed`, that survives crash/restart/failed-restart/
recovery without resetting, is safe under concurrent access, is
attached to the existing Part 2A event payload, and is covered by
focused tests — while explicitly *not* touching previous-state
hardening, deduplication, concurrency-race hardening, shutdown-race
hardening, stale-callback protection, `restart_scheduled`,
`restart_exhausted`, `get_sidecar_status`, `SidecarStatus`, or anything
frontend-side.

## B. Frozen Baseline

Treated as frozen and **not reopened**: Phase 4E-P1; Phase 4E-P2 Parts
1, 2A, 2B-1 through 2B-5; Phase 4E-P3 Part 1 (the architecture
document); Phase 4E-P3 Part 2A (the event adapter implementation).

## C. A load-bearing finding: the sequence authority already existed

Before writing any new counter, this checkpoint's mandatory first step
(task brief §1/§6: "search the complete repository... if an existing
suitable sequence authority already exists, reuse it instead of
creating another") was performed. Result: **it already exists,
complete, from Part 2A.**

`src-tauri/src/events.rs`'s `EventSequencer` (introduced by Part 2A,
unchanged by this checkpoint) already provides everything §2's six
scope items (A–F) ask for:

| Part 2B-1 requirement | Already satisfied by `EventSequencer`, since Part 2A |
|---|---|
| A. One backend-owned sequence authority | `EventSequencer`, one instance, owned as the `events` field on the single `SidecarState` struct (`lib.rs`) — no second owner anywhere |
| B. Monotonic allocation, every `state_changed` gets a unique sequence | `next_sequence()`, called once per `build_state_changed_payload` call, itself called once per `emit_state_changed` call — every emission gets exactly one, distinct value |
| C. Survives crash/restart/failed-restart/recovery without reset | The counter is process-lifetime state on `SidecarState`, constructed exactly once in `run()`'s `.manage(SidecarState::new(...))` call. Nothing on the crash-detection, restart, or recovery paths (`run_crash_poll_loop`, `attempt_restart`, `handle_retry_eligible_failure`) ever constructs a new `EventSequencer` or resets the existing one's atomics — those paths only ever borrow `&state.events` |
| D. Safe allocation across execution contexts | `AtomicU64`/`AtomicU32` with `fetch_add(1, Ordering::SeqCst)`, a single indivisible hardware operation — safe whether called from the `setup` closure's thread, the crash-poll loop's thread, or the restart-scheduler's timer thread |
| E. Attached to the existing Part 2A payload | `StateChangedPayload::sequence: u64` (and `::generation: u32`), populated by `build_state_changed_payload` on every construction — already wired, not added by this checkpoint |
| F. Focused tests, independently and through the event adapter | Part 2A already shipped `sequence_is_strictly_increasing_across_emissions` and `generation_bumps_only_on_not_started_to_starting`; this checkpoint adds the remaining coverage (§F below) |

**Conclusion, per the task brief's own instruction:** no new sequence
authority was created. `EventSequencer` is reused as-is. This
checkpoint's actual work is (1) closing the specific test gaps Part 2A
itself documented as deferred, and (2) this document, formally
verifying and recording that the authority meets every Part 2B-1
requirement.

This is recorded as an **INFORMATIONAL** finding (§K), not a defect —
Part 2A's own module doc already described `EventSequencer` as "the
minimal foundation" for exactly this purpose, and the P3 architecture
document (§10.4) specified this single-`AtomicU64`-on-`SidecarState`
design in full before either checkpoint existed. Nothing here
contradicts either frozen document; this checkpoint confirms the
foundation Part 2A built already satisfies the contract Part 2B-1 was
asked to establish.

## D. Sequence Authority

**Type:** `EventSequencer { sequence: AtomicU64, generation: AtomicU32 }`,
`src-tauri/src/events.rs`.

**Ownership:** one instance, the `events` field of `SidecarState`
(`src-tauri/src/lib.rs`), constructed once via `EventSequencer::new()`
in the state's own constructor. No other `AtomicU64`/`AtomicUsize`/
counter in the repository serves this purpose — confirmed by a
repository-wide search (§J).

**Sequence type:** `u64`, an unsigned integer suitable for a
long-running desktop application's lifetime — no timestamp, UUID,
random number, PID, or memory address is used as a substitute,
matching the task brief §7's explicit prohibition.

**Initial value / numbering:** 1-based. `next_sequence()` returns
`fetch_add(1, ...) + 1`, so the first allocation of a fresh
`EventSequencer` is `1`, matching architecture doc §10.4/§27's
description of a real, monotonic counter with no stated 0-based
requirement; no implementation/document conflict was found (task
brief §8 — nothing to STOP and report here).

## E. Monotonicity and Lifetime

**Invariant:** `sequence(n+1) > sequence(n)`, enforced structurally —
`next_sequence()` is the only place either atomic is ever written
upward, and nothing anywhere resets `sequence` or `generation` to a
lower value or to zero after construction.

**Lifetime:** the counter lives exactly as long as the one
`SidecarState` instance Tauri manages for the life of the application
process — i.e., for the life of the *application*, not the life of
any one sidecar child-process episode. A sidecar crash, a restart
attempt (successful or failed), and a full recovery all reuse the same
`SidecarState`/`EventSequencer`; none of `run_crash_poll_loop`,
`attempt_restart`, or `handle_retry_eligible_failure` touch
`state.events` except to pass `&state.events` into `emit_state_changed`.
This was re-verified this session (§J: repository-wide search for any
second construction of `EventSequencer`, or any `.store(`/reset-shaped
call on its atomics — none found beyond the one constructor call).

## F. Thread-Safety

`AtomicU64::fetch_add`/`AtomicU32::fetch_add` under `Ordering::SeqCst`
is a single indivisible hardware read-modify-write — not a
load/increment/store sequence performed as separate unsynchronized
steps. Two concurrent callers therefore always observe two distinct
post-increment values (task brief §15's exact requirement). No new
`Mutex` was introduced for this purpose, and no second lifecycle mutex
was created — `EventSequencer`'s atomics are the only synchronization
primitive it owns, entirely separate from `SidecarState`'s existing
`Mutex<SidecarProcess>` (§F's requirement 14: "do not create a second
lifecycle mutex" — satisfied by construction, since the sequencer
never gates or blocks on lifecycle state at all).

## G. Event Integration

`StateChangedPayload.sequence: u64` and `.generation: u32` are
populated by `build_state_changed_payload` on every call, using the
one `EventSequencer` passed by reference from `SidecarState`. No
change was needed to the payload shape (already correct since Part
2A); no change was made to `emit_state_changed`'s signature or to any
of the twelve call sites in `lib.rs` — reuse, not redesign.

Sequence allocation happens only for a real, already-authoritative
transition being reported — never for a poll tick that found nothing
(`run_crash_poll_loop`'s `None` branch never reaches
`emit_state_changed`, unchanged from Part 2A), never for a health
check, and never for an internal log line. This was re-verified this
session by re-reading every `emit_state_changed` call site in `lib.rs`
(§J).

## H. Restart/Crash Behavior

Traced explicitly, this session, against the actual `lib.rs` call
sites:

- **Crash** (`run_crash_poll_loop`): `Running -> Crashed`, one
  `emit_state_changed` call, one `next_sequence()` allocation. No
  construction or reset of `EventSequencer` on this path.
- **Restart, success** (`attempt_restart`'s `Ok` arm): `reset()`
  (`<terminal> -> NotStarted`), then `start()`'s internal
  `NotStarted -> Starting -> Running` — three `emit_state_changed`
  calls, three further allocations, all against the same
  `&state.events` reference. `generation` bumps exactly once (the
  `NotStarted -> Starting` transition).
- **Restart, failure** (`attempt_restart`'s `Err` arm): same
  `reset()` + `Starting` emissions, then `Starting -> Failed`/
  `Starting -> Timeout` instead of `Running` — still the same
  `&state.events` reference; the failure path is not tied to any
  separate counter and does not reset the existing one.
- **Recovery**: not a distinct code path — a successful restart
  (above) *is* the recovery; `RUNNING` is reached exactly as during
  the initial launch, through the same `EventSequencer`.

No path constructs a second `EventSequencer`, and no path calls
anything that would zero either atomic. This is exactly the "sequence
30 → CRASHED → sequence 31 → STARTING" behavior the task brief's §10
worked example requires, and is now covered by an explicit test
(`sequence_survives_a_simulated_crash_and_restart_cycle_without_resetting`,
§I).

## I. Tests

All six requested test categories now exist in
`src-tauri/src/events.rs`'s `#[cfg(test)] mod tests`. Two
(sequential-increase, generation-bump-on-launch) were already present
from Part 2A; four are new this checkpoint, closing the gaps Part 2A's
own module doc explicitly named as deferred:

| # | Test | Status |
|---|---|---|
| 1 | First allocation matches the contract | Covered indirectly by every existing payload test (`sequence` is always populated from a fresh `EventSequencer` starting at 1); explicit uniqueness/ordering assertions below make this concrete |
| 2 | Sequential allocation strictly increasing | `sequence_is_strictly_increasing_across_emissions` (Part 2A, unchanged) |
| 3 | Uniqueness | **New:** `many_sequential_allocations_are_all_unique` — 1000 allocations from one sequencer, asserted pairwise-distinct via a `HashSet` |
| 4 | Concurrent allocation | **New:** `concurrent_allocations_are_unique_and_monotonic` — 8 threads × 200 allocations each directly against `next_sequence()`, asserts all 1,600 values are unique, the sorted set is the exact gap-free run `1..=1600`, and the count matches expectation exactly |
| 5 | No reset (crash/restart) | **New:** `sequence_survives_a_simulated_crash_and_restart_cycle_without_resetting` — drives the real `build_state_changed_payload` through two full crash→reset→restart→recover cycles on one `EventSequencer`, asserting strict increase throughout and correct `generation` bumps only on the two `NotStarted -> Starting` transitions |
| 6 | Event payload contains the sequence | **New:** `event_payload_carries_the_allocated_sequence` — asserts a real, representative (crash) payload's `sequence` field is populated and present in its serialized JSON form |

No test for deduplication, shutdown-race, stale-callback,
`restart_scheduled`, `restart_exhausted`, `get_sidecar_status`, or
frontend projection was added — all explicitly out of scope (task
brief §23).

No existing P2/P3 test was deleted, weakened, or rewritten. The two
Part 2A sequence/generation tests are unchanged; all of Part 2A's other
tests (payload construction, event name, transition mapping, forbidden
fields, RFC 3339 formatting, the `sidecar-core` Tauri-purity check) are
untouched.

## J. Static Verification (tooling unavailable, see §M)

Performed this session in place of a live `cargo test` run:

- **Repository-wide sequence-symbol search** (`grep -rn` for
  `AtomicU64|AtomicUsize|AtomicU32|sequence|SequenceAuthority`,
  excluding test-only fixture code): confirms exactly one production
  sequence authority (`events::EventSequencer`) exists.
  `sidecar-core/src/restart.rs`'s `NEXT_RESTART_TOKEN`/
  `NEXT_STABILITY_TOKEN` are a different, pre-existing, unrelated
  mechanism (single-flight restart/stability *token* issuance, not
  event sequencing — confirmed by reading their call sites, which
  never touch `StateChangedPayload`). `restart_scheduler.rs`'s several
  `AtomicUsize` instances are all inside `#[cfg(test)]` fixtures
  (call-counters for test doubles), not production code.
- **Sequence-authority ownership audit**: exactly one field
  (`SidecarState.events: EventSequencer`), exactly one constructor
  call (`EventSequencer::new()`, in `SidecarState`'s own constructor),
  confirmed by grep across `src-tauri/src/*.rs`.
- **Event payload audit**: `StateChangedPayload` unchanged from Part
  2A; `sequence`/`generation` fields present and populated on every
  construction path (only one, `build_state_changed_payload`).
- **Event call-site audit**: all twelve `emit_state_changed(...)`
  call sites in `lib.rs` re-read this session; each passes
  `&state.events` (the one instance), none constructs a new
  sequencer, none bypasses `build_state_changed_payload`.
- **Restart-reset audit**: `attempt_restart`, `handle_retry_eligible_failure`,
  `run_crash_poll_loop`, and the `RunEvent::Exit` handler re-read in
  full; none stores/resets either atomic or constructs a new
  `EventSequencer`.
- **Polling allocation audit**: `run_crash_poll_loop`'s `None` branch
  (nothing happened this tick) re-confirmed to never reach
  `emit_state_changed`/`next_sequence()` — unchanged from Part 2A.
- **Tauri-boundary audit**: `sidecar-core/Cargo.toml` re-confirmed to
  have no `tauri` dependency (also asserted by the pre-existing
  `sidecar_core_cargo_toml_has_no_tauri_dependency` test); `events.rs`
  remains the only file with `use tauri::Emitter;`.
- **Duplicate-counter audit**: no second `AtomicU64`/`Mutex`-protected
  counter serving an event-sequence purpose exists anywhere in
  `src-tauri` or `sidecar-core`.
- **Full recursive diff** against the uploaded Part 2A baseline
  (`SOC-IQ-Phase4E-P3-Part2A-COMPLETE-FULL-PROJECT.zip`): exactly one
  file differs, `src-tauri/src/events.rs` (test additions only — no
  change to `EventSequencer`, `StateChangedPayload`, or
  `build_state_changed_payload`/`emit_state_changed`'s logic). No
  other file, in any directory, was touched.
- **Manual brace/paren balance check** of the modified file (a
  string/comment-aware scanner, since the sandboxed environment has no
  Rust toolchain — see §M) found the file balanced with no stray or
  mismatched delimiters.

Specifically confirmed, per the task brief's own required findings:
only one sequence authority exists; no sequence reset is tied to
sidecar restart; no polling tick allocates a sequence; no frontend
sequence counter exists (frontend untouched, out of scope); no second
lifecycle authority was introduced.

## K. Environment Limitations

`cargo`/`rustc` are **not** available in this sandboxed environment
(confirmed: `which cargo`/`which rustc` both report not found), and
outbound network access to fetch a toolchain (e.g. via `rustup` or
`apt`) is disabled in this environment/session, unlike Part 2A's
session where `apt`-installed `rustc`/`cargo` 1.75.0 were reachable.

**Rust toolchain unavailable. cargo/rustc could not be executed.
Runtime compilation/test execution was not independently verified
this session.** Static verification (§J) was performed in its place,
and is reported separately from execution, per the task brief's own
instruction not to conflate the two. This limitation applies equally
to the four new tests added this checkpoint and to every pre-existing
test in the repository (`sidecar-core`'s 49-test suite included) —
none were re-executed this session; all were re-read.

## L. Files Changed

```text
Modified:
  src-tauri/src/events.rs
    - added four tests: many_sequential_allocations_are_all_unique,
      concurrent_allocations_are_unique_and_monotonic,
      sequence_survives_a_simulated_crash_and_restart_cycle_without_resetting,
      event_payload_carries_the_allocated_sequence
    - no change to EventSequencer, StateChangedPayload,
      build_state_changed_payload, emit_state_changed, or any
      non-test code in this file
    - no change to any existing test

Created:
  docs/phase4/PHASE4E_P3_PART2B1_SEQUENCE_AUTHORITY_IMPLEMENTATION.md
    - this document

Unchanged (confirmed by full recursive diff against the uploaded
Part 2A archive, §J): src-tauri/src/lib.rs, src-tauri/src/sidecar.rs,
src-tauri/src/restart_scheduler.rs, src-tauri/src/main.rs,
src-tauri/Cargo.toml, src-tauri/Cargo.lock, sidecar-core/ in its
entirety, frontend/ in its entirety, app/ in its entirety, every other
docs/ file including both frozen P3 documents.

Implementation source changes: 1 file (modified, tests only).
Documentation changes: 1 file (created).
Packaging source changes: 0.
```

## M. Frozen Checkpoint Verification

Confirmed intact this session by full recursive diff against the
uploaded `SOC-IQ-Phase4E-P3-Part2A-COMPLETE-FULL-PROJECT.zip`:

```text
P1                 unchanged
P2                 unchanged
P3 Part 1          unchanged
P3 Part 2A         unchanged (only src-tauri/src/events.rs differs,
                   and only its test module)
```

## N. Git

```text
$ git status
fatal: not a git repository (or any of the parent directories): .git
```

`.git` not present — Git metadata was not available and was not
fabricated, consistent with every prior checkpoint's identical
finding.

## O. Final Classification

**PASS WITH DOCUMENTED LIMITATION.**

The sequence authority required by this checkpoint's scope was found
to already exist, complete and correct, from Part 2A; it was reused,
not recreated, per the task brief's own §6 instruction. The specific
test gaps Part 2A itself documented as deferred (uniqueness at scale,
genuine multi-threaded concurrency, and an explicit no-reset-across-
restart scenario) are now closed. Runtime compilation/test execution
could not be independently verified this session because `cargo`/
`rustc` are unavailable and this environment has no network access to
fetch them (§K) — this is an environment limitation, not an
implementation defect, and static verification (§J) was performed in
its place and reported separately, per the task brief's own
instruction.

## P. Final Recommendation

Ready to proceed to **P3 Part 2B-2 — Previous-State Integrity + Event
Ordering**, on the same one `EventSequencer`/`sequence` field this
checkpoint verified and strengthened test coverage for. No further
sequence-authority work is needed before that checkpoint begins; Part
2B-2's own scope (previous-state hardening, event ordering) is a
consumer of the `sequence` values this authority already allocates
correctly, not a change to the authority itself.
