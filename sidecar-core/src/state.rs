//! Lifecycle state machine.
//!
//! States and the transition table below are the canonical vocabulary
//! from `docs/phase4/PHASE4_PRE_2A_CONTRACT.md` §1. This module invents
//! no second vocabulary and represents the lifecycle as a single enum
//! rather than a set of boolean flags, per the task brief §4.

use crate::error::SidecarError;
use std::fmt;

/// Canonical sidecar lifecycle states.
///
/// ```text
/// NOT_STARTED
///     -> STARTING            (spawn requested)
/// STARTING
///     -> RUNNING              (health check succeeds within timeout)
///     -> FAILED                (spawn failure)
///     -> TIMEOUT                (readiness handshake/health-check did not complete in time)
/// RUNNING
///     -> STOPPING              (shutdown requested)
///     -> CRASHED               (process exited unexpectedly while healthy)
/// STOPPING
///     -> STOPPED               (process exits)
///     -> FAILED                (did not exit within the shutdown timeout)
/// ```
///
/// `FAILED`, `TIMEOUT`, `CRASHED`, and `STOPPED` are terminal: recovery
/// requires an explicit [`Lifecycle::transition`] back to `NOT_STARTED`
/// before a fresh `NOT_STARTED -> STARTING` cycle (contract §1's
/// "requiring a fresh NOT_STARTED -> STARTING transition to recover").
/// Part 1 implements no automatic-retry state machine — restart is
/// always an explicit, separate caller action.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum LifecycleState {
    NotStarted,
    Starting,
    Running,
    Stopping,
    Stopped,
    Failed,
    Timeout,
    Crashed,
}

impl LifecycleState {
    /// Terminal states, per contract §1: `STOPPED` is included because
    /// contract §4's "repeated start/stop" cycle also re-enters via
    /// `NOT_STARTED`, not directly from `STOPPED`.
    pub fn is_terminal(self) -> bool {
        matches!(
            self,
            LifecycleState::Stopped
                | LifecycleState::Failed
                | LifecycleState::Timeout
                | LifecycleState::Crashed
        )
    }

    /// Whether `self -> to` is a transition the contract permits.
    /// Every arm not listed here is an invalid transition and is
    /// rejected by [`Lifecycle::transition`].
    pub fn can_transition_to(self, to: LifecycleState) -> bool {
        use LifecycleState::*;
        matches!(
            (self, to),
            (NotStarted, Starting)
                | (Starting, Running)
                | (Starting, Failed)
                | (Starting, Timeout)
                | (Running, Stopping)
                | (Running, Crashed)
                | (Stopping, Stopped)
                | (Stopping, Failed)
                | (Stopped, NotStarted)
                | (Failed, NotStarted)
                | (Timeout, NotStarted)
                | (Crashed, NotStarted)
        )
    }
}

impl fmt::Display for LifecycleState {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        let s = match self {
            LifecycleState::NotStarted => "NOT_STARTED",
            LifecycleState::Starting => "STARTING",
            LifecycleState::Running => "RUNNING",
            LifecycleState::Stopping => "STOPPING",
            LifecycleState::Stopped => "STOPPED",
            LifecycleState::Failed => "FAILED",
            LifecycleState::Timeout => "TIMEOUT",
            LifecycleState::Crashed => "CRASHED",
        };
        write!(f, "{s}")
    }
}

/// Owns the current [`LifecycleState`] and enforces the transition
/// table. This is the single source of truth for "is this transition
/// allowed" — callers never mutate state directly.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Lifecycle {
    state: LifecycleState,
}

impl Default for Lifecycle {
    fn default() -> Self {
        Self::new()
    }
}

impl Lifecycle {
    /// A freshly constructed lifecycle always starts `NOT_STARTED`.
    pub fn new() -> Self {
        Self {
            state: LifecycleState::NotStarted,
        }
    }

    pub fn state(&self) -> LifecycleState {
        self.state
    }

    /// Attempt a transition to `to`. On success, the internal state is
    /// updated and the new state is returned. On an invalid transition,
    /// state is left unchanged and a typed [`SidecarError::InvalidTransition`]
    /// is returned — invalid transitions are rejected explicitly, never
    /// silently ignored or coerced.
    pub fn transition(&mut self, to: LifecycleState) -> Result<LifecycleState, SidecarError> {
        if self.state.can_transition_to(to) {
            self.state = to;
            Ok(to)
        } else {
            Err(SidecarError::InvalidTransition {
                from: self.state,
                to,
            })
        }
    }
}
