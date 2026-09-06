//! Shutdown tests.
//!
//! Part 1 minimum coverage (task brief §11 "Shutdown"): successful
//! shutdown, shutdown timeout, shutdown failure, shutdown from invalid
//! states, repeated shutdown.
//!
//! Part 2 adversarial coverage (task brief §7): normal shutdown,
//! repeated shutdown, shutdown after crash, shutdown after timeout,
//! shutdown after failed startup, shutdown when never started, shutdown
//! during startup, shutdown during stopping — using the hardened
//! `ShutdownOutcome::NotRunning(LifecycleState)` API (see
//! `supervisor.rs`'s "Part 2 hardening note" on `ShutdownOutcome`).

use sidecar_core::{
    ExitStatus, LifecycleState, ShutdownOutcome, SidecarError, Supervisor, TimeoutConfig,
};
use std::time::Duration;

fn running_supervisor() -> Supervisor {
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Running);
    supervisor
}

#[test]
fn successful_shutdown_running_to_stopping_to_stopped() {
    let mut supervisor = running_supervisor();
    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(outcome, ShutdownOutcome::Stopping);
    assert_eq!(supervisor.state(), LifecycleState::Stopping);

    supervisor.process_exited(ExitStatus::with_code(0)).unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Stopped);
}

#[test]
fn shutdown_when_never_started_is_a_no_op_success() {
    let mut supervisor = Supervisor::default();
    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(
        outcome,
        ShutdownOutcome::NotRunning(LifecycleState::NotStarted)
    );
    // No state change — shutdown-of-nothing is not an error and does
    // not pretend a transition happened.
    assert_eq!(supervisor.state(), LifecycleState::NotStarted);
}

#[test]
fn shutdown_during_startup_is_a_no_op_and_does_not_claim_stopped() {
    // Part 2 adversarial case (task brief §7 "shutdown during
    // startup"): the sidecar is actively starting, not stopped. The
    // hardened outcome must say STARTING, not lie that it's already
    // stopped (Part 1's collapsed AlreadyStopped variant would have).
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Starting);

    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(
        outcome,
        ShutdownOutcome::NotRunning(LifecycleState::Starting)
    );
    assert_eq!(supervisor.state(), LifecycleState::Starting);
}

#[test]
fn shutdown_during_stopping_reports_stopping_not_already_stopped() {
    // Part 2 adversarial case (task brief §7 "shutdown during
    // stopping" / §9 "stop(); stop()" while mid-shutdown): a second
    // shutdown request while STOPPING must not claim the process has
    // already stopped — it hasn't yet.
    let mut supervisor = running_supervisor();
    assert_eq!(
        supervisor.request_shutdown().unwrap(),
        ShutdownOutcome::Stopping
    );
    assert_eq!(supervisor.state(), LifecycleState::Stopping);

    let second = supervisor.request_shutdown().unwrap();
    assert_eq!(
        second,
        ShutdownOutcome::NotRunning(LifecycleState::Stopping)
    );
    assert_eq!(supervisor.state(), LifecycleState::Stopping);
}

#[test]
fn shutdown_after_failed_startup_is_a_no_op_success() {
    // Part 2 adversarial case (task brief §7 "shutdown after failed
    // startup").
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.spawn_failed("binary missing").ok();
    assert_eq!(supervisor.state(), LifecycleState::Failed);

    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(outcome, ShutdownOutcome::NotRunning(LifecycleState::Failed));
    assert_eq!(supervisor.state(), LifecycleState::Failed);
}

#[test]
fn shutdown_after_crash_is_a_no_op_success() {
    // Part 2 adversarial case (task brief §7 "shutdown after crash").
    let mut supervisor = running_supervisor();
    supervisor.unexpected_exit(ExitStatus::with_code(1)).ok();
    assert_eq!(supervisor.state(), LifecycleState::Crashed);

    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(
        outcome,
        ShutdownOutcome::NotRunning(LifecycleState::Crashed)
    );
    assert_eq!(supervisor.state(), LifecycleState::Crashed);
}

#[test]
fn shutdown_after_startup_timeout_is_a_no_op_success() {
    // Part 2 adversarial case (task brief §7 "shutdown after timeout").
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor
        .startup_timed_out(Duration::from_secs(99))
        .ok();
    assert_eq!(supervisor.state(), LifecycleState::Timeout);

    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(
        outcome,
        ShutdownOutcome::NotRunning(LifecycleState::Timeout)
    );
    assert_eq!(supervisor.state(), LifecycleState::Timeout);
}

#[test]
fn shutdown_timeout_transitions_stopping_to_failed() {
    let mut supervisor = Supervisor::new(TimeoutConfig::new(
        Duration::from_secs(10),
        Duration::from_secs(5),
    ));
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    supervisor.request_shutdown().unwrap();

    let err = supervisor
        .shutdown_timed_out(Duration::from_secs(6))
        .unwrap_err();
    match err {
        SidecarError::ShutdownFailure {
            elapsed_ms,
            limit_ms,
        } => {
            assert_eq!(elapsed_ms, 6_000);
            assert_eq!(limit_ms, 5_000);
        }
        other => panic!("expected ShutdownFailure, got {other:?}"),
    }
    assert_eq!(supervisor.state(), LifecycleState::Failed);
}

#[test]
fn shutdown_timeout_boundary_elapsed_equals_limit() {
    // Timeout boundary case (task brief §6): elapsed exactly equal to
    // the configured limit. sidecar-core owns no clock (see
    // supervisor.rs's Part 2 review note) so it records exactly what
    // the caller asserts, deterministically, at the boundary.
    let mut supervisor = Supervisor::new(TimeoutConfig::new(
        Duration::from_secs(10),
        Duration::from_secs(5),
    ));
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    supervisor.request_shutdown().unwrap();

    let err = supervisor
        .shutdown_timed_out(Duration::from_secs(5))
        .unwrap_err();
    assert_eq!(
        err,
        SidecarError::ShutdownFailure {
            elapsed_ms: 5_000,
            limit_ms: 5_000,
        }
    );
}

#[test]
fn shutdown_from_invalid_state_process_exited_is_rejected() {
    // process_exited() is only valid from STOPPING; calling it from
    // NOT_STARTED must be rejected, not silently accepted.
    let mut supervisor = Supervisor::default();
    let result = supervisor.process_exited(ExitStatus::unknown());
    assert!(matches!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::NotStarted,
            to: LifecycleState::Stopped,
        })
    ));
    assert_eq!(supervisor.state(), LifecycleState::NotStarted);
}

#[test]
fn repeated_shutdown_is_deterministic() {
    let mut supervisor = running_supervisor();
    assert_eq!(
        supervisor.request_shutdown().unwrap(),
        ShutdownOutcome::Stopping
    );
    supervisor.process_exited(ExitStatus::with_code(0)).unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Stopped);

    // Calling shutdown again (and again) after STOPPED must remain a
    // deterministic no-op success, never an error, never a state
    // change, and always reporting the same carried state.
    for _ in 0..3 {
        assert_eq!(
            supervisor.request_shutdown().unwrap(),
            ShutdownOutcome::NotRunning(LifecycleState::Stopped)
        );
        assert_eq!(supervisor.state(), LifecycleState::Stopped);
    }
}

#[test]
fn start_stop_stop_sequence_is_deterministic() {
    // Part 2 §9 explicit example: start(); stop(); stop() — the
    // sidecar never became RUNNING (no health_check_succeeded call),
    // so both shutdown calls are no-ops against STARTING, identically.
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    let first = supervisor.request_shutdown().unwrap();
    let second = supervisor.request_shutdown().unwrap();
    assert_eq!(first, second);
    assert_eq!(first, ShutdownOutcome::NotRunning(LifecycleState::Starting));
}

#[test]
fn full_stop_start_cycle_leaves_supervisor_reusable_with_no_orphaned_state() {
    let mut supervisor = running_supervisor();
    supervisor.request_shutdown().unwrap();
    supervisor.process_exited(ExitStatus::with_code(0)).unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Stopped);

    // Contract §4: repeated start/stop cycles must be possible. Reset,
    // then run a second full cycle.
    supervisor.reset().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::NotStarted);

    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Running);
    supervisor.request_shutdown().unwrap();
    supervisor.process_exited(ExitStatus::with_code(0)).unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Stopped);
}
