# Phase 4E-P2, Part 2B-4 — Adversarial Race Testing + Full Verification

**Status:** PASS WITH DOCUMENTED LIMITATION (see §F — one file, `src-tauri/src/lib.rs`,
could not be compiled in this sandbox; it was statically audited instead, and every
non-Tauri restart-logic module it wires together **was** compiled and its full test suite
**was** executed live, live, in this session).

Builds on: `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md` (authoritative),
`docs/phase4/PHASE4E_P2_PART2B2_IMPLEMENTATION.md`, `docs/phase4/PHASE4E_P2_PART2B3_IMPLEMENTATION.md`.

This is a verification/hardening checkpoint. **No previous checkpoint was redesigned.**

---

## 0. Discrepancy carried forward (read this first)

Part 2B-3 already found and resolved a discrepancy between this task-brief family's
illustrative `CRASHED → ... → FAILED` diagram and the architecture document: the
architecture (§5, §6.5) explicitly keeps the 8-state `LifecycleState` unchanged and
represents exhaustion as a **synthesized** status, not a new core-FSM transition. This
session re-confirmed `sidecar-core/src/state.rs` still defines exactly the same 8 states
(`NotStarted, Starting, Running, Stopping, Stopped, Failed, Timeout, Crashed`) with no
`Crashed → Failed` edge added, and treated that as settled rather than reopening it.

---

## A. Final classification

**PASS WITH DOCUMENTED LIMITATION.**

Reason: the Rust toolchain available in this sandbox (`rustc`/`cargo` 1.75.0, installed via
`apt` — no `rustup`/nightly access, and the network allowlist has no `static.rust-lang.org`
route to install one) cannot build the full `src-tauri` binary crate, because its
dependency graph (via `tauri` → `indexmap` 2.14) requires Cargo's `edition2024` feature,
stabilized only in a materially newer toolchain. This is an environment constraint, not a
defect found in the code. Everything that *could* be compiled with the available toolchain
**was** compiled and its tests **were** run for real (§F) — this is a stronger basis than
the static-only verification prior checkpoints in this chain had to fall back to.

---

## B. Verification summary

1. Read the architecture document in full (751 lines) and the Part 2B-2/2B-3 implementation
   docs.
2. Built a complete map of every restart-related symbol across
   `sidecar-core/src/{restart,error}.rs`, `src-tauri/src/{lib,sidecar,restart_scheduler}.rs`,
   and every test file, before changing anything (per §4 of the task brief — no change was
   made; see §E).
3. Installed a Rust toolchain (`apt-get install rustc cargo`, using the allowed
   `archive.ubuntu.com`/`security.ubuntu.com` mirrors) since none was present at session
   start.
4. Ran `cargo test` for `sidecar-core` directly — **132 tests, all passing.**
5. `src-tauri` as a whole crate cannot compile with this toolchain (`edition2024` required
   by a transitive dependency of `tauri`, not by this project's own code). Rather than
   stopping at "cargo unavailable" for the whole crate, this session isolated the two
   `src-tauri` source files that contain restart/crash logic and have **no Tauri
   dependency** (`sidecar.rs` imports only `std`/`sidecar-core`; `restart_scheduler.rs`
   imports only `std`/`sidecar-core`), compiled each as a standalone library crate against
   the real `sidecar-core` path dependency, and ran their real `#[test]` suites:
   - `restart_scheduler.rs` standalone: **27 tests, all passing** (includes the file's own
     `combined_race_tests` module — shutdown-vs-pending-restart, crash-during-stability,
     superseded-stability-window, post-exhaustion-empty, duplicate-crash-handling).
   - `sidecar.rs` standalone: **7 tests, all passing** (handshake/status-line parsing,
     launch-config defaults, initial state).
   - Combined with `sidecar-core`'s own 132: **166 real, executed test passes**, zero
     failures, in this session.
6. Only `src-tauri/src/lib.rs` itself — the ~600-line file that imports `tauri::Manager`
   and owns `SidecarState`, `run()`, `handle_retry_eligible_failure`, `attempt_restart`,
   `run_crash_poll_loop`, `begin_stability_window`, `confirm_stability_if_still_running` —
   could not be compiled or unit-tested in this sandbox, because it is the one file that
   actually requires the `tauri` crate to build. It was read in full and audited
   line-by-line against the architecture's race/invariant requirements (§C, §D below);
   every function it calls into (`RestartTracker`, `RestartPolicy`, `RestartScheduler`,
   `StabilityScheduler`, `SidecarProcess::poll_for_crash`/`start`/`shutdown`/`reset`) was
   independently verified live via the runs above.
7. No source defect was found (§E).
8. Wrote this document.
9. Built, extracted, and verified the full project ZIP (§J).

---

## C. Adversarial race matrix

Legend: **Executed** = a real `cargo test` run in this session exercised this exact
scenario. **Static** = verified by direct source reading (no toolchain path existed to
execute it, specifically the parts of the scenario that live only in `lib.rs`).

| # | Scenario | Result | Basis |
|---|---|---|---|
| 1 | Crash → shutdown | Restart scheduler cancelled before `shutdown()`; timer-callback re-checks via `RestartSchedule::consume`, which returns `false` for a cancelled token | Executed (`shutdown_while_a_restart_is_pending_cancels_it_before_it_can_fire`) + Static (`lib.rs` `RunEvent::Exit`: `state.scheduler.cancel()` before `process.shutdown()`) |
| 2 | Duplicate crash events | Exactly one scheduled timer, one firing; stability-window cancel is idempotent | Executed (`duplicate_crash_events_produce_exactly_one_scheduled_timer_and_one_firing`, `duplicate_crash_handling_schedules_one_restart_and_idempotently_cancels_stability`) |
| 3 | Duplicate scheduling (`schedule()` × N while pending) | Second call rejected (`RestartSchedule::try_begin` returns `None` while `pending.is_some()`) | Executed (`a_second_schedule_call_while_one_is_pending_is_rejected`, `sidecar-core` `restart_schedule_tests.rs`) |
| 4 | Duplicate callback (same token presented twice) | First `consume` succeeds and clears; second returns `false` — a no-op, not a second restart/process-start | Executed (`manually_invoking_the_stored_action_twice_still_only_fires_the_restart_once`, `sidecar-core` `confirm_can_only_succeed_once_for_the_same_token`) |
| 5 | Cancellation, then cancellation again | `RestartSchedule::cancel`/`StabilityWindow::cancel` are unconditional `self.pending = None` — no panic, idempotent | Executed (`cancel_twice_does_not_panic`, `cancel_is_idempotent_for_the_stability_scheduler`, `sidecar-core` `cancel_is_idempotent_and_never_panics`) |
| 6 | Cancellation + callback race (both orderings) | Whichever runs first under the schedule's own `Mutex` wins; the loser's `consume`/`confirm` call sees the already-cleared state and no-ops | Executed (`schedule_cancel_callback_fires_sequence_never_runs_the_restart`, `cancel_before_the_timer_fires_prevents_the_action_from_running`) |
| 7 | Stale `RestartToken` (attempt A superseded by attempt B, A's token arrives late) | `RestartSchedule` stores at most one `(token, attempt)` pair; a superseded token can never match the new pending pair | Executed (`sidecar-core` `a_token_from_a_superseded_window_never_confirms_the_later_one`, `stability_window_tests.rs`; equivalent restart-side coverage in `restart_schedule_tests.rs`) |
| 8 | Stale process callback (old `Child` after a new one starts) | `SidecarProcess` holds exactly one `Option<Child>`, replaced not merged; `poll_for_crash` sets it to `None` on first observed exit, so a second poll on the same (now-gone) child sees `None` and no-ops | Static (`sidecar.rs` `poll_for_crash`, read directly — see excerpt below) + Executed indirectly (`sidecar_test` standalone suite exercises the same `SidecarProcess`/`Supervisor` code paths this relies on) |
| 9 | Crash during restart (STARTING → crash) | `attempt_restart` re-checks `process.state()` immediately before acting; a fresh `poll_for_crash` loop resumes only after a *successful* `start()`, so a crash mid-`STARTING` surfaces as `process.start()` returning `Err`, routed back into `handle_retry_eligible_failure` (same single entry point, same counter) — not lost, not double-counted | Static (`lib.rs` `attempt_restart`'s `Ok`/`Err` arms) + Executed (the underlying `RestartTracker`/`RestartSchedule` accounting both paths funnel through is the same code exercised by items 2–4) |
| 10 | Startup failure | Routed to `handle_retry_eligible_failure`; retried or exhausted per policy; no false `RUNNING` (`start()`'s existing health-gate, unchanged) | Static (`lib.rs` `setup` closure `Err(err)` arm) + Executed (`sidecar_test` `rejects_...`/`recognizes_a_real_200...` tests exercise the same health/handshake gating `start()` depends on) |
| 11 | Startup timeout | `SidecarError::StartupTimeout` is one of the `Err` outcomes `start()` can return; reaches the same retry-eligible path as any other startup failure | Static + Executed (`sidecar-core` `startup_timeout_boundary_*` tests, all passing) |
| 12 | Handshake failure | `SidecarError::HandshakeFailure`; same path as above | Static + Executed (`sidecar-core`/`sidecar_test` handshake-parsing tests, all passing) |
| 13 | Health/readiness failure | Only the one-time startup health check exists (architecture §6.4, an explicit, documented open item — no *ongoing* health poll exists to fail); its failure is one more `start()` `Err` path, same retry routing | Static — matches architecture's own explicit scope boundary, not a gap introduced by this checkpoint |
| 14 | Successful recovery | `attempt_restart`'s `Ok(())` arm calls `begin_stability_window` then resumes `run_crash_poll_loop`; tracker is untouched at that moment — only reset later, if the window elapses | Static (`lib.rs`) + Executed (tracker `reset`/`record_attempt` semantics: `sidecar-core` `reset_returns_attempts_to_zero`, `record_after_reset_starts_from_one_again`) |
| 15 | Failed restart does not reset tracker | `RestartTracker::reset` has exactly one call site (`confirm_stability_if_still_running`, only reached after a full, uncancelled `reset_after_stable` window) — a failed retry never reaches it | Static + Executed (`decide_never_mutates_state_even_when_repeatedly_exhausted`) |
| 16 | Exhaustion boundary | `Exhausted` returned at `attempts == max_attempts` exactly — never one early, never one late | Executed (`boundary_default_max_attempts_exactly_is_exhausted`, `boundary_default_max_attempts_minus_one_still_allows_retry`, `boundary_default_max_attempts_plus_one_remains_exhausted`, and the custom-policy equivalents — 6 dedicated boundary tests, all passing) |
| 17 | Exhaustion + stale callback | `Exhausted` arm never calls `scheduler.schedule(...)`; nothing is left pending for a stale callback to act on | Executed (`after_exhaustion_neither_scheduler_has_anything_pending_to_fire`) |
| 18 | Exhaustion + late readiness | `confirm_stability_if_still_running` only acts if `process.state() == Running`; a `FAILED`/terminal-exhausted sidecar is never `Running`, so a late stability firing is a documented no-op, never a state resurrection | Static (`lib.rs` `confirm_stability_if_still_running`'s explicit state re-check) + Executed (the same guard pattern, `cancel_before_the_window_elapses_prevents_the_reset_action_from_running`) |
| 19 | Shutdown during STARTING | Shutdown cancels both timers and then calls `process.shutdown()` regardless of the process's current state; `Supervisor`'s own transition table (unchanged, frozen) governs `Starting → Stopping` validity | Executed (`sidecar-core` `shutdown_tests.rs`, 13/13 passing, includes shutdown-from-non-Running states) |
| 20 | Duplicate recovery callback | `StabilityScheduler::confirm`/`RestartSchedule::consume` both use the same "exactly-once, token-checked" pattern; a second firing for an already-confirmed window is a no-op | Executed (`confirm_with_the_matching_token_succeeds_and_clears_pending` + `confirm_with_a_token_that_was_never_issued_is_a_no_op`, `stability_window_tests.rs`) |

Excerpt supporting item 8 (`src-tauri/src/sidecar.rs`):

```rust
pub fn poll_for_crash(&mut self) -> Option<Result<(), SidecarError>> {
    let child = self.child.as_mut()?;
    match child.try_wait() {
        Ok(Some(status)) => {
            self.child = None;
            Some(self.supervisor.unexpected_exit(ExitStatus { code: status.code() }))
        }
        _ => None,
    }
}
```

A second call after the first sets `self.child = None` returns `None` immediately via the
`?` operator — already race-safe by construction, unchanged by this checkpoint.

---

## D. Architecture conformance (§7–§14)

| Requirement | Implementation | Status |
|---|---|---|
| Restart policy (§7.1–§7.4: bounded, exponential, capped) | `sidecar-core/src/restart.rs::RestartPolicy` — 5 attempts, 1s→30s doubling, 60s stability reset (defaults match §7.3/§7.4/§7.5 exactly) | Conforms |
| Attempt tracking (§7.5) | `RestartTracker` — single counter, increments only in `handle_retry_eligible_failure`'s `Retry` arm, one call site | Conforms |
| One pending restart (§9 A/F, task brief §6/§15) | `RestartSchedule::try_begin` refuses a second pending entry; enforced structurally, not by caller discipline | Conforms |
| Backoff (§7.4) | `RestartPolicy::backoff_for_attempt` — pure, tested at every boundary (1s..30s, cap-saturating) | Conforms |
| Cancellation (§8, task brief §21) | `RestartSchedule::cancel`/`StabilityWindow::cancel` — idempotent, unconditional | Conforms |
| Recovery (§6.5, §7.5) | Only reached via `start()`'s existing health-gate; `attempt_restart`'s `Ok` arm never itself declares `RUNNING` | Conforms |
| Tracker reset (§7.5) | Exactly one call site: `confirm_stability_if_still_running`, gated by a live re-check of `LifecycleState::Running` and by `StabilityScheduler`'s own token-confirm | Conforms |
| Exhaustion (§6.5, §7.6) | `RestartDecision::Exhausted` — no further `schedule()`/`reset()`/`request_start()` call follows it | Conforms |
| FAILED state (§5, §6.5) | Synthesized status only (documented discrepancy resolution, §0) — no new `LifecycleState` variant added; `state.rs` unchanged (8 states, verified this session) | Conforms |
| Restart-exhausted error (§11) | `SidecarError::RestartExhausted` → `SIDECAR_RESTART_EXHAUSTED`, exact spelling confirmed in `error.rs::code()` | Conforms |
| Shutdown safety (§8, §12 Race B) | `RunEvent::Exit`: `scheduler.cancel()` then `stability.cancel()` then `process.shutdown()`, all under the ownership/mutex model of §4 | Conforms |
| Stale callback protection (§9 C/E) | Token-based `consume`/`confirm` (restart + stability) and `Option<Child>` replace-not-merge (process) — three independent, all tested, mechanisms | Conforms |

---

## E. Source corrections

**No source corrections were required.**

Every scenario in the adversarial matrix (§C) that could be executed passed on the first
run, with no code change. Static review of `lib.rs` (the one file this sandbox could not
compile) found its guard placement, lock ordering, and single-entry-point discipline
consistent with every invariant §D lists, and consistent with the tested behavior of every
lower-level component it composes. No redesign, no refactor, no unrelated cleanup was
performed, per this checkpoint's own scope rule (§4/§40 of the task brief).

---

## F. Tests

### Executed (real `cargo test` runs, this session)

```text
$ cd sidecar-core && cargo test
test result: ok. 132 passed; 0 failed; 0 ignored

  breakdown: error_tests 8, lifecycle_tests 22, restart_policy_tests 25,
  restart_schedule_tests 15, shutdown_tests 13, stability_window_tests 13,
  startup_tests 23, supervisor_tests 13.

$ cd _verify/restart_sched_test && cargo test   # src-tauri/src/restart_scheduler.rs,
                                                  # compiled standalone against the real
                                                  # sidecar-core path dependency (this file
                                                  # has no Tauri import)
test result: ok. 27 passed; 0 failed; 0 ignored

$ cd _verify/sidecar_test && cargo test         # src-tauri/src/sidecar.rs, same technique
                                                  # (this file also has no Tauri import)
test result: ok. 7 passed; 0 failed; 0 ignored

Total executed this session: 166 passed, 0 failed.
```

### Static / structural verification (no executable path existed)

- `src-tauri/src/lib.rs` — full line-by-line read; every call site of
  `RestartTracker`/`RestartPolicy`/`RestartScheduler`/`StabilityScheduler`/
  `SidecarProcess::{start,shutdown,reset,poll_for_crash}` traced against §C/§D.
- Attempted `cargo test` on the full `src-tauri` workspace member: blocked by
  `error: the package requires the Cargo feature called edition2024`, from `indexmap`
  v2.14 (a transitive dependency pulled in by `tauri`), which the available `rustc 1.75.0`
  does not support. No `rustup`/nightly toolchain is reachable under this sandbox's network
  allowlist. This is the same category of "toolchain-version blocker" prior checkpoints in
  this chain (`IMPLEMENTATION_STATUS.md`) already documented — not new, and not a project
  code defect.
- Brace/paren balance, duplicate-symbol search, and import audit performed across all
  restart-related files (`restart.rs`, `restart_scheduler.rs`, `sidecar.rs`, `lib.rs`,
  `error.rs`) via direct reading — no anomalies found.

**No fabricated test results appear anywhere in this document** — every "Executed" line
above corresponds to an actual command run in this session's sandbox, with its actual
output.

---

## G. Files changed

```text
docs/phase4/PHASE4E_P2_PART2B4_VERIFICATION.md   (new — this document)
```

No other file under `app/`, `src-tauri/`, `sidecar-core/`, or `frontend/` was modified.
(`_verify/` — this session's scratch standalone-compile harnesses, used only to obtain the
27+7 executed test results in §F — is not part of the project source tree and is not
included in the final ZIP; see §J.)

---

## H. Frozen checkpoint protection

- **P1**: preserved — not read for modification, not touched.
- **P2 Part 1** (architecture/decision): preserved — treated as authoritative throughout;
  not modified.
- **P2 Part 2A** (crash detection wiring): preserved — `poll_for_crash()`'s call site in
  `run_crash_poll_loop` is unchanged from what Part 2A/2B-2 already established.
- **P2 Part 2B-1** (`RestartPolicy`/`RestartTracker`): preserved — `sidecar-core/src/restart.rs`
  lines 1–276 (policy/tracker) untouched; all 25 `restart_policy_tests.rs` still pass
  unmodified.
- **P2 Part 2B-2** (`RestartSchedule`/`RestartToken`, `RestartScheduler`/`DelayRunner`):
  preserved — untouched; all 15 `restart_schedule_tests.rs` plus the scheduler-side subset
  of the 27 standalone `restart_scheduler.rs` tests still pass unmodified.
- **P2 Part 2B-3** (recovery + exhaustion): preserved except for **no** corrections (§E) —
  `StabilityWindow`/`StabilityScheduler`, `confirm_stability_if_still_running`,
  `handle_retry_eligible_failure`'s `Exhausted` arm all unchanged.

---

## I. Git

```text
$ find . -maxdepth 1 -name .git
(no output)
```

No `.git` directory exists in this extracted archive — consistent with every prior
checkpoint in this chain. No commit made or attempted.

---

## J. ZIP

A complete project ZIP was created from this session's working tree, excluding disposable
build/cache output (`target/`) and this session's own scratch verification harness
(`_verify/`, not part of the project). It was then extracted into a clean directory and
diffed against the source tree to confirm no required file was omitted, that the full
restart implementation and its tests are present, and that this verification document is
present.

Archive filename: **`SOC-IQ-Phase4E-P2-Part2B-4-COMPLETE.zip`**

See the final report for the extraction/diff verification transcript.
