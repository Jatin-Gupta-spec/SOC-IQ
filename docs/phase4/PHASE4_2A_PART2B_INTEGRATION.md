# Phase 2A Part 2B — Real Process Integration

**Status:** IMPLEMENTED, **NOT VERIFIED BY COMPILATION** — see §5 "Verification" before treating
this as frozen. Builds on the frozen Part 1 + Part 2 (hardening) foundation in
`docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md` and the vocabulary in
`docs/phase4/PHASE4_PRE_2A_CONTRACT.md`.

## 1. What Part 2B adds

A new module, `src-tauri/src/sidecar.rs`, implementing the "future Tauri/native adapter" that
`sidecar-core`'s own doc comments have described since Part 1 — the layer that actually spawns
the Python sidecar, actually reads its stdout handshake, actually polls `/health` over a real
TCP connection, and actually waits for/kills the OS process on shutdown. `sidecar-core` itself
performs none of this (see its crate-level "Hard architectural boundary" doc, unchanged since
Part 1) — this module is where those real observations originate before being reported to the
`Supervisor` through its existing public event methods.

`src-tauri/Cargo.toml` now depends on `sidecar-core` via a path dependency. No other new
dependency was added — `src/sidecar.rs` uses only `std::process`, `std::net::TcpStream`, and
`std::time`, deliberately avoiding `tokio`/`reqwest` (see that module's doc comment for the
rationale).

## 2. What remains owned by Part 2A (`sidecar-core`)

Unchanged: the lifecycle state machine, the transition table, the typed error model, the
timeout configuration type, and the `Supervisor`'s event-driven API. Part 2B's adapter calls
these exactly as a caller was always expected to (`request_start`, `spawn_failed`,
`validate_handshake`, `handshake_failed`, `health_check_succeeded`, `startup_timed_out`,
`request_shutdown`, `process_exited`, `shutdown_timed_out`, `unexpected_exit`) — no internal
state is read or mutated directly from outside `sidecar-core`. There remains exactly one
lifecycle owner.

## 3. One Part 2A correction: the handshake wire format

Adversarial inspection of the real, already-frozen Python sidecar (`app/api/entrypoint.py`,
covered by `tests/test_sidecar_entrypoint.py`'s real-subprocess integration test) found it emits
`print(bound_port, flush=True)` — a **bare decimal integer**, not the `SOCIQ_SIDECAR_PORT=<port>`
prefixed line `sidecar-core::parse_handshake_line` (Part 1) expected. That prefix was Part 1's
own invented wire format, self-documented at the time as never cross-checked against the real
process. Wiring a real adapter to the old parser would never have succeeded against the process
it must actually supervise.

**Fix:** `sidecar-core/src/startup.rs`'s `parse_handshake_line` now accepts a bare decimal port
(trimming surrounding whitespace/newline), matching the real sidecar exactly. The `HANDSHAKE_PREFIX`
constant was removed (no longer meaningful). `sidecar-core/tests/startup_tests.rs` was rewritten
to the corrected format, preserving the full Part 1 + Part 2 coverage matrix (valid parse,
trailing newline, empty line, non-numeric, zero port, out-of-range port, negative-looking value,
trailing garbage, repeated/deterministic parsing, handshake-after-timeout, handshake-after-shutdown)
plus two Part 2B additions (a float-shaped value, and unsplit multi-line input) and one
now-inverted case (the *old* prefixed format is itself now a malformed-input test case). No
lifecycle/state-machine/error-model test was touched.

This is the only place Part 2B modified already-frozen Part 1/Part 2 code. No other file under
`sidecar-core/` changed.

## 4. Lifecycle ownership and integration boundaries

```
SidecarProcess (src-tauri/src/sidecar.rs)
    owns: Child (OS process handle), wall clock (Instant), TCP health-check socket
    reports to -> Supervisor (sidecar-core)  [single source of truth for state]
```

- `SidecarProcess::start()` — `NOT_STARTED → STARTING`, spawns the real process, blocks reading
  one stdout line (the handshake), validates it via the (now-corrected) parser, then polls
  `/health` on a 100ms interval until success or the configured startup timeout elapses. Any
  failure path kills and reaps the child before reporting the corresponding terminal state to
  the supervisor.
- `SidecarProcess::shutdown()` — `RUNNING → STOPPING → STOPPED`, sends a kill signal and waits
  (bounded by the configured shutdown timeout) for the OS to confirm exit before reporting
  success; a timeout reports `ShutdownFailure`.
- `SidecarProcess::poll_for_crash()` — non-blocking; exposes the `RUNNING → CRASHED` observation
  primitive for a later phase's background poll loop to drive. Part 2B does not itself run that
  loop (see §6, scope).

### Kill signal: hard kill, not graceful SIGTERM

`std::process::Child::kill()` is a hard kill on both Unix (SIGKILL) and Windows
(`TerminateProcess`) — the standard library has no portable graceful-terminate primitive. A real
SIGTERM-first escalation needs a platform-specific dependency (`libc` on Unix, `windows` on
Windows) that was not added. Part 2B's `shutdown()` sends the hard kill immediately: this is
contract-safe (the sidecar has no unflushed state of its own — persistent writes happen in the
Python domain/database layer, which this process boundary never touches directly) and still
waits for confirmed exit before returning, so the "no orphaned process" invariant
(`PHASE4_PRE_2A_CONTRACT.md` §4) holds either way. A graceful escalation path is deferred, not
silently dropped — noted explicitly in `sidecar.rs`'s module doc as a known follow-up.

## 5. Verification

| Check | Result |
|---|---|
| `python3 -m pytest tests/` | PASS — 574 passed, 0 failed (unchanged from the Part 2A freeze — Part 2B touched no Python file) |
| `npm run typecheck` / `npm run build` (frontend/) | PASS — unaffected; Part 2B touched no frontend file |
| `cargo check` / `cargo test` (sidecar-core, src-tauri) | **NOT RUN — no `rustc`/`cargo` binary exists in this sandbox at all.** This is a harder blocker than the Part 2A freeze's "toolchain too old" finding: there is no Rust toolchain here whatsoever. |

**Consequence:** `src/sidecar.rs` (the new adapter), the rewritten `startup.rs`, and the
rewritten `startup_tests.rs` have **never been compiled**, not by this task and not by any prior
task in this project's history (the Part 2A freeze report recorded the same gap for the
already-existing `sidecar-core` code). This is a real, unverified-code risk — not a formality —
and is reported here rather than assumed away.

No "genuine `Rust supervisor → real Python sidecar → startup handshake → health check → clean
shutdown` round trip" integration test (`PHASE4_PRE_2A_CONTRACT.md` §6) was added, for the same
reason: adding an untested integration test on top of never-compiled code would not constitute
real verification, and would risk misrepresenting the phase as more verified than it is.

## 6. Scope: what was deliberately NOT implemented

- No `#[tauri::command]` and no wiring of `SidecarProcess` into `run()` / the Tauri application
  builder. `src-tauri/src/lib.rs` declares `mod sidecar;` so the module compiles and its unit
  tests run as part of the crate, but nothing in the running application constructs or drives a
  `SidecarProcess` yet.
- No background crash-poll loop or event emission wiring `poll_for_crash()` into an actual timer
  or Tauri event.
- No graceful (SIGTERM-first) shutdown escalation (§4).
- No React/frontend changes, no new UI, no database changes, no unrelated refactoring — the diff
  is confined to `sidecar-core/src/startup.rs`, `sidecar-core/src/lib.rs`,
  `sidecar-core/tests/startup_tests.rs`, `src-tauri/src/sidecar.rs` (new),
  `src-tauri/src/lib.rs`, `src-tauri/Cargo.toml`, and this documentation.

These are all future-phase functionality per the task brief's own "do not pull future work
forward" rule, not oversights.

## 7. Freeze recommendation

**NOT FROZEN.** Per the task brief's own rule: "If those conditions are not satisfied, STOP and
report the blocker instead of pretending the phase is complete." The blocking condition is
narrow and specific: **no Rust code in this repository, old or new, has ever been compiled in
any environment used across this project's history.** Everything checkable without a Rust
toolchain — the Python regression suite, the frontend build, the architectural boundary
(dependency direction, single lifecycle owner, no business logic leakage), and the contract
cross-check that found and fixed the handshake format bug — has been verified and passes.

**Required before this can be called frozen:** run `cargo check` and `cargo test --workspace` (or
equivalent per-crate commands) on a machine with a real Rust toolchain (`sidecar-core` needs
≥1.75; `src-tauri`'s Tauri dependency graph needs ≥1.85, per the Part 2A freeze report's prior
finding), fix anything that fails to compile or fails a test, and re-run the Python suite once
more to confirm no cross-language regression. `Cargo.lock` will also need to be regenerated/
updated on that machine, since it predates the new `sidecar-core` path dependency added here.
