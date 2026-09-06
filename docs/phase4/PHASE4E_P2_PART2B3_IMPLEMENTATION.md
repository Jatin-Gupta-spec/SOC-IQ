# Phase 4E-P2, Part 2B-3 — Recovery + Exhaustion

**Status:** PASS WITH DOCUMENTED LIMITATION (no Rust toolchain available in
this sandbox — structural/static verification performed instead; see §6).

Builds on: `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`
(the architecture/decision document, authoritative per its own checkpoint
chain), `docs/phase4/PHASE4E_P2_PART2B2_IMPLEMENTATION.md` (restart
scheduling + backoff, unchanged in behavior by this checkpoint),
`sidecar-core/src/restart.rs`'s `RestartPolicy`/`RestartTracker` (Part
2B-1, unchanged) and `RestartSchedule`/`RestartToken` (Part 2B-2,
unchanged).

---

## 0. Discrepancy found and resolved (read this first)

The task brief this checkpoint was given (§ "Final directive" and §19
"Terminal FAILED state" / §37 "State-machine audit") illustrates the
completed lifecycle with a literal transition:

```text
CRASHED
   ↓
RestartPolicy/Tracker
   ↓
   ...
exhausted
   ↓
FAILED
```

Read literally, this asks for a `sidecar-core::LifecycleState` transition
from `Crashed` (or `Timeout`) to `Failed` on exhaustion. That transition
does not exist in `state.rs`'s transition table, and the architecture
document — which this checkpoint's own instructions name as authoritative
or say to "STOP and report" against if it disagrees — is explicit that no
such transition should be added:

- §5 ("State Machine"): "the existing 8-state `LifecycleState` enum and
  its transition table are reused unchanged... No FSM change is required
  or proposed" — and explicitly evaluates and rejects adding a
  `RESTARTING`-shaped state for exactly this reason.
- §6.5 ("Restart exhaustion"): "`RESTARTING → FAILED` (in the
  **synthesized-status sense** of §5/§13, **not a new core-FSM
  transition**) occurs when the bounded attempt counter is exhausted...
  the `Lifecycle` FSM is left in its already-correct terminal `CRASHED`
  (or `FAILED`/`TIMEOUT`) state."
- §12 ("GUI/Application Contract"): "Failed" is listed as a
  **consumer-facing label**, derived from events — not a `LifecycleState`
  variant.

Per the task brief's own §2 ("If the implementation and architecture
materially disagree: STOP and report the discrepancy before improvising")
and its own precedent (Part 2B-2 hit an analogous discrepancy — an
undefined `RestartSchedule` type two orphaned files assumed existed — and
resolved it by reporting, then implementing per the architecture's own
design rather than the illustrative shape), this checkpoint resolves the
same way: **the architecture document's decision governs.** `FAILED` as
used throughout this checkpoint (this document, log messages, doc
comments) refers to the *synthesized* external status "sidecar
unavailable" that a future consumer derives from the event stream
(architecture §12) — never a new `sidecar-core::LifecycleState::Failed`
transition invented from a state other than `Starting`/`Stopping`.
`state.rs` is untouched by this checkpoint (confirmed — see §5).

No other discrepancy was found. Everything else in the task brief (owning
the recovery/retry/exhaustion behavior, not the readiness definition, not
implementing frontend/UI work, reusing the existing scheduler, no second
supervisor, no double-counting, race protection, honest test reporting)
matches the architecture document directly and was implemented as asked.

---

## 1. What this checkpoint adds

Two independent pieces, both driven by the same single `SidecarState`
(§4 of the architecture doc — no second lifecycle owner):

1. **`reset_after_stable` (§7.5).** Every successful `RUNNING` episode —
   the initial launch or a successful automatic restart — now begins a
   real 60-second `StabilityScheduler` window. If the sidecar is *still*
   `RUNNING` when that window elapses, the restart-attempt counter
   resets to zero. A crash, a failed restart, or an intentional shutdown
   cancels the window first, so a stale stability check can never erase
   real crash history for an episode that has already ended (task brief
   §27).
2. **`SIDECAR_RESTART_EXHAUSTED` (§11).** A new `SidecarError::RestartExhausted`
   variant, with the stable code `SIDECAR_RESTART_EXHAUSTED`, is used
   (via its `.code()`/`Display`) at the exact point
   `RestartTracker::decide` first reports `RestartDecision::Exhausted`
   for the current crash-loop window. The frontend-facing `{code,
   message}` contract for `get_sidecar_origin`/Tauri events remains
   deferred (§4, below) — only the error variant and its use in logging
   are in this checkpoint's scope.

---

## 2. Recovery implementation

**Restart attempt → startup → readiness → successful recovery → tracker
reset**, exactly the sequence the task brief's §7 asks for:

- **Restart attempt**: unchanged from Part 2B-2 — `attempt_restart()`
  re-checks `LifecycleState` after acquiring the process mutex, calls
  `SidecarProcess::reset()` then `SidecarProcess::start()` only if the
  state is still `Crashed`/`Failed`/`Timeout`.
- **Startup / readiness**: unchanged — `SidecarProcess::start()`'s
  existing sequence (spawn, handshake, poll `/health` until success or
  timeout) is the sole readiness definition, exactly as the task brief
  §6 requires ("recovery is NOT process started... use the exact
  readiness definition already established"). This checkpoint adds
  nothing to that sequence and does not touch `sidecar.rs`'s `start()`.
- **Successful recovery**: `process.start()` returning `Ok(())` is what
  the architecture already treats as `STARTING → RUNNING` (via
  `Supervisor::health_check_succeeded()`, unchanged). At that point (both
  in `run()`'s `setup` closure for the initial launch, and in
  `attempt_restart()` for a retry) this checkpoint now calls
  `begin_stability_window()` before resuming `run_crash_poll_loop()`.
- **Tracker reset (§7/§8/§9 of the task brief)**: happens **only** when
  `confirm_stability_if_still_running()` — the action a `StabilityScheduler`
  timer invokes after `reset_after_stable` (60s) has genuinely elapsed
  *and* this specific window was not superseded/cancelled — re-checks
  `LifecycleState` one more time and finds it still `Running`. Not reset
  immediately on spawn, not reset on `start()` returning `Ok`, not reset
  on any other event — exactly the `reset_after_stable` semantics the
  architecture doc §7.5 and the task brief §9 both specify. If the
  process is not still `Running` when the window fires (should not
  happen given the cancellation discipline in §3 below, but checked
  anyway per task brief §24), the reset is skipped and logged, not
  performed blindly.
- **Clearing pending state**: after a successful restart, `RestartSchedule`'s
  own token was already consumed by `RestartScheduler`'s wrapper before
  `attempt_restart()` was even invoked (Part 2B-2, unchanged) — no
  orphaned restart schedule exists. No new orphan class is introduced by
  the stability window either (see cancellation discipline, §3).

---

## 3. Failure/retry implementation

Unchanged from Part 2B-2 in its own logic — `handle_retry_eligible_failure()`
is still the single call site for `RestartTracker::decide()` /
`record_attempt()`, reached from exactly the same two paths (initial
startup failure, runtime crash via `run_crash_poll_loop`) plus a third
that already existed (a failed restart attempt inside `attempt_restart()`).
This checkpoint's only change to that function is adding one line at the
top:

```rust
state.stability.cancel();
```

— unconditionally, before the policy is even consulted. This is required
because a retry-eligible failure always means the `RUNNING` episode (if
any) that preceded it is over; without this, a stability window begun by
an earlier successful start/restart could still be sitting pending when a
*new* failure occurs, and could later fire and incorrectly reset the
tracker for a crash-loop episode that has already resumed accumulating
attempts (task brief §27: "a failed restart must not erase the crash
history"). The cancel is a no-op — safe, idempotent — when no window was
pending (e.g. the very first startup failure, before any `RUNNING` episode
has ever occurred).

- **Spawn failure / startup timeout / handshake failure / readiness
  (health-check) failure**: all four already flow into the same
  `Err(err)` arm (initial launch) or the same `Err(err)` arm
  (`attempt_restart`), both already calling `handle_retry_eligible_failure()` —
  unchanged by this checkpoint. None of them transitions to `Running`;
  `SidecarError`'s existing variant distinctions
  (`SpawnFailure`/`StartupTimeout`/`HandshakeFailure`/`HealthCheckFailure`)
  are preserved end to end (nothing in this checkpoint flattens them —
  they are logged via `{err}`'s `Display`, which is variant-specific).
- **Retry decision / scheduler reuse**: unchanged — `RestartTracker::decide()`
  → (`Retry`) `record_attempt()` → `RestartScheduler::schedule()` (the
  same real timer Part 2B-2 built) → the timer's action is
  `attempt_restart()`. No second timer, no second retry path.

---

## 4. Exhaustion implementation

- **Final-attempt semantics**: unchanged from Part 2B-1/2B-2 —
  `RestartTracker::decide()` returns `Exhausted { attempts }` exactly at
  `self.attempts >= policy.max_attempts` (i.e. after the 5th recorded
  retry), never earlier, never later; boundary tests for this already
  exist in `sidecar-core/tests/restart_policy_tests.rs` (Part 2B-1,
  untouched).
- **Transition to "FAILED"**: per §0 above, this is the *synthesized*
  external status, not a new `LifecycleState` transition. The `Lifecycle`
  FSM is left in whichever terminal state (`Crashed`/`Failed`/`Timeout`)
  it was already in when the last retry attempt failed — unchanged,
  `state.rs` untouched.
- **`SIDECAR_RESTART_EXHAUSTED`**: `handle_retry_eligible_failure()`'s
  `Exhausted` arm now constructs `SidecarError::RestartExhausted { attempts }`
  and logs its `.code()` (`SIDECAR_RESTART_EXHAUSTED`) and `Display`
  message, rather than the previous ad hoc string. This is the exact code
  name the architecture doc §11 specifies — no substitute
  (`RESTART_FAILED`/`RESTART_LIMIT`/`CRASH_LOOP`/`SIDECAR_FAILED`) was
  used.
- **Cancellation of pending restart**: on the `Exhausted` path, nothing
  is ever scheduled on `RestartScheduler` (the function returns without
  calling `schedule()`), and the stability window was already cancelled
  unconditionally at the top of the function (§3) — so both timers are
  guaranteed empty once exhaustion is reached.
- **Prevention of further automatic restart**: structural, not a flag —
  the only caller of `RestartScheduler::schedule()` is
  `handle_retry_eligible_failure()`'s `Retry` arm; the `Exhausted` arm
  never reaches it. No stale timer exists to resurrect the sidecar (see
  §5, Race F/G).

---

## 5. Race-condition protection

| Race (task brief §33) | Protection | Verified by |
|---|---|---|
| A. Crash + shutdown | `RunEvent::Exit` cancels `scheduler` then `stability` before calling `shutdown()`; both cancels are idempotent no-ops if a crash raced in first and already consumed/cancelled them. Same single `process` mutex ordering the architecture doc §9 already relies on for this class of race. | Existing `restart_schedule_tests.rs` (Part 2B-2) + new `shutdown_while_a_restart_is_pending_cancels_it_before_it_can_fire` (this checkpoint). |
| B. Scheduled restart + shutdown | Same as A — `scheduler.cancel()` guarantees a pending restart's token can never later `consume()` successfully once cancelled, even if its real timer fires afterward. | `shutdown_while_a_restart_is_pending_cancels_it_before_it_can_fire`. |
| C. Stale callback (old scheduling identity, new lifecycle) | `RestartToken`/`StabilityToken` are both process-wide, monotonic, and single-use via `consume`/`confirm` — a token from a superseded or cancelled schedule/window can never succeed again. `attempt_restart()`/`confirm_stability_if_still_running()` both additionally re-check `LifecycleState` itself, a second independent layer. | `a_token_from_a_superseded_schedule_never_matches_a_later_one` (Part 2B-2, unchanged) + new `stability_window_tests.rs` (`a_token_from_a_superseded_window_never_confirms_the_later_one`, `a_cancelled_tokens_later_confirm_is_a_no_op`). |
| D. Duplicate crash | `poll_for_crash()`'s existing `self.child = None` on first observed exit (unchanged since Part 2A) means a second poll is already a no-op before `handle_retry_eligible_failure()` is even reached a second time for the same exit. At the scheduler level, a second `schedule()` call while one is pending is rejected outright. | Existing `a_second_schedule_call_while_one_is_pending_is_rejected` + new `duplicate_crash_handling_schedules_one_restart_and_idempotently_cancels_stability`. |
| E. Duplicate recovery | `RUNNING` is declared exactly once per `start()` call (synchronous, no separate async "recovery callback" exists in this codebase to duplicate — see architecture doc §9 Race D/E's same reasoning). `begin_stability_window()` is called from exactly the two call sites that can observe a successful `start()`, once each. | New `a_superseded_stability_window_never_fires_even_if_its_timer_wakes_after_a_newer_one` (proves the underlying token mechanism is duplicate-safe even in the hypothetical case two "recoveries" did race). |
| F. Exhaustion + late readiness | Not reachable under this design: `start()` is synchronous — there is no separate readiness callback that could arrive "late" relative to the exhaustion decision, which itself is only computed after a `start()` call has already returned `Err`. | New `after_exhaustion_neither_scheduler_has_anything_pending_to_fire` documents the resulting invariant (nothing pending on either timer once exhaustion is reached, so nothing can race to resurrect it). |
| G. Crash during restart | A crash observed while a *new* stability window is pending (i.e., a restart just succeeded and then crashed again quickly) cancels that window via the same unconditional `state.stability.cancel()` in `handle_retry_eligible_failure()`. | New `a_crash_during_the_stability_window_cancels_it_before_it_can_fire`. |

---

## 6. Tests

**Rust toolchain unavailable in this sandbox** — `which cargo` / `which
rustc` both report nothing, and no `.cargo/bin` directory exists. This
matches every prior Phase 4 Rust checkpoint in this project. No `cargo
test` was run, and no test-count number below is fabricated.

**Executed:**

```text
$ pip install --break-system-packages -q pytest pytest-qt PySide6
$ pip install --break-system-packages -q -r requirements.txt
$ python3 -m pytest tests/ -q --ignore=tests/gui
  600 passed, 1 warning in 4.35s
```

600 passed — matches the documented baseline exactly (unchanged from
Part 2B-1/2B-2's own re-confirmations). No Python file was touched by
this checkpoint, so this is a non-regression confirmation, not new
coverage; it was re-run anyway per the task brief's own §35 instruction
to run the regression suite before claiming completion.

**Not executed (and not claimed to have been):** `cargo test -p
sidecar-core`, `cargo test -p soc-iq` (the `src-tauri` crate), any
real-time-based test, any real killed-mid-run-process integration test,
any `vitest`/frontend test (no frontend file was touched).

**Structural/static verification performed instead:**

- Brace/paren/bracket balance checked on every edited/created Rust file
  (`error.rs`, `restart.rs`, `lib.rs` (sidecar-core),
  `stability_window_tests.rs`, `error_tests.rs`, `restart_scheduler.rs`,
  `lib.rs` (src-tauri)) — all balanced.
- Confirmed by direct grep: `RestartTracker::record_attempt` has exactly
  one call site in `src-tauri/src/lib.rs` (line 380, inside
  `handle_retry_eligible_failure`'s `Retry` arm) — unchanged from Part
  2B-2, proving this checkpoint introduces no double-counting.
- Confirmed by direct grep: exactly one `struct Supervisor`, exactly one
  `struct SidecarState`, exactly one `struct SidecarProcess` in the
  entire source tree — no second lifecycle owner was introduced.
- Confirmed `sidecar-core/src/state.rs` was not modified by this
  checkpoint (git-free archive, so confirmed by direct re-read against
  the Part 2B-2 baseline copy rather than `git diff` — content is
  byte-for-byte the transition table already documented in the
  architecture doc §5).
- Every new `std::thread`/timer call site
  (`StabilityScheduler`'s production path, reusing the existing
  `ThreadDelayRunner`) was traced: it is the *same* `DelayRunner`
  abstraction and production implementation `RestartScheduler` already
  used, not a new timer mechanism — no new thread-spawning primitive was
  introduced.
- New tests added and read line-by-line against their own assertions
  (no execution possible, so each was hand-traced against the
  implementation it exercises):
  - `sidecar-core/tests/stability_window_tests.rs` — 13 cases covering
    `StabilityWindow`'s fresh state, begin/confirm, single-confirm-only,
    unknown-token no-op, supersession, cancellation (including
    idempotence and post-cancel no-op confirm), and fresh-window-after-cancel.
  - `sidecar-core/tests/error_tests.rs` — 2 new cases (the
    `RestartExhausted` code and its message content), appended to the
    existing per-variant code table without altering any existing case.
  - `src-tauri/src/restart_scheduler.rs` — 8 new `StabilityScheduler`
    unit tests (mirroring `RestartScheduler`'s existing test shape:
    pending state, delay recording, fire timing, supersession,
    cancellation idempotence, post-cancel re-begin, timer-creation
    failure) plus a new `combined_race_tests` module (5 tests) composing
    both scheduler types together to reproduce the task brief §33
    scenarios (§5 above).

---

## 7. Files changed

| File | Purpose |
|---|---|
| `sidecar-core/src/error.rs` | Added `SidecarError::RestartExhausted { attempts }` → `"SIDECAR_RESTART_EXHAUSTED"`. No existing variant changed. |
| `sidecar-core/src/restart.rs` | Added `StabilityToken`/`StabilityWindow` (pure pending-stability-window bookkeeping, same shape as the existing `RestartToken`/`RestartSchedule`). `RestartPolicy`/`RestartTracker`/`RestartSchedule`/`RestartToken` (Parts 2B-1/2B-2) unchanged — only new, additive code appended. |
| `sidecar-core/src/lib.rs` | Exported `StabilityToken`/`StabilityWindow`; added a Part 2B-3 module-doc note (including the §0 discrepancy resolution). |
| `sidecar-core/tests/stability_window_tests.rs` | New — 13 tests for `StabilityWindow`. |
| `sidecar-core/tests/error_tests.rs` | Added 2 tests for `SidecarError::RestartExhausted`. |
| `src-tauri/src/restart_scheduler.rs` | Added `StabilityScheduler<R>` (composes `StabilityWindow` with the existing `DelayRunner`/`ThreadDelayRunner`), its unit tests, and a `combined_race_tests` module exercising `RestartScheduler` + `StabilityScheduler` together against the task brief §33 scenarios. `RestartScheduler`/`RestartSchedule` (Part 2B-2) unchanged. |
| `src-tauri/src/lib.rs` | `SidecarState` grew a `stability: StabilityScheduler` field; added `begin_stability_window()` and `confirm_stability_if_still_running()`; both success paths (`run()`'s `setup` closure and `attempt_restart()`) now call `begin_stability_window()`; `handle_retry_eligible_failure()` now cancels `state.stability` unconditionally at its top and logs exhaustion via `SidecarError::RestartExhausted`; `RunEvent::Exit` now also cancels `state.stability`, alongside the existing `state.scheduler.cancel()`. |
| `docs/phase4/PHASE4E_P2_PART2B3_IMPLEMENTATION.md` | This file, new. |

No other file was modified. `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`
(the architecture document itself) and
`docs/phase4/PHASE4E_P2_PART2B2_IMPLEMENTATION.md` were read, not edited.

---

## 8. Frozen checkpoint verification

- **Phase 4E-P1**: untouched.
- **Phase 4E-P2 Part 1** (architecture doc): untouched (read only). Its
  §5/§6.5 decision (no core-FSM change for exhaustion) is what this
  checkpoint follows in place of the task brief's own illustrative
  diagram (§0).
- **Phase 4E-P2 Part 2A** (crash detection wiring): `poll_for_crash()`'s
  call site and behavior in `run_crash_poll_loop()` are unchanged —
  still detects a crash and hands off to `handle_retry_eligible_failure()`,
  itself unchanged from Part 2B-2 except the one added `stability.cancel()`
  line at its top.
- **Phase 4E-P2 Part 2B-1** (`RestartPolicy`/`RestartTracker`): zero
  lines inside `impl RestartPolicy`/`impl RestartTracker` were changed.
- **Phase 4E-P2 Part 2B-2** (`RestartSchedule`/`RestartToken`/`RestartScheduler`/
  `DelayRunner`/`ThreadDelayRunner`): zero lines inside any of those
  existing `impl` blocks were changed; the real scheduler for *restarts*
  is reused exactly as built, not reimplemented or duplicated.

---

## 9. Git

```text
$ ls -la .git
ls: cannot access '.git': No such file or directory
```

No `.git` directory exists in the extracted archive — consistent with
every prior phase document in this project. No commit was made or
attempted.

---

## 10. Pass criteria assessment

| Criterion (task brief §45) | Met? |
|---|---|
| Successful restart reaches the existing readiness definition | Yes — unchanged `start()` sequence, not touched by this checkpoint |
| Successful recovery reaches `RUNNING` | Yes — unchanged (`health_check_succeeded()`) |
| Tracker resets only at the correct recovery point | Yes — `StabilityScheduler` (60s continuous `RUNNING`, re-checked at fire time), never on spawn/start alone |
| Failed restart does not falsely reach `RUNNING` | Yes — unchanged; `Err` from `start()` always routes to `handle_retry_eligible_failure()` |
| Retry goes through the existing scheduler | Yes — `RestartScheduler`, zero changes to its own logic |
| Attempts are not double-counted | Yes — `record_attempt()` has exactly one call site, confirmed by grep |
| Exhaustion is correctly detected | Yes — unchanged `RestartTracker::decide()` boundary (Part 2B-1, already tested) |
| `SIDECAR_RESTART_EXHAUSTED` is correctly represented | Yes — new `SidecarError::RestartExhausted`, exact code name, used exactly once at the exhaustion boundary |
| Exhausted lifecycle reaches the correct terminal state | Yes, per §0's resolved reading — the already-correct existing terminal state (`Crashed`/`Failed`/`Timeout`); "FAILED" is the synthesized status per the authoritative architecture doc |
| No automatic restart occurs after exhaustion | Yes — structural; `Exhausted` arm never calls `schedule()` |
| No automatic restart occurs after intentional shutdown | Yes — unchanged from Part 2B-2, plus the new stability-window cancel alongside it |
| Stale callbacks cannot resurrect an old lifecycle | Yes — token identity (both `RestartToken` and the new `StabilityToken`) + lifecycle-state re-check, two independent layers each |
| Duplicate callbacks are safe | Yes — `consume`/`confirm` are exactly-once by construction |
| Race tests cover the critical paths | Yes, at the unit/combined-scheduler level (§5/§6) — no real-time/Tauri-integration race test was run (toolchain unavailable) |
| No second supervisor/process owner exists | Yes — confirmed by static grep audit (§6) |
| No unrelated architecture redesign occurred | Yes — every changed file is either the §0 discrepancy resolution or direct recovery/exhaustion wiring |
| Complete ZIP is produced and verified | See the delivered archive and its accompanying message |

**Classification: PASS WITH DOCUMENTED LIMITATION** — no Rust toolchain in
this sandbox to compile/run the real `cargo test` suite; strong
structural/hand-traced verification was performed in its place, per the
task brief's own explicit allowance for this exact situation (§35/§45:
"PASS WITH DOCUMENTED LIMITATION is acceptable only if structural
verification is strong and the limitation is explicitly documented").
Python's 600-test baseline was independently re-run and confirmed
unaffected.

**Next checkpoint:** frontend event integration
(`docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md` §10/§14,
items 4–5) — the Tauri-native `sidecar:*` event emission and the
frontend listener/status derivation — explicitly out of this
checkpoint's scope per the task brief's own §4.
