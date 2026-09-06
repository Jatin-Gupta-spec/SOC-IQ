//! Typed error model.
//!
//! Categories mirror `docs/phase4/PHASE4_PRE_2A_CONTRACT.md` §3 exactly
//! (names kept identical to the contract table — the contract explicitly
//! allows renaming to match project convention, but SOC-IQ's existing
//! convention, per `docs/contracts/error-model.md`, is specific/named
//! error types, which these already are). `InvalidTransition` is added
//! for the lifecycle state machine itself, which the contract's table
//! does not need to cover since it is Part 1's own internal concern.

use crate::state::LifecycleState;

/// All typed errors `sidecar-core` can produce. Every variant carries
/// context useful for diagnosing what happened, without leaking
/// implementation details (e.g. no raw OS error structs, no process
/// internals) — per the task brief §5.
#[derive(Debug, thiserror::Error, Clone, PartialEq, Eq)]
pub enum SidecarError {
    /// Requested transition is not in the contract's transition table.
    #[error("invalid lifecycle transition: {from} -> {to}")]
    InvalidTransition {
        from: LifecycleState,
        to: LifecycleState,
    },

    /// The child process could not be created at all (binary missing,
    /// permission denied, etc). Contract §3.
    #[error("sidecar process could not be spawned: {reason}")]
    SpawnFailure { reason: String },

    /// Process spawned but the readiness handshake/health-check did not
    /// complete within the configured startup timeout. Contract §3.
    #[error("sidecar did not become ready within {elapsed_ms}ms (limit {limit_ms}ms)")]
    StartupTimeout { elapsed_ms: u64, limit_ms: u64 },

    /// Startup output was received but was malformed/unparseable.
    /// Contract §3.
    #[error("startup handshake output was malformed: {detail}")]
    HandshakeFailure { detail: String },

    /// `/health` was reachable but returned a non-success response.
    /// Contract §3. Part 1 represents this category for completeness;
    /// nothing in Part 1 actually calls `/health` (no real I/O — task
    /// brief §6).
    #[error("health check failed: {detail}")]
    HealthCheckFailure { detail: String },

    /// The process exited on its own while previously `RUNNING`
    /// (a crash). Contract §3/§9.
    #[error("sidecar exited unexpectedly (exit code: {exit_code:?})")]
    UnexpectedExit { exit_code: Option<i32> },

    /// The process did not terminate within the shutdown timeout (even
    /// after escalation, per contract §4). Contract §3.
    #[error("sidecar did not shut down within {elapsed_ms}ms (limit {limit_ms}ms)")]
    ShutdownFailure { elapsed_ms: u64, limit_ms: u64 },

    /// A more specific case of `HandshakeFailure`: output that parses
    /// but contains an invalid value (e.g. an out-of-range port).
    /// Contract §3.
    #[error("startup output parsed but was invalid: {detail}")]
    InvalidStartupOutput { detail: String },

    /// Automatic restart attempts were exhausted (Phase 4E-P2 Part
    /// 2B-3; architecture doc §6.5/§7.6/§11). Raised exactly once, at
    /// the moment `RestartTracker::decide` first reports
    /// `RestartDecision::Exhausted` for the current crash-loop window —
    /// never for an ordinary retry-eligible failure, which uses
    /// whichever of the categories above actually occurred instead.
    /// `attempts` is the final attempt count (`policy.max_attempts`).
    #[error("sidecar restart attempts exhausted after {attempts} attempt(s)")]
    RestartExhausted { attempts: u32 },
}

impl SidecarError {
    /// Stable, machine-readable code for this error category, following
    /// the `{ code, message }` convention documented in
    /// `docs/contracts/error-model.md` — so that whichever later phase
    /// wires this into the Tauri command/event boundary has a code to
    /// surface immediately rather than inventing one then. This is the
    /// only place in `sidecar-core` that anticipates that future wiring;
    /// nothing else in this crate assumes it exists.
    pub fn code(&self) -> &'static str {
        match self {
            SidecarError::InvalidTransition { .. } => "SIDECAR_INVALID_TRANSITION",
            SidecarError::SpawnFailure { .. } => "SIDECAR_SPAWN_FAILURE",
            SidecarError::StartupTimeout { .. } => "SIDECAR_STARTUP_TIMEOUT",
            SidecarError::HandshakeFailure { .. } => "SIDECAR_HANDSHAKE_FAILURE",
            SidecarError::HealthCheckFailure { .. } => "SIDECAR_HEALTH_CHECK_FAILURE",
            SidecarError::UnexpectedExit { .. } => "SIDECAR_UNEXPECTED_EXIT",
            SidecarError::ShutdownFailure { .. } => "SIDECAR_SHUTDOWN_FAILURE",
            SidecarError::InvalidStartupOutput { .. } => "SIDECAR_INVALID_STARTUP_OUTPUT",
            SidecarError::RestartExhausted { .. } => "SIDECAR_RESTART_EXHAUSTED",
        }
    }
}
