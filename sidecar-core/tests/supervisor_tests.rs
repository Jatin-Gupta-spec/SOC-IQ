//! Runtime/crash and supervisor-construction tests.
//!
//! Part 1 minimum coverage (task brief §11 "Runtime"): running state,
//! unexpected exit, crash transition. Also covers supervisor
//! construction and spawn failure, since those precede "running" in
//! the lifecycle.
//!
//! Part 2 adversarial coverage (task brief §9 "Repeated operations",
//! §11 "Supervisor abstraction review"): status()/status() determinism,
//! start()/failure/stop() sequencing, and confirmation that the
//! abstraction stays minimal (see the module doc note at the bottom of
//! this file for the review's conclusion).

use sidecar_core::{ExitStatus, LifecycleState, ShutdownOutcome, SidecarError, Supervisor, TimeoutConfig};

#[test]
fn supervisor_construction_starts_not_started() {
    let supervisor = Supervisor::default();
    assert_eq!(supervisor.state(), LifecycleState::NotStarted);
}

#[test]
fn supervisor_construction_with_explicit_timeouts() {
    let timeouts = TimeoutConfig::new(
        std::time::Duration::from_secs(20),
        std::time::Duration::from_secs(8),
    );
    let supervisor = Supervisor::new(timeouts);
    assert_eq!(supervisor.timeouts(), timeouts);
    assert_eq!(supervisor.state(), LifecycleState::NotStarted);
}

#[test]
fn successful_startup_reaches_running_state() {
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Starting);
    supervisor.health_check_succeeded().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Running);
}

#[test]
fn spawn_failure_transitions_starting_to_failed_with_reason() {
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    let err = supervisor.spawn_failed("binary not found").unwrap_err();
    match err {
        SidecarError::SpawnFailure { reason } => assert_eq!(reason, "binary not found"),
        other => panic!("expected SpawnFailure, got {other:?}"),
    }
    assert_eq!(supervisor.state(), LifecycleState::Failed);
}

#[test]
fn spawn_failed_called_out_of_order_is_rejected() {
    // spawn_failed is only valid from STARTING (STARTING -> FAILED).
    // Calling it before request_start() must reject the underlying
    // invalid transition rather than silently recording a spawn
    // failure that never happened.
    let mut supervisor = Supervisor::default();
    let result = supervisor.spawn_failed("should not apply");
    assert!(matches!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::NotStarted,
            to: LifecycleState::Failed,
        })
    ));
}

#[test]
fn unexpected_exit_while_running_transitions_to_crashed() {
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Running);

    let err = supervisor.unexpected_exit(ExitStatus::with_code(1)).unwrap_err();
    assert!(matches!(
        err,
        SidecarError::UnexpectedExit { exit_code: Some(1) }
    ));
    assert_eq!(supervisor.state(), LifecycleState::Crashed);
}

#[test]
fn unexpected_exit_with_unknown_code_is_represented() {
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();

    let err = supervisor.unexpected_exit(ExitStatus::unknown()).unwrap_err();
    assert!(matches!(
        err,
        SidecarError::UnexpectedExit { exit_code: None }
    ));
    assert_eq!(supervisor.state(), LifecycleState::Crashed);
}

#[test]
fn crash_does_not_auto_restart() {
    // No implicit recovery: after CRASHED, the supervisor stays
    // CRASHED until an explicit reset() call (task brief §9).
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    supervisor.unexpected_exit(ExitStatus::with_code(1)).ok();
    assert_eq!(supervisor.state(), LifecycleState::Crashed);

    // Still crashed one "tick" later — nothing auto-transitions it.
    assert_eq!(supervisor.state(), LifecycleState::Crashed);

    supervisor.reset().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::NotStarted);
}

#[test]
fn unexpected_exit_only_valid_from_running() {
    // RUNNING -> CRASHED only; calling it from NOT_STARTED is invalid.
    let mut supervisor = Supervisor::default();
    let result = supervisor.unexpected_exit(ExitStatus::with_code(1));
    assert!(matches!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::NotStarted,
            to: LifecycleState::Crashed,
        })
    ));
}

// --- Part 2: repeated operations (task brief §9) ---

#[test]
fn status_status_is_a_pure_deterministic_read() {
    // status(); status() — a plain getter, calling it any number of
    // times must never change state or produce different answers.
    let supervisor = Supervisor::default();
    for _ in 0..5 {
        assert_eq!(supervisor.state(), LifecycleState::NotStarted);
    }
}

#[test]
fn start_then_failure_then_stop_sequence() {
    // Part 2 §9 explicit example: start(); failure; stop().
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    let spawn_err = supervisor.spawn_failed("no such binary").unwrap_err();
    assert!(matches!(spawn_err, SidecarError::SpawnFailure { .. }));
    assert_eq!(supervisor.state(), LifecycleState::Failed);

    // stop() after a failed startup is a no-op success, not an error —
    // there is nothing running to stop, and FAILED is not RUNNING.
    let outcome = supervisor.request_shutdown().unwrap();
    assert_eq!(outcome, ShutdownOutcome::NotRunning(LifecycleState::Failed));
    assert_eq!(supervisor.state(), LifecycleState::Failed);
}

#[test]
fn health_check_succeeded_called_twice_is_rejected_the_second_time() {
    // RUNNING -> RUNNING is not a valid transition; a duplicate/late
    // health-check-succeeded observation must be rejected, not
    // silently treated as a no-op.
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Running);

    let result = supervisor.health_check_succeeded();
    assert!(matches!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Running,
            to: LifecycleState::Running,
        })
    ));
    assert_eq!(supervisor.state(), LifecycleState::Running);
}

#[test]
fn unexpected_exit_called_twice_second_call_rejected() {
    // A duplicate crash observation (e.g. two OS wait-signals for the
    // same exit) must not be allowed to re-fire CRASHED -> CRASHED.
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    supervisor.unexpected_exit(ExitStatus::with_code(1)).ok();
    assert_eq!(supervisor.state(), LifecycleState::Crashed);

    let result = supervisor.unexpected_exit(ExitStatus::with_code(1));
    assert!(matches!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Crashed,
            to: LifecycleState::Crashed,
        })
    ));
}

// --- Part 2: concurrency / race review (task brief §10) ---
//
// sidecar-core is entirely synchronous: every mutating Supervisor
// method takes `&mut self`, and the crate contains no threads, no
// async runtime, and no interior-mutability types (no Mutex, RefCell,
// Arc, or Rc anywhere under sidecar-core/src — verified by grep as
// part of this review, not just asserted). Rust's ownership rules
// therefore make concurrent mutation of a single Supervisor a
// *compile-time* impossibility from outside this crate without an
// external synchronization primitive the crate does not provide and
// does not need to. There is no shared mutable state, no background
// task, and nothing that can outlive the Supervisor object. Conclusion
// of this review: no code change needed, and no concurrency framework
// (tokio, async-std, parking_lot, etc.) should be added merely to have
// something to test — doing so would violate task brief §10's own
// "don't add async complexity merely for this task" instruction. A
// real Part 2B adapter that wraps `Supervisor` in `Arc<Mutex<..>>` (or
// drives it from a single dedicated task) is where any future
// concurrency-safety work belongs, not this crate.

// --- Part 2: supervisor/process abstraction review (task brief §11) ---
//
// Reviewed questions and conclusions:
// - "Is the interface minimal?" Yes — 11 methods, each corresponding
//   to exactly one contract-named event or query; no method exists
//   that isn't exercised by at least one test in this suite.
// - "Does it expose implementation details?" No — no OS process
//   handle, no file descriptor, no socket type anywhere in the public
//   API; `ExitStatus` is the only process-shaped value and it is
//   already deliberately narrow (see process.rs's doc comment).
// - "Is it accidentally coupled to Tauri?" No — confirmed by grep
//   (see the Part 2 report's static architecture audit section).
// - "Can a future native adapter implement it cleanly?" Yes, and by
//   composition rather than trait implementation: `Supervisor`
//   performs no I/O, so a Part 2B adapter *owns* a `Supervisor` and
//   calls its event methods as it observes a real process, rather
//   than needing to implement a trait `Supervisor` defines. This was
//   considered and rejected as unnecessary: extracting a
//   `trait SupervisorApi` now, with only one implementor, would be
//   speculative generality with no present caller — task brief §11's
//   own instruction is "refactor only where there is a concrete
//   architectural reason," and none exists yet.
// - "Can tests use a fake implementation?" Not needed — because
//   `Supervisor` does no I/O, tests drive it directly with literal
//   `Duration`/`ExitStatus`/`&str` values instead of mocking a trait,
//   which is simpler than the alternative, not a workaround for
//   missing one.
// - "Does it make impossible states representable?" One instance was
//   found and fixed: Part 1's `ShutdownOutcome::AlreadyStopped`
//   allowed a caller to be told "already stopped" while the sidecar
//   was actually STARTING or STOPPING — see supervisor.rs's Part 2
//   hardening note and shutdown_tests.rs's coverage of that fix. No
//   other impossible-state representation was found in this review.
