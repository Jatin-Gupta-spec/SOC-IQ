# Phase 4E-P2, Part 2B-2 — Restart Scheduling + Backoff

**Status:** PASS WITH DOCUMENTED LIMITATION (no Rust toolchain available in
this sandbox — structural/static verification performed instead; see §7).

Builds on: `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`
(the architecture/decision document, §7–§14 in particular),
`sidecar-core/src/restart.rs`'s `RestartPolicy`/`RestartTracker` (Part
2B-1, unchanged in behavior by this checkpoint).

---

## 0. Discrepancy found and resolved (read this first)

The archive this checkpoint started from (labeled
`SOC-IQ-Phase4E-P2-Part2B-1-COMPLETE.zip`) already contained two files
that described themselves, in their own doc comments, as **Part 2B-2**
work:

- `src-tauri/src/restart_scheduler.rs` — a complete `RestartScheduler`/
  `DelayRunner` real-timer implementation, with its own test suite
- `sidecar-core/tests/restart_schedule_tests.rs` — a complete test suite
  for pending-restart bookkeeping

Both imported and exercised `sidecar_core::{RestartSchedule,
RestartToken}` with a full implied API (`new`, `default`, `try_begin`,
`consume`, `is_pending`, `cancel`, `pending_attempt`). **That type did
not exist anywhere in the source tree** — not in `sidecar-core/src/`, not
exported from `sidecar-core/src/lib.rs`. `src-tauri/src/restart_scheduler.rs`
was also not wired into `src-tauri/src/lib.rs`'s module tree (no `mod
restart_scheduler;`). As shipped, `cargo test` on `sidecar-core` would
have failed to compile.

Per the task brief's own instruction ("if Part 2B-1 does not match §7,
stop and report the discrepancy before implementing scheduling" / "if
[attempt accounting] is ambiguous, stop and resolve the discrepancy
before proceeding"), this was reported to the requester before any
further implementation, rather than silently patched over. The
requester chose: implement the missing `RestartSchedule`/`RestartToken`
type now, inferring its exact contract from what the two orphaned files
already assumed of it, then wire everything together. That is what this
checkpoint does. See §1 below for the resulting design; nothing about
`RestartPolicy`/`RestartTracker` (Part 2B-1's actual, correct scope) was
touched.

---

## 1. Scheduler architecture

```
Crash detected / startup failure
        v
RestartPolicy::decide()   (sidecar-core, Part 2B-1, unchanged)
        v
RestartTracker::record_attempt()   (sidecar-core, Part 2B-1, unchanged)
        v
RestartSchedule::try_begin()   (sidecar-core, NEW this checkpoint)
        v
RestartScheduler::schedule()   (src-tauri, NEW this checkpoint — real timer)
        v
backoff delay elapses on a dedicated OS thread (never the Tauri/lifecycle thread)
        v
RestartSchedule::consume()   (re-validates scheduling identity)
        v
attempt_restart()   (src-tauri/src/lib.rs — re-validates LIFECYCLE state, then
                      SidecarProcess::reset() + SidecarProcess::start())
```

**Ownership.** Two new types, split exactly along the crate boundary
`sidecar-core` already enforces (no real I/O/timing in that crate):

- `sidecar_core::RestartSchedule`/`RestartToken` (`sidecar-core/src/restart.rs`)
  — pure, in-memory "is a restart currently pending" bookkeeping. No
  clock, no thread, no process. A `RestartToken` is a globally
  (process-wide, not per-instance) unique opaque id, deliberately not a
  simple per-instance counter — two independent `RestartSchedule`
  instances must never mint colliding tokens.
- `RestartScheduler`/`DelayRunner` (`src-tauri/src/restart_scheduler.rs`)
  — the real adapter. Composes one `RestartSchedule` with a
  `DelayRunner` (production: `ThreadDelayRunner`, one dedicated,
  named OS thread per scheduled restart, parked in
  `std::thread::sleep`). Generic over `DelayRunner` specifically so
  tests inject a fake that fires deterministically instead of ever
  sleeping in real time.

**There is still exactly one lifecycle owner.** No second `Supervisor`,
`SidecarState`, `SidecarProcess`, or crash detector was introduced.
`SidecarState` (`src-tauri/src/lib.rs`) grew two new fields
(`restart_tracker: Mutex<RestartTracker>`, `restart_policy:
RestartPolicy`, `scheduler: RestartScheduler`) alongside the existing
`process: Mutex<SidecarProcess>` — the same single `tauri::State` this
application has always had one of.

**Pending-restart representation.** `RestartSchedule` holds
`Option<(RestartToken, u32)>` — `None` means "no pending restart";
`Some((token, attempt))` means exactly one is pending. `try_begin`
refuses a second `Some` while one already exists (returns `None`
without side effects); `consume`/`cancel` are the only ways back to
`None`, and both are exactly-once/idempotent respectively (§4/§5).

**Callback lifecycle.** `RestartScheduler::schedule()`:

1. `RestartSchedule::try_begin(attempt)` — reserves the one pending slot
   and mints a token, or returns `false` immediately if one is already
   pending (no timer is started in that case).
2. `DelayRunner::run_after(delay, action)` — hands the action to the
   real (or fake) timer. The action, when it eventually runs, first
   calls `RestartSchedule::consume(token)`; only if that returns `true`
   does it invoke the caller-supplied restart action
   (`attempt_restart()` in `lib.rs`).
3. If the timer itself could not be created (`run_after` returns
   `false`), the pending registration from step 1 is rolled back via
   `cancel()`, so a real, later `schedule()` call is not permanently
   blocked by a phantom pending restart (task brief §20).

`attempt_restart()` (`src-tauri/src/lib.rs`) is what actually calls
`SidecarProcess::reset()` + `SidecarProcess::start()` — but only after
re-checking `LifecycleState` itself. `RestartScheduler`/`RestartSchedule`
guarantee the *scheduling* identity is still current; they have no
visibility into lifecycle state at all, so that check belongs in
`lib.rs`, immediately after acquiring the same `process` mutex every
other lifecycle-mutating call already serializes through.

---

## 2. Backoff

Exactly `RestartPolicy::backoff_for_attempt()` from Part 2B-1, reused
verbatim — no second formula was written. Capped exponential, no
jitter: `1s, 2s, 4s, 8s, 16s, 30s, 30s, ...` for attempts `1..7+`, per
the architecture doc §7.4. `RestartTracker::decide()` (unchanged) is the
only place that computes a delay; `RestartScheduler` only ever consumes
the `after: Duration` it is handed.

---

## 3. Cancellation

`RestartScheduler::cancel()` clears any pending restart via
`RestartSchedule::cancel()` — safe to call any number of times,
including when nothing is pending (idempotent, never panics). It does
**not** interrupt an already-sleeping timer thread; instead, a
cancelled token can never later be `consume()`d successfully, so a
timer that fires after cancellation still no-ops correctly when it
wakes up and presents its (now-invalid) token.

**Shutdown interaction.** `RunEvent::Exit`'s handler now calls
`state.scheduler.cancel()` *before* `SidecarProcess::shutdown()`. Two
outcomes, both correct:

- Cancellation wins the race against a not-yet-fired timer: the token
  is invalidated, the timer later no-ops, `shutdown()` proceeds
  normally.
- A timer's callback has already been consumed and is concurrently
  running `attempt_restart()` (holding the `process` mutex): `cancel()`
  itself is a no-op in that instant (nothing left to cancel — the token
  was already consumed), but `shutdown()`'s own `lock_process()` call
  simply blocks until `attempt_restart()` releases the mutex, and then
  proceeds — if `attempt_restart()` happened to succeed and left the
  process `Running`, `shutdown()` still observes `Running` and kills it
  normally. There is no path that leaves an orphaned process.

---

## 4. Duplicate / race protection

| Race (task brief numbering) | Protection |
|---|---|
| Duplicate crash events (crash A, crash B close together) | `RestartSchedule::try_begin` refuses a second pending restart while one exists — enforced by the type itself, not caller discipline. Covered by `duplicate_crash_events_produce_exactly_one_scheduled_timer_and_one_firing` (`restart_scheduler.rs`) and `try_begin_while_already_pending_is_rejected`/`only_one_restart_is_ever_pending_across_repeated_begin_attempts` (`restart_schedule_tests.rs`). |
| Duplicate callback invocation | `RestartSchedule::consume` succeeds exactly once per successful `try_begin` — a second presentation of the same token always returns `false`. Covered by `consuming_the_same_token_twice_only_succeeds_once` and `manually_invoking_the_stored_action_twice_still_only_fires_the_restart_once`. |
| Shutdown during a pending restart | `RunEvent::Exit` calls `scheduler.cancel()` before `shutdown()` (§3 above). Covered structurally; see §3's race-outcome walkthrough (no real Tauri runtime available to drive an actual `RunEvent::Exit` in this sandbox — see §7). |
| STOPPING/STOPPED observed inside the fired callback | `attempt_restart()` re-checks `SidecarProcess::state()` after acquiring the process mutex, and only proceeds for `Crashed`/`Failed`/`Timeout` — `Stopping`/`Stopped` (or any other unexpected state) hits the `other => { ... }` no-op arm. |
| Stale callback (schedule superseded / lifecycle changed) | `RestartSchedule`'s token identity: a token from an old, already-consumed-and-replaced schedule can never match a later one (`a_token_from_a_superseded_schedule_never_matches_a_later_one`, `consume_with_a_token_that_was_never_issued_is_a_no_op`). At the lifecycle level, `attempt_restart()`'s own state re-check (previous row) is the second, independent layer. |
| Process identity (old process's exit notification vs. a newly started process) | Unchanged from Part 2A: `SidecarProcess` holds exactly one `Option<Child>`, replaced (not merged) on each `start()`; `poll_for_crash()` only ever observes whichever child is currently stored. No new identity mechanism was needed or added. |

---

## 5. Recovery boundary (explicitly deferred, per the task brief)

- **Full recovery/readiness handling: DEFERRED TO PART 2B-3.** This
  checkpoint may trigger a start attempt via `attempt_restart()`, but
  `RUNNING` is only ever declared by `SidecarProcess::start()`'s own
  existing health-check logic (unchanged) — never merely because a
  timer fired.
- **`reset_after_stable` (60s stability reset, §7.5): NOT implemented.**
  `RestartTracker` is never reset automatically by this checkpoint — it
  only accumulates via `record_attempt()` across crashes/failed
  restarts until `Exhausted`. Implementing the stability window requires
  a real-time-owning caller that confirms *continuous* `RUNNING` for 60s,
  which is recovery-adjacent work explicitly out of this checkpoint's
  scope.
- **`SIDECAR_RESTART_EXHAUSTED` error/event contract: NOT IMPLEMENTED.**
  On `RestartDecision::Exhausted`, `handle_retry_eligible_failure()`
  only logs (`eprintln!`) and leaves the lifecycle in its already-correct
  terminal state. No new `SidecarError` variant was added to
  `sidecar-core/src/error.rs`.
- **Frontend event integration: NOT IMPLEMENTED.** No `app.emit(...)`
  calls exist anywhere in this checkpoint's changes; `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`
  §10's event contract remains a specification for a later part.

---

## 6. Files changed

| File | Purpose |
|---|---|
| `sidecar-core/src/restart.rs` | Added `RestartSchedule`/`RestartToken` (the missing Part 2B-2 bookkeeping type identified in §0). `RestartPolicy`/`RestartTracker` unchanged. |
| `sidecar-core/src/lib.rs` | Exported the two new types; added a Part 2B-2 module-doc note alongside the existing Part 2B-1 one. |
| `src-tauri/src/sidecar.rs` | Added `SidecarProcess::reset()`, a thin wrapper around `Supervisor::reset()` — needed so the restart trigger can drive the existing terminal-state -> `NOT_STARTED` transition without reaching into `Supervisor` directly. |
| `src-tauri/src/lib.rs` | Wired `mod restart_scheduler;`; `SidecarState` grew `restart_tracker`/`restart_policy`/`scheduler` fields (was a bare `Mutex<SidecarProcess>` tuple struct); added `build_launch_config()`, `lock_process()`, `run_crash_poll_loop()`, `handle_retry_eligible_failure()`, `attempt_restart()`; `run()`'s `setup` closure and `RunEvent::Exit` handler now go through this new logic instead of `eprintln!`-and-stop / a bare `shutdown()` call. |
| `src-tauri/src/restart_scheduler.rs` | Unchanged from what the archive already contained (§0) — now compiles and is wired in, since its `sidecar_core::{RestartSchedule, RestartToken}` dependency now exists. |
| `sidecar-core/tests/restart_schedule_tests.rs` | Unchanged from what the archive already contained (§0) — now compiles against the newly added type. |
| `docs/phase4/PHASE4E_P2_PART2B2_IMPLEMENTATION.md` | This file, new. |

No other file was modified. `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md` (the architecture document itself) was read, not edited.

---

## 7. Tests

**Rust toolchain unavailable in this sandbox** — `which cargo` / `which
rustc` both report not found (confirmed directly, not assumed). No
`cargo test` was run, and none of the numbers below are fabricated test
results.

**Structural/static verification performed instead:**

- Brace/paren balance checked on every edited file (all balanced).
- Every call site of the previous `SidecarState(Mutex<SidecarProcess>)`
  tuple-struct API (`state.0`) was located and confirmed migrated to
  the new named-field struct — none remain.
- Confirmed, by direct grep across `src-tauri/src` and `sidecar-core/src`,
  that: exactly one `struct Supervisor`, exactly one `struct
  SidecarState`, exactly one `struct SidecarProcess`; no `tokio::spawn`
  anywhere in the project; the only `std::thread::spawn`/
  `std::thread::Builder::spawn` call sites are the original one-time
  `setup` thread and `ThreadDelayRunner`'s one-thread-per-scheduled-restart
  timer (both already existing/doc'd, neither new-supervisor-shaped);
  every `std::thread::sleep` call is inside a function that only ever
  runs on one of those background threads, never inside the Tauri
  `setup`/`run` closures' own synchronous bodies.
- `sidecar-core/tests/restart_schedule_tests.rs` (pre-existing, §0) was
  read line-by-line and each assertion traced by hand against the new
  `RestartSchedule`/`RestartToken` implementation (documented inline in
  §0's discrepancy note and verified during implementation) — all 15
  cases are satisfied by the implementation as written, including the
  cross-instance token-collision case that specifically required a
  process-wide (not per-instance) token counter.
- `src-tauri/src/restart_scheduler.rs`'s existing test module (§0) was
  likewise read and traced against the same `RestartSchedule` contract;
  no changes were needed to that file.

**Not executed (and not claimed to have been):** `cargo test -p
sidecar-core`, `cargo test -p soc-iq` (a.k.a. the `src-tauri` crate),
any real-time-based race test, any real killed-mid-run-process
integration test. `python3 -m pytest tests/ --ignore=tests/gui` was not
re-run either — no Python file was touched by this checkpoint, so it is
out of this change's blast radius.

---

## 8. Frozen checkpoints

- Phase 4E-P1: untouched.
- Phase 4E-P2 Part 1 (architecture doc): untouched (read only).
- Phase 4E-P2 Part 2A (crash detection wiring): its `poll_for_crash()`
  call site in `lib.rs` is preserved in behavior — still detects a
  crash and logs it — now additionally handed off to
  `handle_retry_eligible_failure()` instead of simply breaking the loop.
- Phase 4E-P2 Part 2B-1 (`RestartPolicy`/`RestartTracker`): semantics
  fully preserved — no line inside the existing `impl RestartPolicy`/
  `impl RestartTracker` blocks was changed. Only new, additive code
  (`RestartSchedule`/`RestartToken`) was appended to the same file.

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

| Criterion | Met? |
|---|---|
| Scheduler exists | Yes (`RestartScheduler`, `RestartSchedule`) |
| Backoff is correct | Yes — reused verbatim from Part 2B-1, not reimplemented |
| One pending restart is enforced | Yes — by `RestartSchedule::try_begin`, not caller discipline |
| Cancellation works | Yes — idempotent, race-safe against a concurrently-firing timer |
| Shutdown cannot accidentally restart the sidecar | Yes — `scheduler.cancel()` + lifecycle-state re-check inside `attempt_restart()`, two independent layers |
| Duplicate scheduling / duplicate callbacks prevented | Yes — token-based, structurally enforced |
| Stale callbacks rejected | Yes — token identity + lifecycle-state re-check |
| Policy/tracker reused correctly | Yes — zero changes to their existing logic |
| No blocking delay on the lifecycle thread | Yes — every sleep is on a dedicated background thread |
| No second supervisor | Yes — confirmed by static audit (§7) |
| Tests cover critical scheduler races | Yes, at the unit level (pre-existing files, traced by hand, §7) — no real-time/integration race test was run |
| Regression verification honestly reported | Yes — toolchain unavailability stated plainly, no fabricated results |
| No unrelated changes | Yes — every changed file is either the discrepancy fix (§0) or direct scheduling-integration wiring |
| Full project ZIP produced and verified | See the delivered archive and its accompanying message |

**Classification: PASS WITH DOCUMENTED LIMITATION** — no Rust toolchain
in this sandbox to compile/run the real test suite; strong structural
verification was performed in its place, per the task brief's own
allowance for this exact situation.

**Next checkpoint:** Phase 4E-P2 Part 2B-3 — Recovery + Exhaustion.
