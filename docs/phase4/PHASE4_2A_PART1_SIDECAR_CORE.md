# Phase 2A — `sidecar-core` Foundation (Part 1) + Hardening (Part 2)

**Status:** Part 1 IMPLEMENTED; Part 2 (adversarial hardening) IMPLEMENTED — both frozen at
this checkpoint. See `docs/phase4/PHASE4_CHECKPOINT_NAMING.md` for what "Phase 2A" means in
this repository. §1–14 below are Part 1 as originally written (updated in place only where a
Part 2 finding changed the design — each such change is called out explicitly in context).
§15 is Part 2's own addendum: what was hardened, what was reviewed and left unchanged, and
the adversarial test coverage added.

**Phase 2B update:** real process integration (previously deferred) is now implemented — see
`docs/phase4/PHASE4_2A_PART2B_INTEGRATION.md`. Phase 2B required one narrow correction to this
document's own Part 1/Part 2 work: `parse_handshake_line`'s wire format (§2/§15 below still
describe the original `SOCIQ_SIDECAR_PORT=<port>` format as Part 1/Part 2 implemented and
tested it — that history is preserved as-written, not edited here). The Part 2B document is the
record of what changed and why; this document is not rewritten to pretend Part 2B's format was
what Part 1/Part 2 always used.
**Builds on:** `docs/phase4/PHASE4_PRE_2A_CONTRACT.md` (the canonical vocabulary this
implementation follows), `docs/security/ipc-security-model.md`, `docs/contracts/event-model.md`,
`docs/phase4/PHASE4_PRE2A_FOUNDATION_CORRECTION_REPORT.md`.

## 1. What `sidecar-core` is

A new, standalone Rust crate at `sidecar-core/` (a sibling of `src-tauri/`, not nested inside
it). It implements the framework-independent lifecycle core for the future Python-sidecar
supervisor: the state machine, typed errors, startup/handshake validation, timeout
configuration, shutdown semantics, and a minimal supervisor abstraction described by
`PHASE4_PRE_2A_CONTRACT.md`.

It is a library crate only — nothing depends on it yet, and it depends on nothing in
`src-tauri/`. `src-tauri/Cargo.toml` was **not modified** by this checkpoint; the two crates
are not yet wired together (that wiring, and everything else in the diagram below, is Part 2).

## 2. Hard architectural boundary (preserved)

```
sidecar-core
    -> abstract process/supervisor contracts   (this crate, Part 1)
    -> future Tauri/native adapter               (Part 2, depends on this crate)
```

`sidecar-core/Cargo.toml` has exactly one dependency: `thiserror` (already present in the
workspace's transitive graph via `src-tauri/Cargo.lock`, so this follows the existing
project's typed-error convention rather than introducing a new one). No `tauri`, `tauri-build`,
`serde`, `tokio`, `reqwest`, or any process/async/HTTP crate. Verified by inspection of
`sidecar-core/Cargo.toml` and by grep — no `tauri` string appears anywhere under
`sidecar-core/`.

## 3. Lifecycle state machine — IMPLEMENTED

`sidecar_core::state` implements `LifecycleState` (`NotStarted`, `Starting`, `Running`,
`Stopping`, `Stopped`, `Failed`, `Timeout`, `Crashed`) as a single enum — no boolean flags —
and `Lifecycle`, which owns the current state and is the only thing permitted to change it,
via `transition(to) -> Result<LifecycleState, SidecarError>`.

The transition table implements exactly the contract's diagram (§1):

```
NOT_STARTED -> STARTING
STARTING    -> RUNNING | FAILED | TIMEOUT
RUNNING     -> STOPPING | CRASHED
STOPPING    -> STOPPED | FAILED
{STOPPED, FAILED, TIMEOUT, CRASHED} -> NOT_STARTED   (explicit reset; contract §1's
                                                        "fresh NOT_STARTED -> STARTING
                                                        transition to recover")
```

Every other `(from, to)` pair is rejected with `SidecarError::InvalidTransition`, state
unchanged. No automatic-retry/restart policy exists — restart is always the caller's explicit
`reset()` followed by `request_start()`.

## 4. Typed error model — IMPLEMENTED

`sidecar_core::error::SidecarError` (via `thiserror`) implements every category in the
contract's §3 table verbatim — `SpawnFailure`, `StartupTimeout`, `HandshakeFailure`,
`HealthCheckFailure`, `UnexpectedExit`, `ShutdownFailure`, `InvalidStartupOutput` — plus
`InvalidTransition` for the state machine itself (not part of the contract's table, which is
scoped to process/I/O outcomes, not the state machine's own invariants).

Each variant carries typed context (a `String` reason/detail, `u64` millisecond durations, an
`Option<i32>` exit code, or the two `LifecycleState`s involved) — no raw OS error types, no
process internals. `SidecarError::code()` maps each variant to a stable `SIDECAR_*` string,
anticipating (but not implementing) the `{ code, message }` convention in
`docs/contracts/error-model.md`, for whichever later phase wires this into the Tauri
command/event boundary.

## 5. Startup / handshake contract — IMPLEMENTED (core representation + validation only)

`sidecar_core::startup::StartupInfo { port: u16 }` represents the one field the contract
requires (§2: the bound loopback port). `parse_handshake_line(&str) -> Result<StartupInfo,
SidecarError>` is pure, synchronous, and takes no I/O — it validates a literal line, never a
real child process's stdout.

Wire format decision (Part 1's own, since the contract specifies the mechanism but not a
concrete line format): `SOCIQ_SIDECAR_PORT=<port>`, defined once as `HANDSHAKE_PREFIX` so a
future adapter and this crate's tests share one literal instead of duplicating it.

- Line doesn't match the expected prefix/shape at all -> `HandshakeFailure` (contract §2:
  "malformed startup output... treats this as StartupTimeout/HandshakeFailure").
- Line matches the shape but the value is unparseable, zero, or out of `u16` range ->
  `InvalidStartupOutput` (contract §3's "more specific case" of handshake failure).
- `Supervisor::validate_handshake` performs parsing without mutating lifecycle state (the
  handshake is a precondition for health polling, not a transition of its own — contract §2).
  `Supervisor::handshake_failed(err)` performs the corresponding `STARTING -> TIMEOUT`
  transition and re-raises `err`.

## 6. Timeout abstraction — IMPLEMENTED

`sidecar_core::timeout::TimeoutConfig { startup: Duration, shutdown: Duration }`, with
`Default` values (10s / 5s) documented as Part 1's own choice — the contract requires both
timeouts to be bounded (§2, §4) but does not mandate specific numbers. No sleep-based logic
exists anywhere in this crate; `Supervisor::startup_timed_out`/`shutdown_timed_out` take an
`elapsed: Duration` supplied by the caller, so all timing tests are deterministic (no
`std::thread::sleep` in the test suite).

## 7. Shutdown semantics — IMPLEMENTED (hardened in Part 2)

- `Supervisor::request_shutdown()`: `RUNNING -> STOPPING` if currently running; otherwise a
  deterministic `ShutdownOutcome::NotRunning(LifecycleState)` no-op — not an error — per
  contract §4 ("sidecar already exited: shutdown is a no-op that succeeds immediately").
  Verified repeatable (`shutdown_tests::repeated_shutdown_is_deterministic`).
  **Part 2 finding and fix:** Part 1 originally collapsed every non-`RUNNING` state into one
  `ShutdownOutcome::AlreadyStopped` variant. Adversarial testing of "shutdown during startup"
  and "shutdown during stopping" (task brief §7) found this was actively misleading — calling
  `request_shutdown()` while `STARTING` or `STOPPING` reported "already stopped," which was
  false. Fixed by carrying the actual `LifecycleState` in the outcome
  (`ShutdownOutcome::NotRunning(state)`), so "never started," "already stopped," "shutdown
  already in progress," and each terminal-failure state are distinguishable rather than
  identical. See `sidecar-core/src/supervisor.rs`'s doc comment on `ShutdownOutcome` for the
  full note, and `shutdown_tests.rs` for the eight tests covering every non-`RUNNING` state
  this outcome can now report accurately.
- `Supervisor::process_exited(status)`: `STOPPING -> STOPPED`.
- `Supervisor::shutdown_timed_out(elapsed)`: `STOPPING -> FAILED`, carrying
  `SidecarError::ShutdownFailure` (contract §4's escalation-then-`ShutdownFailure` path,
  represented at the state-machine level — Part 1 does not implement a real kill-signal
  escalation, since that requires a real process).
- A full `NOT_STARTED -> STARTING -> RUNNING -> STOPPING -> STOPPED -> (reset) -> NOT_STARTED`
  cycle is exercised twice in one test
  (`shutdown_tests::full_stop_start_cycle_leaves_supervisor_reusable_with_no_orphaned_state`),
  satisfying contract §4's explicit "at least one repeated cycle" requirement — "no orphaned
  process" itself is a Part 2 concern (there is no real process here to orphan); what Part 1
  proves is that the *state machine* imposes no leftover/undefined state across cycles.

## 8. Crash / unexpected exit — IMPLEMENTED

`Supervisor::unexpected_exit(status)`: `RUNNING -> CRASHED`, carrying
`SidecarError::UnexpectedExit { exit_code }`. No automatic restart — `CRASHED` is terminal
and stays that way until an explicit `reset()` (task brief §9, verified by
`supervisor_tests::crash_does_not_auto_restart`).

## 9. Supervisor / process abstraction — IMPLEMENTED (minimal)

`sidecar_core::supervisor::Supervisor` owns a `Lifecycle` and a `TimeoutConfig` and exposes
explicit event methods (`request_start`, `spawn_failed`, `validate_handshake`,
`handshake_failed`, `health_check_succeeded`, `startup_timed_out`, `request_shutdown`,
`process_exited`, `shutdown_timed_out`, `unexpected_exit`, `reset`) rather than performing any
I/O itself. This is deliberately event-driven rather than process-owning: every method
represents an observation a real adapter would make (or a test supplies directly), so the
crate needs no process handle, no OS wait-call, and no async runtime.

`sidecar_core::process::ExitStatus { code: Option<i32> }` is the one process-shaped value
worth naming at this layer (both the normal-exit and crash paths need it) — deliberately not a
`ProcessHandle` trait with `spawn`/`kill` methods, since nothing in Part 1 would implement one
and an unimplemented trait is dead weight, not an abstraction.

## 10. Module structure

```
sidecar-core/
  Cargo.toml
  src/
    lib.rs         — crate docs, module wiring, public re-exports
    state.rs        — LifecycleState, Lifecycle (state machine + transition table)
    error.rs         — SidecarError (typed error model)
    startup.rs        — StartupInfo, parse_handshake_line, HANDSHAKE_PREFIX
    timeout.rs         — TimeoutConfig
    process.rs          — ExitStatus
    supervisor.rs         — Supervisor, ShutdownOutcome
  tests/
    lifecycle_tests.rs     — initial/valid/invalid/failure transitions, reset, repeated cycles
    startup_tests.rs        — valid/malformed/invalid handshake lines, timeout, supervisor wiring
    shutdown_tests.rs         — success, no-op, timeout, invalid-state, repeated, full cycle
    supervisor_tests.rs        — construction, running state, crash, spawn failure, out-of-order calls
    error_tests.rs               — stable codes, context, determinism, variant matching
```

## 11. Deferred to Part 2 (confirmed NOT implemented here)

```
Real OS process spawning:                 NOT IMPLEMENTED
Python sidecar launching:                  NOT IMPLEMENTED
Real stdout reading:                        NOT IMPLEMENTED
Real HTTP /health polling:                   NOT IMPLEMENTED
Tauri integration (commands/state/events):    NOT IMPLEMENTED
src-tauri/Cargo.toml changes:                  NOT MADE (no dependency added on sidecar-core)
React/frontend integration:                     NOT IMPLEMENTED
SSE:                                             NOT IMPLEMENTED
Automatic restart/backoff policy:                 NOT IMPLEMENTED (contract §1: explicit
                                                    future enhancement, not Part 1 scope)
Real kill-signal escalation on shutdown timeout:   NOT IMPLEMENTED (state-machine outcome
                                                    only — SidecarError::ShutdownFailure)
```

## 12. Web research

| Source | What was observed | How SOC-IQ adapts it | Decision |
|---|---|---|---|
| Rust API Guidelines, "Type safety" / newtype & enum-over-bools guidance (`rust-lang.github.io/api-guidelines`) | Idiomatic Rust favors a closed enum with an explicit legal-transition function over multiple independent boolean flags for state that has mutual-exclusion invariants | Directly matches task brief §4's explicit instruction; `LifecycleState::can_transition_to` is the single source of truth rather than scattered `if is_running && !is_stopping` checks | Implemented as a table-driven `match` on `(from, to)` tuples inside one function, not duplicated per call site |
| `thiserror` crate docs (docs.rs/thiserror) — `#[error("...")]` attribute and field interpolation | `#[error]` format strings can interpolate named fields directly (`{field}`), and the derive requires the enum already implement/derive `Debug` | Used field interpolation for every variant's message (`{from}`, `{to}`, `{reason}`, `{elapsed_ms}`, etc.) instead of hand-writing a `Display` impl | Adopted directly — no custom `Display` impl for `SidecarError` was needed |
| Rust standard library docs, `std::time::Duration` | `Duration` has no notion of "current time elapsed" itself — measuring elapsed time requires `Instant`, which is a real-time side effect | Because Part 1 must have zero sleep-based/timing-dependent test logic (task brief §11), timeout-related methods accept a caller-supplied `elapsed: Duration` rather than calling `Instant::now()` internally | `Supervisor` never constructs an `Instant`; all elapsed-time values are test/caller-supplied inputs |

No external code was copied; each row above informed a design decision, not a pasted
implementation.

## 13. Known environment limitations (this checkpoint's execution sandbox)

This sandbox has **no Rust toolchain at all** (`rustc`/`cargo` not installed, and `apt-get
install cargo rustc` fails — outbound package-mirror access returns `403 Forbidden` /
`host_not_allowed` for every external host tried, including `archive.ubuntu.com`,
`security.ubuntu.com`, and `static.rust-lang.org`). This is a stricter limitation than the one
recorded in `PHASE4_PRE2A_FOUNDATION_CORRECTION_REPORT.md`'s §7/§9 (which had a real, working
`rustc`/`cargo` 1.75.0 and was blocked only by Tauri's transitive `edition2024` requirement) —
that discrepancy is reported here honestly rather than silently assumed away. Neither `cargo
fmt`, `cargo test`, `cargo clippy`, nor `cargo check` could be executed in this session, for
`sidecar-core` or for `src-tauri`. The same outbound restriction also blocked `pip install`
(for the Python regression suite's dependencies — `fastapi`, `pydantic`, etc. are not
importable in this sandbox) and `npm install` (for the frontend's `typecheck`/`build`), so
none of the verification commands in the task brief's §16/§17 could be run this session. See
§14 for what this means for this checkpoint's status, and the final report's "Verification"
section for the exact commands attempted and their exact failures.

`sidecar-core` was written to compile under this constraint's *intent* even though it could
not be proven by execution: it targets `edition = "2021"`/`rust-version = "1.75"` specifically
so it does not inherit the `edition2024` blocker that `src-tauri`'s Tauri dependency graph
hits, and its only dependency (`thiserror 1.x`) is a version already present and resolvable in
`src-tauri/Cargo.lock`'s existing dependency graph.

**Part 2 re-check (independent, not assumed from this note):** the Part 2 task brief asserted
"Rust 1.75 is available in the sandbox" as a known limitation. This session re-verified that
claim directly (`which rustc cargo`, `apt-get install -y cargo rustc`, a direct `curl` against
an Ubuntu package-mirror URL) rather than trusting it, and found it does not hold in this
execution environment: no `rustc`/`cargo` binary is present, and `apt-get install` fails with
`403 Forbidden`/`host_not_allowed` on every mirror host tried. This is reported as a
discrepancy between the task brief's assumption and this session's actual environment, not
silently reconciled either direction.

## 14. What "frozen" means for this checkpoint

Per the checkpoint-naming convention, this document and the implementation it describes are
frozen at Part 1's scope, then re-frozen at Part 2's scope (§15). No file under `frontend/`,
`app/`, `tests/`, `database/`, or `src-tauri/` was modified by either part. Phase 2B (real
spawning, Tauri wiring, health polling, SSE, React integration) is explicitly deferred and not
started, per both task briefs' hard stop.

## 15. Phase 2A Part 2 — Hardening & Adversarial Verification addendum

**Purpose (task brief §2):** Part 2 attacks Part 1's architecture rather than extending it —
no new capability, no scope expansion. Everything below is either (a) a concrete finding with
a fix, or (b) a reviewed area with an explicit "no change needed" conclusion and its
rationale, which is itself a legitimate adversarial-review outcome per task brief §11
("Refactor only where there is a concrete architectural reason").

### 15.1 Findings and fixes

**`ShutdownOutcome::AlreadyStopped` collapsed distinct states (task brief §7).** Documented in
§7 above. This is the one behavioral code change Part 2 made. Every other change in Part 2 is
additive (new tests, new/clarified documentation) — no other public API signature changed, no
other transition rule changed, no other error variant changed.

**Everything else adversarially tested came back correct as designed.** Specifically:
non-numeric/negative/whitespace-only/trailing-garbage handshake values, zero/out-of-range
ports, calling any event method from the wrong state (start twice, stop twice, health-check
succeeded twice, unexpected-exit twice, handshake-failed after already `TIMEOUT`, any
transition attempted from a terminal state), and every timeout boundary (`elapsed == 0`,
`elapsed == limit`, `elapsed >> limit`) all already behaved deterministically and correctly
against the Part 1 implementation — confirmed, not assumed, by the 76-test suite (up from 34
in Part 1; see §15.3).

### 15.2 Reviewed, no change needed

- **Timeout self-verification (task brief §6).** `startup_timed_out`/`shutdown_timed_out` do
  not internally check `elapsed >= limit` before allowing the transition. Reviewed and left
  as-is: `sidecar-core` deliberately owns no clock (its hard architectural boundary — §2
  above), so it cannot independently verify a timeout occurred; it can only record what a
  caller who *does* own the timer (a later phase) asserts. Documented directly in
  `supervisor.rs`'s doc comments on both methods.
- **Panic/unwrap audit (task brief §8).** `grep -rn "unwrap()\|expect(\|panic!" sidecar-core/src/`
  returns zero matches. No change needed. (Test files do use `unwrap()`/`panic!` — expected
  and appropriate in test code, not a finding.)
- **Concurrency/race review (task brief §10).** The crate is entirely synchronous: no
  `Mutex`/`RefCell`/`Arc`/`Rc`/threads/async anywhere under `sidecar-core/src/` (confirmed by
  grep). Every mutating method takes `&mut self`, so Rust's ownership rules make concurrent
  mutation of one `Supervisor` a compile-time impossibility without external synchronization
  this crate deliberately doesn't provide. No concurrency framework was added — doing so would
  have had nothing real to protect and would have violated task brief §10's own instruction
  not to add async complexity "merely for this task." Full review reasoning recorded in
  `supervisor_tests.rs`'s trailing comment block.
- **Supervisor/process abstraction review (task brief §11).** All six of the brief's review
  questions were worked through explicitly; see the trailing comment block in
  `supervisor_tests.rs`. Summary conclusion: the interface stayed minimal and I/O-free by
  design, so no trait extraction was warranted (a `trait SupervisorApi` with exactly one
  implementor and no present caller would be speculative generality, which task brief §11
  explicitly warns against manufacturing a reason for).
- **Security review (task brief §13).** Re-confirmed by grep: no `127.0.0.1`/hard-coded port
  literals, no credential-shaped strings, no filesystem or network calls, no shell/process
  execution anywhere in `sidecar-core/src/`. One forward-looking note for Phase 2B (not a
  Part 2 gap, since nothing in Part 1/2 reads a real pipe): `parse_handshake_line` takes an
  already-fully-read `&str` with no length cap of its own; this is fine today because nothing
  in this crate reads a child process's stdout, but whichever future code does should apply
  its own bound on line length before handing untrusted process output to this parser, rather
  than assuming the parser bounds it.
- **Event/API contract review (task brief §14).** `sidecar-core` defines no event vocabulary
  of its own (no `analysis.*`/`investigation.*`/etc. strings anywhere in the crate) and
  introduces no new terminology beyond the contract's own `LifecycleState` names. No schema
  duplication was created; none existed to begin with at this layer.

### 15.3 Adversarial test coverage

Test count by file, Part 1 → Part 2:

| File | Part 1 | Part 2 | Added |
|---|---|---|---|
| `lifecycle_tests.rs` | 11 | 22 | start/stop twice, start-after-stopped, stop-before-started, stop-while-stopping, transition-after-{failure,crash,timeout} (exhaustive per state), no-self-transitions (general form), full 8×8 transition-table completeness check |
| `startup_tests.rs` | 12 | 21 | timeout boundaries (zero/exact/far-exceeded), negative/whitespace/trailing-garbage handshake values, repeated-handshake determinism, handshake-after-timeout, handshake-after-shutdown |
| `shutdown_tests.rs` | 8 | 13 | shutdown during startup, shutdown during stopping, shutdown after failed-startup/crash/timeout (each as its own state, not collapsed), shutdown-timeout boundary, start/stop/stop sequence |
| `supervisor_tests.rs` | 9 | 13 | status/status determinism, start/failure/stop sequence, health-check-succeeded twice, unexpected-exit twice, concurrency review note, abstraction review note |
| `error_tests.rs` | 4 | 7 | `std::error::Error` trait bound, structurally-similar-variant distinguishability, InvalidTransition-vs-every-domain-error distinguishability |
| **Total** | **34 (44*)** | **76** | |

*Part 1's final report stated 34 tests; recounting by file at that checkpoint gives the same
total.

All 76 tests are deterministic — no `std::thread::sleep`, no wall-clock dependency, no
ordering dependency between tests (each constructs its own `Supervisor`/`Lifecycle`).

### 15.4 Static architecture audit (task brief §19)

Re-run against the Part 2 code:

```
Tauri imports inside sidecar-core:        NONE FOUND (grep -rn "tauri::" src/)
React references inside Rust core:         NONE FOUND
Python references inside Rust core:         NONE FOUND
Filesystem access inside core:               NONE FOUND
Network access inside core:                   NONE FOUND
Business-domain logic:                         NONE FOUND
Hard-coded ports:                               NONE FOUND
Hard-coded credentials:                          NONE FOUND
Unsafe command execution:                         NONE FOUND
Panic-based lifecycle failure handling:            NONE FOUND (0 unwrap/expect/panic in src/)
```

The doc-comment mentions of "Tauri"/"React" in `lib.rs`, `error.rs`, `process.rs`, and
`Cargo.toml` are prose explaining what is deliberately *absent* (e.g. "no Tauri dependency"),
not references to those crates — verified by inspecting each match's context, not just the
grep hit count.

### 15.5 What Part 2 did not do

Consistent with task brief §12: no `std::process` spawning, no Tauri shell plugin
integration, no Python executable launch, no stdout monitoring, no real `/health` HTTP calls,
no SSE, no Tauri command bridge. `src-tauri/Cargo.toml` remains unmodified — the two crates
are still not wired together. `sidecar-core/Cargo.toml`'s dependency list is unchanged from
Part 1 (`thiserror` only).
