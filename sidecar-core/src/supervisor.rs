//! Minimal supervisor abstraction (task brief §10).
//!
//! [`Supervisor`] owns lifecycle state and enforces the pre-2A
//! contract's transition and error rules, but performs no I/O of its
//! own. It is driven entirely by explicit event methods representing
//! observations a future process adapter (Part 2) would make: spawn
//! requested, spawn failed, a handshake line arrived, a health check
//! result, the process exited, etc. This keeps `sidecar-core`
//! framework-independent — nothing here spawns a process, opens a
//! socket, or waits on a timer; a caller (test today, real adapter
//! later) supplies every observation and decides how time is measured.

use std::time::Duration;

use crate::error::SidecarError;
use crate::process::ExitStatus;
use crate::startup::{parse_handshake_line, StartupInfo};
use crate::state::{Lifecycle, LifecycleState};
use crate::timeout::TimeoutConfig;

/// Result of a shutdown request, distinguishing the contract's
/// "already exited -> no-op success" case (§4) from an active
/// `RUNNING -> STOPPING` transition still in progress.
///
/// **Part 2 hardening note:** Part 1 collapsed every non-`RUNNING`
/// state into a single `AlreadyStopped` variant. Adversarial review
/// (task brief §7 "shutdown during startup"/"shutdown during stopping")
/// found this was misleading: calling `request_shutdown()` while the
/// state was `STOPPING` or `STARTING` reported `AlreadyStopped`, which
/// is simply false — the sidecar had not stopped, and in the `STARTING`
/// case had not even run yet. No error was introduced (the contract's
/// "no-op success" rule is still correct in spirit for every
/// non-`RUNNING` state), but the outcome now carries the actual state
/// so a caller/log can't be told something happened that didn't.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ShutdownOutcome {
    /// A `RUNNING -> STOPPING` transition was made. The caller must
    /// still report the outcome via [`Supervisor::process_exited`] or
    /// [`Supervisor::shutdown_timed_out`] to complete the cycle.
    Stopping,
    /// No transition was made because the sidecar was not `RUNNING`.
    /// Always a no-op success per contract §4 — never an error — but
    /// callers can inspect the carried [`LifecycleState`] to tell
    /// "never started" apart from "already stopped" apart from
    /// "shutdown already in progress" apart from a terminal failure
    /// state, rather than all four being reported identically.
    NotRunning(LifecycleState),
}

/// Framework-independent sidecar lifecycle supervisor.
#[derive(Debug)]
pub struct Supervisor {
    lifecycle: Lifecycle,
    timeouts: TimeoutConfig,
}

impl Default for Supervisor {
    fn default() -> Self {
        Self::new(TimeoutConfig::default())
    }
}

impl Supervisor {
    pub fn new(timeouts: TimeoutConfig) -> Self {
        Self {
            lifecycle: Lifecycle::new(),
            timeouts,
        }
    }

    pub fn state(&self) -> LifecycleState {
        self.lifecycle.state()
    }

    pub fn timeouts(&self) -> TimeoutConfig {
        self.timeouts
    }

    /// `NOT_STARTED -> STARTING`: spawn requested.
    pub fn request_start(&mut self) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Starting)?;
        Ok(())
    }

    /// Record that the OS-level spawn call itself failed.
    /// `STARTING -> FAILED`. Contract §3 `SpawnFailure`.
    pub fn spawn_failed(&mut self, reason: impl Into<String>) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Failed)?;
        Err(SidecarError::SpawnFailure {
            reason: reason.into(),
        })
    }

    /// Validate one handshake line without changing lifecycle state —
    /// the handshake is a precondition for health polling, not a state
    /// transition of its own (contract §2). On failure, the caller
    /// reports it via [`Supervisor::handshake_failed`], which does
    /// perform the state transition.
    pub fn validate_handshake(&self, line: &str) -> Result<StartupInfo, SidecarError> {
        parse_handshake_line(line)
    }

    /// Record a handshake failure (malformed/unparseable/invalid
    /// output). `STARTING -> TIMEOUT`, per contract §2: "the supervisor
    /// treats this as StartupTimeout/HandshakeFailure... rather than
    /// guessing a port or retrying indefinitely" — a malformed
    /// handshake is treated the same as never receiving one, so it
    /// shares the `TIMEOUT` destination rather than `FAILED` (which is
    /// reserved for the process not spawning at all).
    pub fn handshake_failed(&mut self, error: SidecarError) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Timeout)?;
        Err(error)
    }

    /// `STARTING -> RUNNING`: health check succeeded within the startup
    /// timeout.
    pub fn health_check_succeeded(&mut self) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Running)?;
        Ok(())
    }

    /// `STARTING -> TIMEOUT`: readiness handshake/health-check did not
    /// complete within `timeouts.startup`. Contract §3 `StartupTimeout`.
    /// The caller supplies `elapsed` (this crate performs no timing of
    /// its own — task brief §7/§11: no sleep-based logic here).
    ///
    /// **Part 2 review note:** this method does not itself verify
    /// `elapsed >= timeouts.startup` before allowing the transition.
    /// That is a deliberate boundary, not an oversight: `sidecar-core`
    /// owns no clock (by design — see the crate's hard architectural
    /// boundary), so it cannot independently confirm a timeout actually
    /// elapsed; it can only record what the caller — who does own the
    /// clock/timer in a later phase — asserts happened. Reviewed and
    /// left unchanged; see `docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md`
    /// §6 for the full rationale.
    pub fn startup_timed_out(&mut self, elapsed: Duration) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Timeout)?;
        Err(SidecarError::StartupTimeout {
            elapsed_ms: elapsed.as_millis() as u64,
            limit_ms: self.timeouts.startup.as_millis() as u64,
        })
    }

    /// `RUNNING -> STOPPING`, or a no-op success if not currently
    /// `RUNNING` (contract §4: "sidecar already exited: shutdown is a
    /// no-op that succeeds immediately — not an error"). Calling this
    /// repeatedly once stopped is deterministic: every call after the
    /// first returns the same `NotRunning(state)` again, never an
    /// error, for as long as the state doesn't change underneath it.
    pub fn request_shutdown(&mut self) -> Result<ShutdownOutcome, SidecarError> {
        let current = self.lifecycle.state();
        if current != LifecycleState::Running {
            return Ok(ShutdownOutcome::NotRunning(current));
        }
        self.lifecycle.transition(LifecycleState::Stopping)?;
        Ok(ShutdownOutcome::Stopping)
    }

    /// `STOPPING -> STOPPED`: process exit observed after a shutdown
    /// request.
    pub fn process_exited(&mut self, _status: ExitStatus) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Stopped)?;
        Ok(())
    }

    /// `STOPPING -> FAILED`: process did not exit within
    /// `timeouts.shutdown`, even after escalation (contract §4).
    /// Contract §3 `ShutdownFailure`. Same caller-trust boundary as
    /// [`Supervisor::startup_timed_out`] — see that method's Part 2
    /// review note.
    pub fn shutdown_timed_out(&mut self, elapsed: Duration) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Failed)?;
        Err(SidecarError::ShutdownFailure {
            elapsed_ms: elapsed.as_millis() as u64,
            limit_ms: self.timeouts.shutdown.as_millis() as u64,
        })
    }

    /// `RUNNING -> CRASHED`: process exited on its own while previously
    /// healthy. Contract §1/§9/§3 `UnexpectedExit`. Never automatic —
    /// Part 1 implements no restart policy (task brief §9).
    pub fn unexpected_exit(&mut self, status: ExitStatus) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::Crashed)?;
        Err(SidecarError::UnexpectedExit {
            exit_code: status.code,
        })
    }

    /// Any terminal state (`STOPPED`/`FAILED`/`TIMEOUT`/`CRASHED`) ->
    /// `NOT_STARTED`: the explicit recovery step the contract requires
    /// before a fresh `NOT_STARTED -> STARTING` cycle (§1). Restart is
    /// always this explicit call, never implicit.
    pub fn reset(&mut self) -> Result<(), SidecarError> {
        self.lifecycle.transition(LifecycleState::NotStarted)?;
        Ok(())
    }
}
