# Pre-2A Sidecar Contract (Documentation Only)

**Status:** Documentation Foundation. No code in this document is implemented by this
checkpoint — see `docs/phase4/PHASE4_CHECKPOINT_NAMING.md` for what "Phase 2A" means here.
**Builds on:** `docs/phase4/PHASE4E_SIDECAR_TAURI_SCOPE.md` (architecture, non-goals, staged
migration, §9 test strategy), `docs/security/ipc-security-model.md` (loopback/ephemeral-port
design, CSP note).

This document exists so Phase 2A has one place that defines the vocabulary it must implement
against, rather than inferring it from prose scattered across the scope doc. It does not
change any decision already made in `PHASE4E_SIDECAR_TAURI_SCOPE.md` — it makes a subset of
that document's intent explicit and named.

## 1. Sidecar Lifecycle States

```
NOT_STARTED
    ↓ (spawn requested)
STARTING
    ↓ (health check succeeds within timeout)
RUNNING
    ↓ (shutdown requested)
STOPPING
    ↓ (process exits)
STOPPED
```

Failure transitions:

```
STARTING → FAILED     (process could not be spawned at all — see SpawnFailure)
STARTING → TIMEOUT    (process spawned but never became healthy in time)
RUNNING  → CRASHED    (process exited unexpectedly while previously healthy)
STOPPING → FAILED     (process did not exit within the shutdown timeout)
```

`FAILED`, `TIMEOUT`, and `CRASHED` are terminal states requiring a fresh `NOT_STARTED → STARTING`
transition to recover — Phase 2A does not need an automatic-retry state machine at this
checkpoint; that is an explicit future enhancement, not an implicit requirement.

## 2. Startup Contract

- The sidecar signals readiness only via a successful `GET /health` response (per
  `PHASE4E_SIDECAR_TAURI_SCOPE.md` §4 P0-2) — process-alive is necessary but not sufficient;
  a process that is running but has not yet bound its port or finished initialization is
  still `STARTING`, not `RUNNING`.
- Required startup information the supervisor needs before it can consider the sidecar
  reachable: the bound loopback port (ephemeral, per `ipc-security-model.md`).
- **Port communication:** via a synchronous startup handshake (print-then-flush on the
  child's stdout, read by the parent before polling begins) — not a hard-coded port, not a
  race-prone "assume it's ready after N seconds." This mirrors
  `PHASE4E_SIDECAR_TAURI_SCOPE.md` §10 risk #2's mitigation.
- **Malformed startup output:** if the handshake line is not parseable as the expected
  port announcement, the supervisor treats this as `StartupTimeout`/`HandshakeFailure` (§3
  below) rather than guessing a port or retrying indefinitely.
- **No startup output arrives:** bounded by a startup timeout; on expiry the supervisor
  transitions `STARTING → TIMEOUT` and does not leave the child process running
  unsupervised — it is killed as part of the timeout handling.
- **Readiness vs. process-alive:** process-alive (the OS reports the PID still running) is
  a precondition for polling `/health`, never a substitute for it. A process can be alive
  and not ready (still importing/initializing).
- **Health-check expectations:** `/health` has no database or domain dependency (P0-2,
  already the case in the frozen Python API layer) so a health-check failure means the
  process itself is unhealthy, not that some downstream dependency is slow.
- **Timeout expectations:** both the startup handshake and the health-poll loop are
  bounded; neither Phase 2A implementation may block indefinitely on either step.

## 3. Error Model

Typed error categories Phase 2A's Rust supervisor must distinguish (names may be adapted to
existing project error-naming conventions in `docs/contracts/error-model.md`, but the
categories below must all be representable):

| Category | Meaning |
|---|---|
| `SpawnFailure` | The child process could not be created at all (binary missing, permission denied, etc.) |
| `StartupTimeout` | Process spawned but the readiness handshake/health-check did not complete in time |
| `HandshakeFailure` | Startup output was received but malformed/unparseable |
| `HealthCheckFailure` | `/health` was reachable but returned a non-success response |
| `UnexpectedExit` | The process exited on its own while previously `RUNNING` (crash) |
| `ShutdownFailure` | The process did not terminate within the shutdown timeout |
| `InvalidStartupOutput` | A more specific case of `HandshakeFailure` for output that parses but contains an invalid value (e.g. an out-of-range port) |

This is a documentation-only taxonomy — no error enum is added to `src-tauri/` by this
checkpoint (Cargo.toml intentionally has no process/async dependency yet — see §7 of the
foundation report).

## 4. Shutdown Contract

- **Normal application shutdown:** the supervisor sends a termination signal to the sidecar
  and waits (bounded) for exit before allowing the Tauri app itself to fully close.
- **Sidecar already exited:** shutdown is a no-op that succeeds immediately — not an error.
- **Unexpected sidecar exit** (while `RUNNING`): treated as `UnexpectedExit`/`CRASHED`, not
  as a shutdown path; the supervisor does not attempt to "shut down" a process that is
  already gone.
- **Shutdown timeout:** if the process does not exit within the bounded wait, the supervisor
  escalates (e.g. a harder kill signal) rather than waiting indefinitely; this is recorded as
  `ShutdownFailure` if even the escalation does not result in exit.
- **Repeated start/stop:** each `NOT_STARTED → STARTING → RUNNING → STOPPING → STOPPED` cycle
  must leave no orphaned process; Phase 2A's lifecycle test (§5 below) must include at least
  one repeated cycle, not only a single spawn/kill.
- **Application termination:** the sidecar must never outlive the Tauri process — no
  orphaned child on abnormal Tauri exit (crash/panic), per
  `PHASE4E_SIDECAR_TAURI_SCOPE.md` §10 risk #1.

## 5. Security Boundary (Trust Boundary)

```
React  →  Tauri/Rust  →  sidecar process  →  Python API
```

| Layer | Responsibility |
|---|---|
| React | UI, presentation, client state, motion, user interaction only |
| Tauri/Rust | Desktop boundary, capabilities, process lifecycle, sidecar supervision, secure native integration |
| Python | Application/domain logic, database, threat intelligence, analysis, reporting |

Hard rules (already established, restated here for Phase 2A's benefit):

- No business logic in Rust — the supervisor manages a process and speaks HTTP to it; it
  never re-implements or duplicates domain logic (ADR-004, ADR-006).
- React never accesses SQLite or external threat-intelligence providers directly — every
  such call is mediated through the Tauri → sidecar → Python path.
- See `docs/security/ipc-security-model.md` for the loopback-bind/ephemeral-port/CSP details
  this boundary depends on.

## 6. Phase 2A Test Strategy

Minimum test surface (builds on, does not replace,
`PHASE4E_SIDECAR_TAURI_SCOPE.md` §9):

```
Supervisor construction
Successful startup
Startup timeout
Malformed startup output
Health-check success
Health-check failure
Unexpected process exit
Normal shutdown
Shutdown timeout/failure
Repeated lifecycle operations (at least one full stop/start cycle)
Typed error mapping (§3 categories all reachable/testable)
```

Plus the real integration test named in `PHASE4E_SIDECAR_TAURI_SCOPE.md` §9's "New Rust-side
lifecycle test": a genuine `Rust supervisor → real Python sidecar → startup handshake →
health check → clean shutdown` round trip, not a mocked process.

None of the above is implemented by this checkpoint — this section exists so Phase 2A's own
test plan does not have to be re-derived from scratch.
