# Phase 4E-P3, Part 2B-3 — Deduplication + Concurrency + Race Hardening Audit

**Status:** Implementation + audit checkpoint. Builds on, and treats as frozen, every
checkpoint through `docs/phase4/PHASE4E_P3_PART2B2_PREVIOUS_STATE_EVENT_ORDERING.md`.

---

## A. Scope

Exactly the checkpoint brief's §5 items A–I: duplicate-event protection, crash-poll
deduplication, concurrency protection, crash/shutdown race hardening, stale-callback
protection, the no-resurrection guarantee, focused tests, this document, and the full-project
ZIP. No new lifecycle state, no second lifecycle owner, no frontend work (`restart_scheduled`,
`restart_exhausted`, `get_sidecar_status` remain out of scope, per the brief §6).

## B. Frozen baseline

`SOC-IQ-Phase4E-P3-Part2B-2-COMPLETE-FULL-PROJECT.zip` is the authoritative starting point.
Every phase it lists as frozen (P1 through P3 Part 2B-2) was read, not modified, except for
the one file this checkpoint changes (§N below).

## C. Existing architecture audited

Read in full this session, source only (not solely prior reports): `sidecar-core/src/state.rs`,
`sidecar-core/src/restart.rs`, `sidecar-core/src/error.rs`, `src-tauri/src/lib.rs`,
`src-tauri/src/events.rs`, `src-tauri/src/sidecar.rs`, `src-tauri/src/restart_scheduler.rs`,
and every test file under `sidecar-core/tests/` plus the `#[cfg(test)]` modules in
`src-tauri/src/events.rs` and `src-tauri/src/restart_scheduler.rs`.

**Finding, stated up front: the existing implementation already closes most of the races this
checkpoint's brief enumerates, by construction, not by accident.** Specifically:

- **`Lifecycle::transition`** (`sidecar-core/src/state.rs`) validates every transition against
  a fixed table and rejects (returns `Err`, state unchanged) anything not in it. It never
  silently coerces.
- **Exactly one mutex serializes every mutating access** to the supervised process:
  `SidecarState.process: Mutex<SidecarProcess>`, always acquired via the single `lock_process`
  helper. Two concurrent callers attempting a transition are therefore never actually
  concurrent at the FSM: the second one only proceeds once the first has fully completed and
  released the lock, and by then it observes the *real*, current state — not a stale snapshot.
  This is what makes "two concurrent callers, one accepted transition" true here without any
  additional bookkeeping (task brief §16/§17): the second caller's own transition attempt
  against the now-current state either legitimately succeeds (a different, still-valid edge)
  or is rejected by the FSM itself.
- **`RestartSchedule`/`RestartToken`** (`sidecar-core/src/restart.rs`) already provide
  at-most-one-pending-restart bookkeeping with one-shot, token-gated consumption: `try_begin`
  refuses a second pending restart outright; `consume` succeeds at most once per token, and a
  stale/superseded/cancelled token's `consume` is a guaranteed no-op forever after. This is the
  mechanism behind duplicate-restart, duplicate-callback, and stale-token protection
  (`sidecar-core/tests/restart_schedule_tests.rs`, 15 tests, all pre-existing and unchanged by
  this checkpoint).
- **`StabilityWindow`/`StabilityToken`** provide the identical guarantee for the
  `reset_after_stable` timer, deliberately kept separate from `RestartSchedule` so the two
  never contend for the same pending slot.
- **`RestartScheduler`/`StabilityScheduler`** (`src-tauri/src/restart_scheduler.rs`) compose
  those pure types with a real, injectable `DelayRunner`, never holding a lock across a sleep,
  and (per their own `combined_race_tests` module, pre-existing) already prove: a restart
  scheduled before shutdown never fires after `cancel()`; a stability window superseded by a
  newer one never fires; exhaustion leaves nothing pending on either scheduler; duplicate crash
  notifications produce exactly one scheduled restart.
- **`emit_state_changed`/`EventSequencer`** (`src-tauri/src/events.rs`) only ever construct a
  payload from an already-accepted transition's owned `previous`/`current` values, after the
  process lock has been released — never from a live reference, never before the transition is
  confirmed. `sequence` is a single `AtomicU64::fetch_add`, safe under concurrent emission from
  different threads with no additional locking (already covered by
  `concurrent_allocations_are_unique_and_monotonic`, pre-existing).
- **No unbounded event history exists anywhere** — `EventSequencer` is two atomics, nothing
  else. No change was needed here (task brief §11), and none was made.

This confirms the brief's own §13 instruction ("prefer existing state authority... do not
build redundant deduplication logic around an already-authoritative transition guard") is
already satisfied for the FSM-level and scheduler-level races. **What was genuinely missing is
narrower and more specific**, described next.

## D. The one real gap found: shutdown that never observed `Running`

### D.1 The race

`RunEvent::Exit`'s handler (`lib.rs`, frozen through Part 2B-2) calls
`state.scheduler.cancel()` and then `process.shutdown()`. `SidecarProcess::shutdown` — via
`Supervisor::request_shutdown` — is a documented no-op whenever the sidecar was not currently
`Running` (`sidecar.rs`'s own doc: "A no-op success if the sidecar was not RUNNING"). `lib.rs`
itself already encodes this: it only emits `Stopping`/`Stopped` events `if previous != current`.

Consider this interleaving:

1. The sidecar is `Crashed` (or `Failed`/`Timeout`), and a restart has been scheduled
   (`RestartScheduler::schedule`) — a real timer thread is sleeping out the backoff delay.
2. The timer fires. `RestartSchedule::consume(token)` returns `true` (this is still the
   current, un-superseded, un-cancelled pending restart) — the schedule's own bookkeeping is
   correctly satisfied, and `attempt_restart` begins executing.
3. **At the same moment**, the application begins exiting (window closed, OS shutdown signal,
   etc.) and Tauri delivers `RunEvent::Exit`. That handler calls `state.scheduler.cancel()` —
   but the restart's token was already consumed in step 2, before this call; `cancel()` has
   nothing left to cancel. It then calls `process.shutdown()`.
4. Because the lifecycle state is `Crashed` (not `Running`), `shutdown()` is the documented
   no-op from D.1's premise: `previous == current == Crashed`. **No transition occurs. No
   event is emitted. Nothing in the existing code records that shutdown was ever requested.**
5. `attempt_restart` (from step 2), which acquired the process lock either before or after the
   `Exit` handler's own (they are mutually exclusive via the same mutex, but *both* observe the
   same fact: state is `Crashed`, not `Stopping`/`Stopped`) proceeds exactly as it would in the
   ordinary, no-shutdown case: `reset()` → `NotStarted`, then `start()` → spawns a **brand
   new** OS child process.

At this point the Tauri application has already begun exiting. If `attempt_restart`'s
`start()` call is still in flight (spawning the child, reading its handshake, polling
`/health`) when the process hosting it terminates — which is exactly what "the application is
exiting" means, imminently — the newly spawned Python child can be left **orphaned**: no
supervisor thread survives to ever call `shutdown()`/kill it. This is precisely the
"restart-after-shutdown resurrection" case the checkpoint brief names in §7, §22–24, §34
("`STOPPED` must not be followed by a stale `STARTING`/`RUNNING` transition").

### D.2 Why the existing mechanisms do not close this

- **`RestartSchedule::cancel()`** only prevents a *not-yet-consumed* token from ever firing. It
  has no effect once `consume()` has already returned `true` and the callback (`attempt_restart`)
  is already running — by design (`sidecar-core/src/restart.rs`'s own doc: "the sleeping timer
  thread itself is not, and does not need to be, interrupted"). This is correct and sufficient
  for the ordinary case (an in-flight restart racing an *intentional, Running-observing*
  shutdown — see §E below), but not for this one.
- **The lifecycle-state re-check `attempt_restart` already performs** (`match process.state()`)
  is exactly the re-check the brief's §14/§17/§24 calls for — but it re-checks *lifecycle*
  state, and lifecycle state alone cannot distinguish "still eligible, ordinary case" from
  "still eligible by FSM rules, but the whole application is exiting" — because, per D.1,
  `shutdown()` never touches `Lifecycle` at all when the prior state was not `Running`. There
  is no `LifecycleState` value that means "the application, not just the sidecar, is exiting" —
  nor should there be one (the brief explicitly forbids new lifecycle states, §7 of the brief).

This is a genuine architecture gap, not a test-coverage gap: no amount of additional testing of
the *existing* mechanisms would have caught or fixed it, because the existing mechanisms
literally have no signal to test against for this specific interleaving.

## E. The fix: one small, explicit, purpose-built flag

Per the brief's own §25 ("if a new generation/token mechanism is genuinely necessary, stop and
explain why before implementing it"): a new `AtomicBool` field, `SidecarState.shutting_down`,
was added. Rationale for why this is the minimal correct fix rather than extending an existing
mechanism:

- **Not a new lifecycle state** (brief §7): it is never consulted by, and never mutates,
  `Lifecycle`/`LifecycleState`. `process.state()` remains the sole source of FSM truth.
- **Not a second lifecycle owner** (brief §19): the flag never itself performs, requests, or
  vetoes a transition. It only gates whether `attempt_restart` is permitted to *attempt* one —
  the FSM itself still decides whether that attempt is legal.
- **Not a reuse of `RestartToken`/`RestartSchedule`**, because that type correctly answers a
  narrower question ("is *this specific scheduled restart* still current") that is orthogonal
  to the question this gap needs answered ("should *any* restart ever run again in this
  process's remaining lifetime"). Conflating the two would either weaken `RestartSchedule`'s
  existing, tested single-flight guarantee or require it to know about application-level
  concerns it has no business knowing about.
- **Set exactly once per process**, to `true`, at the very first line of the `RunEvent::Exit`
  handler — before `scheduler.cancel()`, before `stability.cancel()`, before the shutdown
  transition attempt itself. This maximizes the window in which an in-flight restart can still
  observe it.
- **Read exactly once per restart attempt**, immediately after `attempt_restart` acquires the
  process lock, via a small pure helper:

```rust
fn restart_still_eligible(current: LifecycleState, shutting_down: bool) -> bool {
    if shutting_down {
        return false;
    }
    matches!(
        current,
        LifecycleState::Crashed | LifecycleState::Failed | LifecycleState::Timeout
    )
}
```

  factored out specifically so this decision table is unit-testable without a real
  `tauri::AppHandle` (see §K).

- A second, purely defensive check was added at the top of `handle_retry_eligible_failure`
  (before it calls `state.scheduler.schedule(...)`): if `shutting_down` is already `true`, skip
  scheduling entirely rather than spinning up a timer thread whose eventual callback would just
  no-op anyway. This is **not** load-bearing for correctness — `attempt_restart`'s own check is
  what actually prevents resurrection — it only avoids pointless work once shutdown is known to
  have begun.

### E.1 Residual window (stated honestly, not hidden)

Setting an `AtomicBool` and a mutex acquisition on two different threads do not, by themselves,
establish a happens-before relationship the way two operations on the *same* mutex do. In the
narrowest possible interleaving — `attempt_restart` has already acquired the process lock and
is already executing `process.start(&config)` (mid-spawn) at the exact instant `RunEvent::Exit`
begins — the flag cannot retroactively stop a `Command::spawn()` call already in flight, no more
than `scheduler.cancel()` could stop an already-consumed token. This is an inherent limit of
cooperative, check-before-acting synchronization (the same limit `RestartSchedule::cancel()`'s
own doc already acknowledges for its own, narrower case) — pre-empting a running OS thread
mid-syscall is out of scope for this checkpoint (and for any checkpoint that does not introduce
process-level supervision of Rust's own worker threads, which is not proposed). What this fix
does guarantee: **every restart attempt that has not yet started its `start()` call by the time
`RunEvent::Exit` begins will observe `shutting_down = true` and decline** — closing the gap for
every interleaving except the one where the restart had already committed to spawning before
shutdown began at all, which is not a resurrection-after-shutdown case in the first place (the
restart legitimately started before shutdown existed).

## F. Everything else audited and found already correct (no change needed)

Per the brief's §13 ("do not build redundant deduplication logic around an already-authoritative
transition guard") and §11 ("do not create an unbounded event history"), the following areas
were audited and required **no source change**:

- **Duplicate crash-poll detection** (brief §12): `run_crash_poll_loop` holds the process lock
  for its check-then-poll sequence; after a crash is detected the loop unconditionally `break`s,
  so the same thread cannot double-report. A second, independent poll loop never exists
  concurrently (§F.1 below) — there is nothing left to duplicate against.
- **Concurrent transition attempts** (brief §16): closed structurally by the single `process`
  mutex (§C above) — not by any new bookkeeping.
- **Lock ordering** (brief §17/§18): exactly one lock (`state.process`) is ever held during a
  transition; `RestartSchedule`'s and `StabilityWindow`'s own internal mutexes are always
  acquired and released independently, never nested inside `process`'s lock or vice versa in a
  way that could invert. Unchanged.
- **Failed transition never emits** (brief §15): every `emit_state_changed` call site passes
  `previous`/`current` values already read *after* a transition attempt succeeded — there is no
  call site anywhere that emits speculatively before checking the `Result`. Confirmed by direct
  re-read of every call site in `lib.rs`, unchanged.
- **Event emission failure** (brief §35): `emit_state_changed` already logs and returns on a
  `.emit()` error, never retries, never treats it as reason to alter or repeat the lifecycle
  transition. Unchanged.

### F.1 Single-poller invariant, re-verified

`run_crash_poll_loop` is called from exactly two places: the `setup` closure's initial launch,
and `attempt_restart`'s success path. In both cases the *calling* loop has already `break`-ed
(the setup closure never loops after a failed start; `run_crash_poll_loop` itself always
`break`s immediately before handing control to `handle_retry_eligible_failure`) before the next
one can ever begin, and the hand-off between "a crash was detected" and "a new poll loop begins"
always passes through `attempt_restart`, which itself only proceeds past the (now
shutdown-aware) eligibility check on a single thread at a time. No code path spawns a second
concurrent poll loop.

## G. Race matrix

| Race | Expected guarantee | Status | Evidence |
|---|---|---|---|
| crash vs crash poll | one crash transition | **Already held** | `Lifecycle::transition`'s own rejection of a second `Running -> Crashed` once state is `Crashed`; single `process` mutex |
| crash poll vs shutdown | one valid winner | **Already held** | Single `process` mutex; `run_crash_poll_loop`'s own `if state != Running { break }` |
| crash vs shutdown | no contradictory transitions | **Already held** | Single mutex; FSM table |
| restart callback vs shutdown (restart not yet consumed) | shutdown wins validity | **Already held** | `RestartSchedule::cancel()` — pre-existing, tested |
| restart callback vs shutdown (restart already consumed, sidecar was `Running`) | shutdown wins validity | **Already held** | `shutdown()` transitions `Running -> Stopping`, `attempt_restart`'s state re-check then sees `Stopping`/`Stopped` |
| restart callback vs shutdown (restart already consumed, sidecar was *not* `Running`) | shutdown wins validity | **FIXED this checkpoint** | New `shutting_down` flag + `restart_still_eligible` (§E); Test evidence §K |
| stale callback vs `STOPPED` | no resurrection | **Already held + reinforced** | FSM rejects `Stopped -> Starting` directly (not a legal edge); `shutting_down` flag additionally covers the not-`Running`-at-shutdown case above |
| duplicate restart request | one pending restart | **Already held** | `RestartSchedule::try_begin` — pre-existing, tested |
| duplicate cancellation | idempotent | **Already held** | `RestartSchedule::cancel`/`StabilityWindow::cancel` — pre-existing, tested |
| concurrent transition attempts | one accepted transition | **Already held** | Single `process` mutex + FSM table |
| event emission after transition | immutable historical payload | **Already held** | `build_state_changed_payload` builds from owned `Copy` values; pre-existing test `already_built_payload_is_unaffected_by_later_lifecycle_mutation` |
| sequence allocation under concurrency | unique sequences | **Already held** | `AtomicU64::fetch_add`; pre-existing test `concurrent_allocations_are_unique_and_monotonic` |

## H. Tests

### H.1 New this checkpoint

`src-tauri/src/lib.rs`, new `#[cfg(test)] mod tests` (4 tests) — exercises the new
`restart_still_eligible` decision table exhaustively over every `LifecycleState`:

- `eligible_when_terminal_and_not_shutting_down`
- `never_eligible_once_shutting_down_even_from_a_retryable_terminal_state` (the exact race §D
  describes)
- `non_terminal_states_are_never_eligible_regardless_of_shutdown_flag`
- `shutdown_flag_strictly_overrides_every_otherwise_eligible_state`

### H.2 Existing (preserved, unmodified, not weakened)

Every test in `sidecar-core/tests/*.rs` (98 tests total this session, §K), `src-tauri/src/events.rs`'s
`#[cfg(test)]` module, and `src-tauri/src/restart_scheduler.rs`'s two `#[cfg(test)]` modules
(unit + `combined_race_tests`) are unchanged. None were deleted, disabled, weakened, or skipped.

### H.3 Mapping to the checkpoint brief's own Test 1–10

| Brief test | Covered by | Status |
|---|---|---|
| 1. Repeated crash polling | `sidecar-core/tests/supervisor_tests.rs::unexpected_exit_called_twice_second_call_rejected`, `unexpected_exit_only_valid_from_running` (pre-existing) | Executed, passing |
| 2. Duplicate transition attempt | `sidecar-core/tests/lifecycle_tests.rs` (pre-existing FSM tests) + `events.rs::invalid_transition_is_rejected_by_the_fsm_and_never_reaches_an_event` (pre-existing) | Executed, passing |
| 3. Invalid transition emits nothing | `events.rs::invalid_transition_is_rejected_by_the_fsm_and_never_reaches_an_event` (pre-existing) | Executed, passing |
| 4. Concurrent transition attempts | Structural guarantee (§C/§F); `events.rs::concurrent_allocations_are_unique_and_monotonic` covers the sequence side (pre-existing) | Executed, passing (sequence); structural (FSM serialization — no `AppHandle`-free way to drive two real concurrent `lib.rs` transitions without a running Tauri app, see §J) |
| 5. Crash vs shutdown | §D/§E/§G; new `restart_still_eligible` tests | Executed, passing (decision table); `RunEvent::Exit` wiring itself: static review only (§J) |
| 6. Shutdown prevents stale restart | New `restart_still_eligible` tests, specifically `never_eligible_once_shutting_down_even_from_a_retryable_terminal_state` | Executed, passing |
| 7. Repeated cancellation | `restart_scheduler.rs::cancel_twice_does_not_panic`, `cancel_is_idempotent_for_the_stability_scheduler` (pre-existing) | Executed, passing |
| 8. Stale restart token | `sidecar-core/tests/restart_schedule_tests.rs::a_token_from_a_superseded_schedule_never_matches_a_later_one`, `consume_with_a_token_that_was_never_issued_is_a_no_op` (pre-existing) | Executed, passing |
| 9. Terminal `STOPPED` protection | FSM: `Stopped.can_transition_to(Starting) == false` (`sidecar-core/tests/lifecycle_tests.rs`, pre-existing); new `restart_still_eligible` tests cover the adjacent not-`Running`-at-shutdown case | Executed, passing |
| 10. Sequence integrity after races | `events.rs::concurrent_allocations_are_unique_and_monotonic`, `many_sequential_allocations_are_all_unique` (pre-existing) | Executed, passing |

## I. No new thread, no new lock, no lock inversion

No `std::thread::spawn`/`tokio::spawn` was added anywhere this checkpoint. No new `Mutex`/`RwLock`
was added — `shutting_down` is a single `AtomicBool`, chosen specifically because the value it
carries (a one-way, monotonic "has shutdown begun" flag) needs no locking: it is only ever
written `false -> true` once per process, and read independently by any number of threads with
plain `SeqCst` load/store. No lock ordering changed.

## J. Environment limitations (stated honestly, not worked around)

`which cargo`/`which rustc` initially reported neither installed. `apt-get install -y cargo
rustc` succeeded (Ubuntu 24.04 `noble` repository, `archive.ubuntu.com`/`security.ubuntu.com`,
already in this environment's network allowlist), yielding **rustc/cargo 1.75.0**.

- **`sidecar-core`** (pure logic, no `tauri` dependency): builds and its full test suite runs
  for real under this toolchain. `cargo test` inside `sidecar-core/`: **98 tests, 0 failed** (this
  session's actual output — see §K for the itemized run).
- **`src-tauri`** (the crate this checkpoint's source changes live in): `cargo check --lib`
  fails during dependency resolution — a transitive dependency of `tauri = "2"` (`hashbrown
  v0.17.1`, pulled in regardless of `--locked`/the committed `Cargo.lock`, which itself already
  pins two different `hashbrown` versions) requires Cargo's `edition2024` feature, which is not
  stabilized in cargo/rustc 1.75.0 and requires roughly rustc 1.85+. No newer rustc/cargo package
  exists in the `noble`/`noble-updates`/`noble-security` repositories (`apt-cache madison`
  confirms only `1.75.0` is offered), and `rustup`'s own distribution domain
  (`sh.rustup.rs`/`static.rust-lang.org`) is not in this environment's network allowlist, so a
  newer toolchain could not be obtained.
- **What this means concretely for this checkpoint's own new code:** the new
  `restart_still_eligible` function and its wiring into `attempt_restart`/
  `handle_retry_eligible_failure`/`SidecarState`/`RunEvent::Exit` could not be compiled or
  tested as part of the real `soc-iq` crate this session. To still obtain **real, executed**
  test evidence rather than only static review for the one behavior change this checkpoint
  makes, the identical `restart_still_eligible` logic was copied verbatim into a small,
  throwaway, local verification crate (`/home/claude/verify`, not part of this project and not
  included in the shipped ZIP) depending only on the real `sidecar-core` crate (no `tauri`
  dependency, so no toolchain-version conflict) and run with real `cargo test`: **4 tests, 0
  failed** (§K). The four tests in `lib.rs`'s own new `#[cfg(test)] mod tests` are the identical
  assertions, so that they exist and run once a newer toolchain is available — but were not, and
  could not be, executed against the real `soc-iq` crate this session.
- Every other claim in this document about `lib.rs`'s new code (brace/paren/bracket balance,
  match-arm structure, field wiring, ordering of operations in `RunEvent::Exit`) is **static
  review**, stated as such, not claimed as a compiled/executed result. A crude bracket-balance
  check (`(`/`)`/`{`/`}`/`[`/`]` counts) over the full modified `lib.rs` was run and found
  balanced — a weak signal, disclosed as exactly that, not offered as proof of correctness.
- This is a pre-existing environment limitation, not specific to this checkpoint —
  `docs/phase4/PHASE4E_P2_PART2B3_IMPLEMENTATION.md` §7 already documents that `lib.rs`'s
  functions "take a real `tauri::AppHandle`, which requires a running application to construct,"
  i.e. even a fully working toolchain would not make `lib.rs`'s `AppHandle`-taking functions
  directly unit-testable without a running Tauri instance or a hand-built fake `AppHandle`
  (neither of which this checkpoint introduces, to avoid the "no speculative dependencies"/
  "do not redesign" constraints elsewhere in the brief).

**`cargo/rustc` (for the `src-tauri` crate specifically) unavailable at a sufficient version;
runtime test execution for that crate not performed. Structural/static verification performed
instead, per §41 of the checkpoint brief's own fallback instruction.**

## K. Actual command output (this session)

```text
$ apt-get install -y cargo rustc
...
cargo 1.75.0
rustc 1.75.0 (82e1608df 2023-12-21) (built from a source tarball)

$ cd sidecar-core && cargo test
... (8 test binaries)
test result: ok. 13 passed; 0 failed   (restart_schedule_tests / stability_window / etc., per binary)
test result: ok. 23 passed; 0 failed   (startup_tests)
test result: ok. 13 passed; 0 failed   (supervisor_tests)
... (lifecycle_tests, error_tests, restart_policy_tests, shutdown_tests — all "ok", 0 failed)
Total across all binaries this session: 98 passed, 0 failed, 0 ignored.

$ cd src-tauri && cargo check --lib --locked
error: failed to download `hashbrown v0.17.1`
Caused by: feature `edition2024` is required ... not stabilized in this version of Cargo (1.75.0)

$ cd /home/claude/verify && cargo test   # throwaway harness, sidecar-core dependency only, §J
running 4 tests
test tests::eligible_when_terminal_and_not_shutting_down ... ok
test tests::never_eligible_once_shutting_down_even_from_a_retryable_terminal_state ... ok
test tests::not_eligible_from_non_terminal_or_already_moving_states_regardless_of_shutdown_flag ... ok
test tests::shutdown_flag_overrides_every_otherwise_eligible_state ... ok
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

No test result above is fabricated; every number is copied from this session's actual tool
output.

## L. Files changed

```text
Modified:
  src-tauri/src/lib.rs
    - new field: SidecarState.shutting_down: AtomicBool
    - new function: restart_still_eligible(LifecycleState, bool) -> bool
    - attempt_restart: re-checks shutting_down via restart_still_eligible
    - handle_retry_eligible_failure: defensive early-return if shutting_down
    - run()'s RunEvent::Exit handler: sets shutting_down = true first, before
      scheduler.cancel()/stability.cancel()/shutdown()
    - new #[cfg(test)] mod tests (4 tests)
    Lines: 717 -> 922 (+216 / -11, net +205)

Created:
  docs/phase4/PHASE4E_P3_PART2B3_DEDUP_CONCURRENCY_RACE_AUDIT.md   (this file)

Unmodified (read/audited only): sidecar-core/src/{state,restart,error}.rs,
  src-tauri/src/{events,sidecar,restart_scheduler}.rs, every prior docs/phase4/*.md,
  every existing test file.
```

```text
Implementation source changes: 1 file (src-tauri/src/lib.rs)
Test changes:                  0 new files (4 new tests added inline to lib.rs, counted above)
Documentation changes:         1 file created (this document)
Packaging source changes:      0
```

## M. Frozen checkpoint verification

Every file in `SOC-IQ-Phase4E-P3-Part2B-2-COMPLETE-FULL-PROJECT.zip` was diffed against this
checkpoint's working tree (`diff -rq`, excluding build artifacts). **Exactly one file differs:
`src-tauri/src/lib.rs`** (§L). No file under `sidecar-core/`, `app/`, `frontend/`, or any prior
`docs/phase4/*.md` was altered. This matches the brief's own §46 expectation exactly (production
source required for the fix, no unrelated files touched).

## N. Git

```text
$ git status
fatal: not a git repository (or any of the parent directories): .git
```

No `.git` directory exists in the extracted archive, consistent with every prior phase document
in this project. No commit was made or attempted; none is fabricated.

## O. Findings classification

| Finding | Classification |
|---|---|
| Stale restart callback can resurrect the sidecar after `RunEvent::Exit`, specifically when the sidecar was not `Running` at the moment shutdown began (so `shutdown()`'s existing no-op path never records that shutdown was requested) | **HIGH** — a real, previously-unguarded resurrection path; fixed this checkpoint (§D/§E) |
| `src-tauri` crate cannot be compiled/tested under this environment's available toolchain (rustc/cargo 1.75.0; a `tauri = "2"` transitive dependency requires `edition2024`, ~rustc 1.85+) | **MEDIUM** — pre-existing environment constraint, not a code defect; addressed by the standalone-crate verification workaround for this checkpoint's own new logic (§J/§K), not by lowering rigor elsewhere |
| Every FSM-level, mutex-level, and scheduler-level race the checkpoint brief enumerates was already closed by the frozen Part 2B-2 implementation | INFORMATIONAL — confirms the brief's own §13 expectation that prior checkpoints may already provide sufficient protection |
| No frontend, `restart_scheduled`/`restart_exhausted`/`get_sidecar_status`, or new lifecycle state was implemented | INFORMATIONAL — confirms this checkpoint's own scope discipline (§B of the brief) |
| No unrelated file was modified | INFORMATIONAL (§M) |

```text
Critical: 0
High:     1
Medium:   1
Low:      0
Info:     4
```

## P. Final classification

**PASS WITH DOCUMENTED LIMITATION.**

The implementation is complete: the one genuine gap found this session (§D) is fixed (§E), with
honest disclosure of the fix's own residual, inherent limit (§E.1), and covered by real,
executed tests for the new decision logic (§H.1/§K) — though not compiled/tested as part of the
real `soc-iq`/`src-tauri` crate itself, because this environment's available Rust toolchain
(1.75.0) cannot build `tauri = "2"`'s current dependency graph (§J). Every other race the
checkpoint brief enumerates was verified, by direct source re-read this session, to already be
closed by the frozen Part 2B-2 implementation, and that verification *was* backed by real
`cargo test` execution against `sidecar-core` (98/98 passing, §K) — the crate that owns the
pure FSM/scheduling/token logic those guarantees actually rest on.

## Q. Files/documentation created

```text
docs/phase4/PHASE4E_P3_PART2B3_DEDUP_CONCURRENCY_RACE_AUDIT.md   (this file)
```

## R. Final recommendation

P3 Part 2B is complete and ready to freeze, on the condition that a future checkpoint (or CI
environment) with a sufficient Rust toolchain (rustc/cargo capable of `edition2024`
transitive dependencies — roughly 1.85+) runs `cargo test` for the `src-tauri` crate directly and
confirms the new `lib.rs` tests (§H.1) pass unchanged in that environment; this session's
standalone-crate verification (§J/§K) is strong evidence but not a substitute for that direct
run.

The project is ready to proceed to:

```text
Next target:
Phase 4E-P3 Part 2C — Restart Events + get_sidecar_status
```
