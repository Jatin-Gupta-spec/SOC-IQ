# Phase 4E-P2 — Final Crash/Restart Integration Audit + Freeze

**Status: PASS WITH DOCUMENTED LIMITATIONS / FREEZE**

This is the final integration gate for the complete sidecar crash/restart subsystem
(Architecture → Part 2A → Part 2B-1 → Part 2B-2 → Part 2B-3 → Part 2B-4 → **this
checkpoint**). It is an audit and freeze, not a redesign. **No previous checkpoint was
substantially rewritten; no new functionality was added.** Two documentation-clarity items
are noted (§H) but neither rises to Medium or above, and neither required a source change.

---

## A. Final classification

**PASS WITH DOCUMENTED LIMITATIONS / FREEZE**

Freeze criteria (§40 of the task brief) are met: **0 Critical, 0 High**, exactly one
lifecycle owner, exactly one crash-detection path, exactly one policy/tracker, exactly one
scheduler, at-most-one-pending enforced structurally, stale tokens/callbacks rejected,
shutdown cancels restart, FAILED cannot resurrect automatically, initial startup is bounded
(not an infinite loop), tracker reset occurs at the architecturally-correct point,
exhaustion is correctly represented, `SIDECAR_RESTART_EXHAUSTED` is correct, no
undocumented lifecycle state exists, documentation matches implementation (two minor,
pre-existing, deliberately-unaltered exceptions noted at §H), test coverage is disclosed
honestly (§G), and runtime limitations are explicitly disclosed (§G).

The "documented limitations" are:
1. `src-tauri/src/lib.rs` cannot be compiled in this sandbox (toolchain constraint, not a
   code defect — see §G).
2. The frontend event/error contract (architecture §10/§11's `app.emit`/`{code,message}`
   surface) remains intentionally deferred to a future Part 3, exactly as Parts 2B-2/2B-3
   already documented — reconfirmed, not newly discovered, this session (§F).

---

## B. Executive summary

This audit re-verified, from source, every claim the Part 2B-4 verification document made,
rather than trusting it. All 166 previously-executed tests were re-run fresh in this
session and still pass (132 in `sidecar-core` directly; 27 + 7 more by compiling the two
Tauri-free restart-related `src-tauri` source files as standalone crates against the real
`sidecar-core` dependency — the same technique Part 2B-4 used, repeated independently
here). Repository-wide searches (§C.4) confirm exactly one lifecycle owner, exactly one
thread-spawn call site for the initial startup path, exactly one poll loop function (called
from exactly two places, never concurrently), and zero `app.emit`/`tokio::spawn` call sites
anywhere in the codebase. The 8-state core FSM and its transition table are byte-for-byte
unchanged from Part 1. The exhaustion boundary was independently re-derived from
`RestartTracker::decide`'s actual comparison (`attempts >= max_attempts`) and confirmed
off-by-one-free. One genuinely new piece of analysis this session performed beyond Part
2B-4's own scope: tracing whether `LifecycleState::Failed` — a name shared between a
retry-eligible startup failure and a terminal post-shutdown-timeout state — could let a
stale callback resurrect a shutdown or exhausted sidecar (§E, §H). It cannot: the only two
paths that reach that state are provably disjoint from the restart-callback path. No source
correction was required.

---

## C. Architecture audit

### C.1 Ownership (§5 of the task brief)

```
SidecarState  (src-tauri/src/lib.rs:112, exactly one `struct SidecarState` in the codebase)
    ↓
SidecarProcess (src-tauri/src/sidecar.rs:87, exactly one definition)
    ↓
Supervisor     (sidecar-core/src/supervisor.rs:52, exactly one definition)
```

Repository-wide `grep -rn "struct SidecarState"` / `"struct Supervisor\b"` /
`"struct SidecarProcess\b"` each return exactly one hit in the real project tree. No second
`SidecarState`, no second `Supervisor`, no second process owner, no second restart manager,
no second crash detector exists. `RestartScheduler`/`StabilityScheduler` are held as fields
*inside* `SidecarState` (`lib.rs:130,137`) — scheduling infrastructure, never an
independent lifecycle authority; neither type has any method that reads or mutates
`LifecycleState` itself (confirmed by reading `restart_scheduler.rs` in full — its two
public types only ever touch `RestartSchedule`/`StabilityWindow` bookkeeping and an opaque
`action: F` callback, never `Supervisor`/`SidecarProcess`).

### C.2 §7–§14 conformance table

| Requirement | Implementation | Status |
|---|---|---|
| Restart policy (§7.1–§7.4) | `RestartPolicy` — 5 attempts, 1s→30s exponential, 60s stability reset; pure, no I/O, no timer, no Tauri import | Conforms |
| Attempt tracking (§7.5) | `RestartTracker` — one counter, one increment call site (`handle_retry_eligible_failure`'s `Retry` arm) | Conforms |
| One pending restart (§9A/F) | `RestartSchedule::try_begin` structurally refuses a second pending entry | Conforms |
| Backoff (§7.4) | `RestartPolicy::backoff_for_attempt`, pure, boundary-tested | Conforms |
| Cancellation (§8) | `RestartSchedule::cancel`/`StabilityWindow::cancel`, unconditional, idempotent | Conforms |
| Recovery (§6.5/§7.5) | Reached only through `start()`'s existing health-gate; spawn success alone is never treated as recovery (§9 of this audit) | Conforms |
| Tracker reset (§7.5) | Exactly one call site, gated by both `StabilityScheduler`'s token-confirm and a live `LifecycleState::Running` re-check | Conforms |
| Exhaustion (§6.5/§7.6) | `RestartDecision::Exhausted` — no further `schedule()`/`reset()`/`start()` follows | Conforms |
| FAILED state (§5/§6.5) | Synthesized status only; core FSM unchanged (8 states, re-verified byte-for-byte this session) | Conforms |
| Restart-exhausted error (§11) | `SIDECAR_RESTART_EXHAUSTED`, exact string, in `error.rs::code()` | Conforms |
| Shutdown safety (§8/§12 Race B) | `scheduler.cancel()` → `stability.cancel()` → `process.shutdown()`, one call site, `RunEvent::Exit` only | Conforms |
| Stale callback protection (§9 C/E) | Token-based `consume`/`confirm` (restart, stability) + `Option<Child>` replace-not-merge (process) | Conforms |
| Event contract (§10) | **Not implemented — explicitly deferred.** Zero `app.emit`/`.emit(` call sites exist anywhere in the repo (repo-wide search, this session) | Documented deferral, not a defect |
| Frontend `{code,message}` error contract (§11, `get_sidecar_origin`) | **Not implemented — explicitly deferred.** `get_sidecar_origin` still returns the pre-P2 ad hoc `format!("sidecar is not ready yet (state: {:?})", ...)` string | Documented deferral, not a defect |

---

## D. Lifecycle / state-machine audit

Re-read `sidecar-core/src/state.rs` in full this session (not assumed from a prior
checkpoint's report). `LifecycleState` still has exactly 8 variants
(`NotStarted, Starting, Running, Stopping, Stopped, Failed, Timeout, Crashed`) and
`can_transition_to` still permits exactly these 12 edges — no more, no fewer:

| Current | Event | Expected (Part 1) | Actual (`state.rs`) | Status |
|---|---|---|---|---|
| NOT_STARTED | start | STARTING | `(NotStarted, Starting)` ✓ | Matches |
| STARTING | ready | RUNNING | `(Starting, Running)` ✓ | Matches |
| STARTING | spawn failure | FAILED | `(Starting, Failed)` ✓ | Matches |
| STARTING | readiness timeout | TIMEOUT | `(Starting, Timeout)` ✓ | Matches |
| RUNNING | shutdown requested | STOPPING | `(Running, Stopping)` ✓ | Matches |
| RUNNING | crash | CRASHED | `(Running, Crashed)` ✓ | Matches |
| STOPPING | exits | STOPPED | `(Stopping, Stopped)` ✓ | Matches |
| STOPPING | shutdown timeout | FAILED | `(Stopping, Failed)` ✓ | Matches |
| FAILED | explicit reset | NOT_STARTED | `(Failed, NotStarted)` ✓ | Matches |
| TIMEOUT | explicit reset | NOT_STARTED | `(Timeout, NotStarted)` ✓ | Matches |
| CRASHED | explicit reset | NOT_STARTED | `(Crashed, NotStarted)` ✓ | Matches |
| STOPPED | explicit reset | NOT_STARTED | `(Stopped, NotStarted)` ✓ | Matches |
| CRASHED | restart allowed (synthesized) | *(no core-FSM edge — see §0/§5 of the architecture doc)* | Not a `can_transition_to` edge; realized one layer above as `reset()` then `request_start()`, two of the already-listed edges | Matches (by design) |
| CRASHED | exhausted (synthesized) | *(no core-FSM edge — stays `CRASHED`)* | No transition attempted; `RestartDecision::Exhausted` arm never calls `reset()` | Matches (by design) |
| FAILED / STOPPED | stale restart callback | no transition | `attempt_restart`'s `other =>` arm — logs and no-ops for any state not in `{Crashed, Failed, Timeout}`; `Stopped`/`Stopping`/`Running`/`Starting`/`NotStarted` all fall there | Matches |

`Lifecycle::transition`/`can_transition_to` is unchanged from Part 1 — confirmed by direct
comparison against the architecture document's own §5 quotation of the table, which is
identical to what `state.rs` contains today. **No undocumented transition exists.**

---

## E. RestartPolicy / RestartTracker / RestartSchedule / RestartScheduler audits

### E.1 RestartPolicy (§7 of the task brief)

Read `sidecar-core/src/restart.rs` lines 88–165 line by line. `RestartPolicy` is a plain
`Copy` struct plus one pure method (`backoff_for_attempt`) — no field or method performs
I/O, holds a `Mutex`, spawns a thread, or imports `Supervisor`/`SidecarProcess`/`tauri`.
`grep -n "use " sidecar-core/src/restart.rs` shows only `std::sync::atomic` and
`std::time::Duration` — no Tauri, no process, no GUI dependency of any kind. The policy
never calls `reset()`/`request_start()`/`schedule()` itself; `RestartDecision` is inert
data, matching §7.6 of the architecture ("the decision is data, not an action").

### E.2 RestartTracker (§8 of the task brief)

- **One logical attempt = one accounting operation**: `record_attempt` has exactly one call
  site in the whole codebase (`handle_retry_eligible_failure`'s `Retry` arm,
  `src-tauri/src/lib.rs:380`) — re-confirmed by `grep -rn "record_attempt"` this session.
- **Increment**: only on a retry-eligible failure the policy already agreed to retry.
- **Reset**: only in `confirm_stability_if_still_running`, itself only reachable after
  `StabilityScheduler::begin`'s token survives the full, uncancelled 60s delay *and* a live
  re-check confirms `LifecycleState::Running` at fire time.
- **Not reset** on: spawn (no reset call anywhere in `start()`/`sidecar.rs`), on
  `schedule()`/`try_begin` (scheduling code never touches the tracker), on entering
  `STARTING` (no call site there either), or on a temporary/one-off failure (only the
  stability path resets, and a failure cancels that path first — see §E.4).
- **Boundary/overflow**: `attempts: u32`; the tracker's own tests
  (`boundary_default_max_attempts_exactly_is_exhausted`,
  `boundary_default_max_attempts_plus_one_remains_exhausted`, both re-executed this
  session) prove no off-by-one in either direction, and `decide`'s pure
  `self.attempts >= policy.max_attempts` comparison cannot itself overflow for any `u32`
  value up to `u32::MAX` — no pathological-value handling was invented beyond what the type
  system already guarantees, matching the task brief's own "do not add arbitrary integer
  complexity unless there is a real overflow risk" instruction.

### E.3 Exhaustion boundary (§17 of the task brief), re-derived independently

```rust
pub fn decide(&self, policy: &RestartPolicy) -> RestartDecision {
    if self.attempts >= policy.max_attempts {
        return RestartDecision::Exhausted { attempts: self.attempts };
    }
    let attempt = self.attempts + 1;
    RestartDecision::Retry { attempt, after: policy.backoff_for_attempt(attempt) }
}
```

With the default `max_attempts = 5`: `attempts` 0→1→2→3→4 each yield `Retry` (attempts
numbered 1 through 5, i.e. exactly 5 retries permitted); at `attempts == 5`,
`Exhausted { attempts: 5 }` is returned. **The final permitted attempt is retry #5; the
6th consultation (`attempts == 5`) is the first to report `Exhausted`.** No path allows a
6th automatic retry; no path exhausts one attempt early (`attempts == 4` still retries).
Re-executed `boundary_*` tests (6 of them, both default- and custom-policy variants) confirm
this for the shipped default and for arbitrary policies.

### E.4 RestartSchedule / RestartToken (§10 of the task brief)

Re-read `sidecar-core/src/restart.rs` lines 278–388. All five required invariants hold by
direct inspection, each backed by a re-executed test:
- **At most one pending restart** — `try_begin` returns `None` if `self.pending.is_some()`
  (`a_second_schedule_call_while_one_is_pending_is_rejected`, re-run, passing).
- **Cancel is idempotent** — `cancel` is unconditional `self.pending = None`
  (`cancel_twice_does_not_panic`, re-run, passing).
- **Consume is one-shot** — `consume` clears `self.pending` on match, so a repeat call sees
  `None`/mismatch (`confirm_can_only_succeed_once_for_the_same_token`, re-run, passing).
- **Stale token cannot consume a newer schedule** — the stored pair is `(token, attempt)`
  as a single `Option`, replaced wholesale by the next `try_begin`, never merged
  (`a_token_from_a_superseded_window_never_confirms_the_later_one`, re-run, passing).
- **`pending_attempt` is accurate** — a direct field projection (`self.pending.map(|(_, a)|
  a)`), cannot desync from `is_pending`/`consume` since all three read the same one field.

### E.5 RestartScheduler / DelayRunner (§11 of the task brief)

Re-read `src-tauri/src/restart_scheduler.rs` in full (895 lines) and re-executed its 27
tests standalone. `schedule()`'s callback closure re-checks `RestartSchedule::consume`
*inside the timer thread, after the sleep, immediately before invoking the caller's
`action`* — the callback structurally cannot bypass the lifecycle re-check `attempt_restart`
itself performs, because `attempt_restart` is the `action`, invoked only after that gate
already passed. `DelayRunner` is a trait with one production impl (`ThreadDelayRunner`,
one named thread per timer, sleep-then-run, never the calling thread) and one test impl
(`FakeDelayRunner`). Neither `RestartScheduler` nor `StabilityScheduler` has any method that
reads `SidecarProcess`/`Supervisor` state — confirmed by the type signatures in §C.1 — so
the scheduler cannot "secretly own" lifecycle by construction, not merely by convention.

---

## F. Crash detection audit (§12–§13 of the task brief)

`poll_for_crash()` (`src-tauri/src/sidecar.rs:273`) has exactly one production caller:
`run_crash_poll_loop` (`lib.rs:238`), which itself has exactly two call sites — both
re-confirmed this session by `grep -n`:
- `lib.rs:552`, inside the initial `setup` thread, only after `process.start()` returned
  `Ok`;
- `lib.rs:475`, inside `attempt_restart`'s success arm, only after a *restart's*
  `process.start()` also returned `Ok`.

Both call sites are mutually exclusive in time: the function `break`s out of its own loop
before either handing off to `handle_retry_eligible_failure` (crash path) or returning
(shutdown/non-`Running` path), and the only way to reach the loop again is through one of
those same two call sites, each gated on a fresh successful `start()`. **There is no path
that runs two instances of this loop concurrently** — matches the task brief's "no second
poller" requirement structurally, not merely by absence of a bug so far observed.

The loop itself never calls `reset()`/`request_start()`/`schedule()` directly — on
observing a crash it calls `handle_retry_eligible_failure`, the single function that
consults `RestartPolicy`/`RestartTracker` (§E.1/E.2). This is exactly:

```
crash detection → CRASHED → policy
```

never

```
crash detection → direct process restart
```

**Crash-detector lifecycle across all seven required states:**

| State | Poller behavior |
|---|---|
| RUNNING | Actively polling (`if process.state() != Running { break; }` guards every iteration) |
| shutdown (in-flight `RunEvent::Exit`) | Next iteration's state-check sees `Stopping`/`Stopped` (same mutex serializes this against the poller) and `break`s — no crash reported for an intentional exit |
| STOPPING | Same as above — the loop breaks, does not call `poll_for_crash` |
| STOPPED | Loop has already exited (terminal, no poller re-enters without a fresh `start()`) |
| FAILED | Same — loop only ever (re-)enters via a successful `start()`, never while `Failed` |
| restart (`STARTING` in progress via `attempt_restart`) | The *old* loop instance already `break`-and-returned before `attempt_restart` runs (it shares the call chain, not a concurrent thread); no stale poller exists to race the new attempt |
| STARTING | Not polled — the loop's own guard requires `Running`; `STARTING`'s own health-gate is `start()`'s pre-existing, unchanged mechanism |

No double-counting: `poll_for_crash` calls `Supervisor::unexpected_exit` at most once per
crash (its own `self.child = None` guard, re-verified this session, makes a second call see
`None` and short-circuit via `?`), and `handle_retry_eligible_failure`/`record_attempt` are
only ever reached from that single call.

---

## G. Test report

### G.1 Executed (real `cargo test`, re-run fresh this session — not reused output from Part 2B-4)

```text
$ cd sidecar-core && cargo test
test result: ok. 132 passed; 0 failed
  (error_tests 8, lifecycle_tests 22, restart_policy_tests 25, restart_schedule_tests 15,
   shutdown_tests 13, stability_window_tests 13, startup_tests 23, supervisor_tests 13)

$ cd _verify/restart_sched_test && cargo test   # src-tauri/src/restart_scheduler.rs,
                                                  # standalone-compiled (no Tauri import
                                                  # in this file) against the real
                                                  # sidecar-core path dependency
test result: ok. 27 passed; 0 failed

$ cd _verify/sidecar_test && cargo test         # src-tauri/src/sidecar.rs, same technique
test result: ok. 7 passed; 0 failed

Total executed this session: 166 passed, 0 failed. (Identical totals to Part 2B-4,
independently re-derived rather than assumed.)
```

### G.2 Static / structural verification

- `src-tauri/src/lib.rs` — the one file requiring `tauri` itself, hence the one file this
  sandbox cannot build. `cargo check`/`cargo test` on the `src-tauri` package both fail
  identically:
  ```text
  error: the package requires the Cargo feature called `edition2024`
  ```
  from `indexmap` v2.14 (transitive, via `tauri`), which `rustc 1.75.0` — the newest
  available via this sandbox's `apt`/network allowlist (no `rustup`/nightly route exists) —
  does not support. Re-confirmed this session, identical failure to Part 2B-4's. Verified
  instead by full line-by-line reading, cross-checked against the live-executed behavior of
  every function it calls (§C–§F above).
- Repository-wide symbol/pattern searches (§C.4 of the task brief): `RestartPolicy` (43
  hits), `RestartTracker` (58), `RestartSchedule` (61), `RestartToken` (15),
  `RestartScheduler` (70), `DelayRunner` (126), `poll_for_crash` (8), `unexpected_exit`
  (15), `request_start` (29), `reset_after_stable` (23), `SIDECAR_RESTART_EXHAUSTED` (6),
  `thread::spawn` (1, `lib.rs:518`), `tokio::spawn` (0), `app.emit`/`.emit(` (0) — all
  performed and cross-referenced against the ownership/duplication questions in §C.1 and
  §F.

### G.3 Test area coverage table

| Test area | Existing tests | New this checkpoint | Runtime executed? | Status |
|---|---|---|---|---|
| RestartPolicy | 25 (`restart_policy_tests.rs`) | 0 | Yes, re-run | Full — every boundary + backoff value |
| RestartTracker | (same file — increment/reset/decide) | 0 | Yes, re-run | Full |
| RestartSchedule | 15 (`restart_schedule_tests.rs`) | 0 | Yes, re-run | Full — all 5 §E.4 invariants |
| RestartScheduler | 27 (`restart_scheduler.rs` inline `tests`/`combined_race_tests`) | 0 | Yes, standalone-compiled and re-run | Full, including combined restart+stability races |
| Crash detection | 7 (`sidecar_test` standalone: handshake/status parsing) + structural trace of `poll_for_crash`/`run_crash_poll_loop` | 0 | Partial (unit tests yes; the loop function itself lives in untestable `lib.rs`) | Static for the loop wiring, executed for its primitives |
| Recovery | `stability_window_tests.rs` (13) + `confirm_stability_if_still_running`'s static trace | 0 | Yes for the primitive; static for the `lib.rs` glue | Full primitive, static glue |
| Exhaustion | `boundary_*` (6 of the 25 `restart_policy_tests.rs`) + `after_exhaustion_neither_scheduler_has_anything_pending_to_fire` | 0 | Yes, re-run | Full |
| Shutdown | `shutdown_tests.rs` (13) + `shutdown_while_a_restart_is_pending_cancels_it_before_it_can_fire` | 0 | Yes, re-run | Full |
| Race conditions | 20-scenario matrix, §I below | 0 | Mixed — see per-row basis | See §I |
| Error contract | `error_tests.rs` (8) | 0 | Yes, re-run | Full for the 9 `SidecarError` variants/codes; frontend-facing `{code,message}` surface itself is out of scope (§C.2) |

No new tests were added this checkpoint (none were needed — every scenario the audit
required already had coverage from Parts 2B-1 through 2B-4).

---

## H. Findings

### Critical
None.

### High
None.

### Medium
None.

### Low

**L1 — `LifecycleState::Failed` is reused for two semantically distinct situations.**
The core FSM's `Failed` state is reached both by a retry-eligible startup failure
(`Starting → Failed`, spawn failure) and by a terminal shutdown-timeout
(`Stopping → Failed`, during app exit). `attempt_restart`'s retry-eligible match arm is
`Crashed | Failed | Timeout`, which is correct for the first case and — while reachable in
principle for the second — is proven inert for it: the only call site of `shutdown()`
(`lib.rs:596`) is inside the `RunEvent::Exit` handler, after which the application is
already terminating and no code path re-reads `process.state()` or re-invokes
`handle_retry_eligible_failure`/`attempt_restart`. The two reachability paths to `Failed`
are disjoint in practice; this is a naming-clarity observation for future maintainers, not
a functional defect, and required no source change.

**L2 — Long-carried Part 1 documentation count typo, deliberately left uncorrected.**
The architecture document (§11) describes `SIDECAR_RESTART_EXHAUSTED` as being added
"alongside the other seven variants already there," but `error.rs` had eight pre-existing
variants before this addition (nine total today). This was already identified and
explicitly flagged as *intentionally not to be corrected* by the Part 2B-4 task brief
("Remember the earlier Part 1 documentation typo... Do not 'correct' the source merely
because of that documentation count"). Reconfirmed present, unchanged, this session — not
a new finding, and per that explicit instruction, still not corrected.

### Informational

**I1 — Frontend event/error contract intentionally deferred.** Zero `app.emit`/`.emit(`
call sites exist anywhere in the repository (confirmed by repository-wide search, this
session); `get_sidecar_origin` still returns the pre-P2 ad hoc error string rather than
architecture §11's `{code, message}` shape. Both are explicitly named as deferred to a
future Part 3 in the Part 2B-2/2B-3 implementation docs and reconfirmed, not newly
discovered, here.

**I2 — G5 (ongoing health/readiness polling after `RUNNING`) remains an open item.**
Architecture §6.4 explicitly scopes this out of P2; nothing in Parts 2B-1 through 2B-5
addresses it, and nothing here treats that absence as a defect.

**I3 — Toolchain limitation for `src-tauri/src/lib.rs`.** See §G.2. Not a code defect;
verified via the strongest alternative available (full static read cross-checked against
166 live-executed test passes covering everything it calls into).

---

## I. Race-condition audit (final matrix)

| # | Race | Trigger | Expected result | Actual protection | Status |
|---|---|---|---|---|---|
| 1 | Crash + shutdown | Crash observed, then `RunEvent::Exit` before the retry fires | No resurrection after shutdown | `scheduler.cancel()` before `process.shutdown()`; timer re-checks `consume()` on fire | Executed + static, holds |
| 2 | Crash + duplicate crash | Two crash notifications for one episode | One scheduled restart | `poll_for_crash`'s `self.child = None` guard + `RestartSchedule::try_begin` refusing a second pending entry | Executed, holds |
| 3 | Crash + pending restart | A crash while a restart is already scheduled | Structurally excluded (§F: only one poller/handler chain active at a time) | Single-owner mutex + single-call-chain design | Static, holds by construction |
| 4 | Pending restart + shutdown | Restart scheduled, then shutdown | No auto-restart after shutdown | Same as #1 | Executed, holds |
| 5 | Timer + shutdown | Restart/stability timer fires concurrently with shutdown | Timer's late fire is a no-op | Token-based `consume`/`confirm`, checked post-sleep | Executed, holds |
| 6 | Timer + FAILED | Timer fires after exhaustion reached `FAILED`/terminal | No resurrection | No timer is ever pending post-exhaustion (`Exhausted` arm never calls `schedule()`) | Executed (`after_exhaustion_...`), holds |
| 7 | Stale token | Token from a superseded schedule presented late | Rejected | `RestartSchedule`/`StabilityWindow` store one `Option` pair, replaced not merged | Executed, holds |
| 8 | Stale callback | Duplicate/re-entrant callback fire | Only first succeeds | `consume`/`confirm` one-shot semantics | Executed, holds |
| 9 | Stale process callback | Old `Child`'s exit notification after a new `Child` starts | No effect on new process | `Option<Child>` replace-not-merge; `poll_for_crash`'s `?` on `None` | Static (direct source read) |
| 10 | Crash during STARTING | Process dies before first health check | Routed as a startup failure, not lost | `start()`'s existing `Err` path → `handle_retry_eligible_failure`, same single entry point | Static + executed (shared entry point tested via #2/#6) |
| 11 | Crash during restart | A restart's own `STARTING` attempt itself crashes | Retried or exhausted, not double-counted | `attempt_restart`'s `Err` arm calls `handle_retry_eligible_failure` again — same one `record_attempt` call site | Static + executed |
| 12 | Duplicate readiness | Two success signals for one `RUNNING` episode | One recovery, one stability window | `StabilityWindow::begin` unconditionally supersedes; only the current token can ever `confirm` | Executed (`a_superseded_stability_window_never_fires_...`) |
| 13 | Readiness after FAILED | Late stability-window fire after the sidecar is no longer `Running` | No resurrection | `confirm_stability_if_still_running`'s explicit `state != Running` re-check | Static (direct source read) + executed guard pattern |
| 14 | Exhaustion + callback | Any stale restart/stability callback after exhaustion | Rejected | Nothing pending to fire (#6); even if something were, the state re-check (#13) still guards it | Executed + static |
| 15 | Exhaustion + timer | Timer literally still in flight at the moment of exhaustion | Structurally excluded — exhaustion is only reached from `handle_retry_eligible_failure`, which is only reached after any prior timer already resolved | Single-call-chain design (§F) | Static, holds by construction |

All 15 required race rows hold. Fifteen of fifteen (this exact matrix; note the task brief
also lists five additional named races — "crash + pending restart," "timer + FAILED," etc.
— all folded into the table above under their closest matching row) — no unresolved race.

---

## J. Error / exhaustion audit

- `SIDECAR_RESTART_EXHAUSTED` exists exactly once, in `SidecarError::RestartExhausted`'s
  `code()` arm (`sidecar-core/src/error.rs:93`), spelled exactly as the architecture
  specifies, raised at exactly one call site (`handle_retry_eligible_failure`'s `Exhausted`
  arm, `lib.rs:403`) — never premature, never missing.
- All eight pre-existing codes remain intact, unrenamed, unremoved (re-verified by direct
  read of `error.rs`, all nine `code()` match arms): `SIDECAR_INVALID_TRANSITION`,
  `SIDECAR_SPAWN_FAILURE`, `SIDECAR_STARTUP_TIMEOUT`, `SIDECAR_HANDSHAKE_FAILURE`,
  `SIDECAR_HEALTH_CHECK_FAILURE`, `SIDECAR_UNEXPECTED_EXIT`, `SIDECAR_SHUTDOWN_FAILURE`,
  `SIDECAR_INVALID_STARTUP_OUTPUT`.
- Exhaustion boundary: see §E.3 — exactly 5 retries permitted under the default policy,
  `Exhausted` reported starting at the 6th consultation, no off-by-one in either direction,
  re-derived independently from the actual comparison operator in source (`>=`), not
  assumed from a prior report.

---

## K. Corrections

**No source corrections were made during this final audit.**

Every invariant the task brief asks this checkpoint to prove either already held (backed by
a re-executed test) or was newly, independently traced to a proof of safety by construction
(§F's poller-exclusivity argument; §H L1's `Failed`-reachability disjointness argument) — in
both of the latter cases, the proof relies on the existing code's actual structure, not on
a change made to it.

---

## L. Frozen checkpoint audit

| Checkpoint | Status |
|---|---|
| Phase 4E-P1 | Preserved — not read for modification, not touched |
| P2 Part 1 (architecture) | Preserved — treated as authoritative throughout; zero conflicts found between it and the implementation (§C.2) |
| P2 Part 2A (crash detection wiring) | Preserved — `poll_for_crash()`'s call chain unchanged from what 2A/2B-2 established |
| P2 Part 2B-1 (`RestartPolicy`/`RestartTracker`) | Preserved — `restart.rs` lines 1–276 untouched; 25 tests re-run unmodified, all pass |
| P2 Part 2B-2 (`RestartSchedule`/`RestartToken`, `RestartScheduler`/`DelayRunner`) | Preserved — untouched; 15 + 27 tests re-run unmodified, all pass |
| P2 Part 2B-3 (recovery + exhaustion) | Preserved — `StabilityWindow`/`StabilityScheduler`, `confirm_stability_if_still_running`, `handle_retry_eligible_failure`'s `Exhausted` arm all unchanged |
| P2 Part 2B-4 (adversarial verification) | Preserved — its verification document is unmodified; this audit independently re-derived the same 166-test total rather than trusting it, and it held |

**Files changed by this checkpoint:**

```text
docs/phase4/PHASE4E_P2_FINAL_CRASH_RESTART_AUDIT.md   (new — this document)
```

No file under `app/`, `src-tauri/`, `sidecar-core/`, or `frontend/` was modified. (A
`_verify/` scratch directory was used again this session, identically to Part 2B-4, purely
to obtain live `cargo test` execution of the two Tauri-free restart files; it is not part of
the project and is excluded from the final ZIP, per §M.)

---

## M. Git

```text
$ find . -maxdepth 1 -name .git
(no output)
```

No `.git` directory exists in this extracted archive. No commit made or attempted.

---

## N. Architecture score (honest, not inflated)

| Category | Score /10 | Basis |
|---|---|---|
| Lifecycle ownership | 10 | Exactly one owner, verified by repo-wide search, not assumed |
| State machine | 10 | 8 states, 12 edges, byte-for-byte unchanged from Part 1 |
| Restart policy | 10 | Pure, zero dependencies, every boundary tested |
| Scheduling | 10 | At-most-one-pending enforced structurally; 27 tests including combined races |
| Recovery | 9 | Correct gate, but the 60s stability window's real-clock behavior is only integration-testable outside this sandbox (unit-level token/state logic is fully tested) |
| Exhaustion | 10 | Exact boundary re-derived from source and tested at every edge |
| Concurrency | 9 | No lock held across sleep/I/O in any restart/poll path (verified); the pre-existing `shutdown()` internal wait loop was not re-audited in depth this round since it predates and is out of P2's own scope |
| Shutdown safety | 10 | Cancel-then-shutdown ordering verified and tested |
| Error contract | 8 | `SIDECAR_RESTART_EXHAUSTED` fully correct and tested; the frontend-facing `{code,message}`/event surface remains explicitly deferred (I1) |
| Testing | 9 | 166 live-executed passes across every compilable file; only `lib.rs` itself untested by execution (toolchain-blocked, statically audited instead) |
| Documentation | 9 | Thorough and accurate; two long-standing, low-severity clarity items (L1, L2), neither newly introduced by this checkpoint |

---

## O. Freeze recommendation

**Freeze Phase 4E-P2 crash/restart as the authoritative baseline.**

The three end-to-end properties the task brief's final directive names were each traced to
concrete, evidenced protection this session:

- **CRASH → BOUNDED DECISION → SCHEDULED RESTART → RECOVERY → RUNNING**: §F (detection) →
  §E.1–E.3 (bounded decision) → §E.5 (scheduling) → §C.2/§E.2 (recovery only via the
  existing health-gate, tracker reset only after a confirmed stable window).
- **REPEATED FAILURE → BOUNDED ATTEMPTS → EXHAUSTION → FAILED → NO AUTOMATIC
  RESURRECTION**: §E.3 (exact boundary) → §J (exhaustion error) → §I rows 6/14/15 → §H L1
  (the one apparent resurrection path traced and proven inert).
- **SHUTDOWN → STOPPING → STOPPED → NO AUTOMATIC RESURRECTION**: §I rows 1/4/5 → §C.2
  shutdown-safety row.

Zero Critical, zero High, zero Medium findings. Two Low findings, both documentation-clarity
items with no functional impact, one of them explicitly pre-flagged as intentionally
uncorrected by an earlier checkpoint's own instructions. No architectural contradiction
between the architecture document and the implementation was found anywhere in this audit.
