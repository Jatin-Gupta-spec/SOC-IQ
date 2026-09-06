//! Lifecycle tests.
//!
//! Part 1 minimum coverage (task brief §11 "Lifecycle"): initial state,
//! valid transitions, invalid transitions, failure transitions.
//!
//! Part 2 adversarial coverage (task brief §4): every canonical state
//! exercised explicitly, invalid transitions in both directions where
//! meaningful, and the specific attack cases the brief names (start
//! twice, start after stopped, start while starting, stop before
//! started, stop twice, stop while stopping, transition after
//! failure/crash/timeout).

use sidecar_core::{Lifecycle, LifecycleState, SidecarError};

#[test]
fn initial_state_is_not_started() {
    let lifecycle = Lifecycle::new();
    assert_eq!(lifecycle.state(), LifecycleState::NotStarted);
}

#[test]
fn default_matches_new() {
    assert_eq!(Lifecycle::default().state(), LifecycleState::NotStarted);
}

#[test]
fn valid_happy_path_transitions_succeed_in_order() {
    let mut lifecycle = Lifecycle::new();
    assert_eq!(
        lifecycle.transition(LifecycleState::Starting).unwrap(),
        LifecycleState::Starting
    );
    assert_eq!(
        lifecycle.transition(LifecycleState::Running).unwrap(),
        LifecycleState::Running
    );
    assert_eq!(
        lifecycle.transition(LifecycleState::Stopping).unwrap(),
        LifecycleState::Stopping
    );
    assert_eq!(
        lifecycle.transition(LifecycleState::Stopped).unwrap(),
        LifecycleState::Stopped
    );
}

#[test]
fn invalid_transitions_are_rejected_and_state_is_unchanged() {
    let mut lifecycle = Lifecycle::new();
    // NOT_STARTED -> RUNNING is not in the contract's table.
    let result = lifecycle.transition(LifecycleState::Running);
    assert_eq!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::NotStarted,
            to: LifecycleState::Running,
        })
    );
    // State must be unchanged after a rejected transition.
    assert_eq!(lifecycle.state(), LifecycleState::NotStarted);
}

#[test]
fn cannot_skip_starting_to_go_straight_to_stopping() {
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    // STARTING -> STOPPING is not permitted; only RUNNING -> STOPPING is.
    assert!(lifecycle.transition(LifecycleState::Stopping).is_err());
    assert_eq!(lifecycle.state(), LifecycleState::Starting);
}

#[test]
fn failure_transition_starting_to_failed() {
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    assert_eq!(
        lifecycle.transition(LifecycleState::Failed).unwrap(),
        LifecycleState::Failed
    );
}

#[test]
fn failure_transition_starting_to_timeout() {
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    assert_eq!(
        lifecycle.transition(LifecycleState::Timeout).unwrap(),
        LifecycleState::Timeout
    );
}

#[test]
fn failure_transition_running_to_crashed() {
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Running).unwrap();
    assert_eq!(
        lifecycle.transition(LifecycleState::Crashed).unwrap(),
        LifecycleState::Crashed
    );
}

#[test]
fn failure_transition_stopping_to_failed() {
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Running).unwrap();
    lifecycle.transition(LifecycleState::Stopping).unwrap();
    assert_eq!(
        lifecycle.transition(LifecycleState::Failed).unwrap(),
        LifecycleState::Failed
    );
}

#[test]
fn terminal_states_require_explicit_reset_before_restart() {
    for terminal in [
        LifecycleState::Failed,
        LifecycleState::Timeout,
        LifecycleState::Crashed,
        LifecycleState::Stopped,
    ] {
        assert!(terminal.is_terminal());
        // Every terminal state permits -> NOT_STARTED (reset)...
        assert!(terminal.can_transition_to(LifecycleState::NotStarted));
        // ...but never a direct jump back into STARTING.
        assert!(!terminal.can_transition_to(LifecycleState::Starting));
    }
    assert!(!LifecycleState::NotStarted.is_terminal());
    assert!(!LifecycleState::Starting.is_terminal());
    assert!(!LifecycleState::Running.is_terminal());
    assert!(!LifecycleState::Stopping.is_terminal());
}

#[test]
fn repeated_full_cycle_is_deterministic() {
    let mut lifecycle = Lifecycle::new();
    for _ in 0..3 {
        lifecycle.transition(LifecycleState::Starting).unwrap();
        lifecycle.transition(LifecycleState::Running).unwrap();
        lifecycle.transition(LifecycleState::Stopping).unwrap();
        lifecycle.transition(LifecycleState::Stopped).unwrap();
        lifecycle.transition(LifecycleState::NotStarted).unwrap();
    }
    assert_eq!(lifecycle.state(), LifecycleState::NotStarted);
}

#[test]
fn start_twice_in_a_row_is_rejected() {
    // Part 2 §4 explicit case: "start twice". The second
    // NOT_STARTED -> STARTING attempt is actually STARTING -> STARTING,
    // which is not in the table (no self-transitions).
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    let result = lifecycle.transition(LifecycleState::Starting);
    assert_eq!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Starting,
            to: LifecycleState::Starting,
        })
    );
    assert_eq!(lifecycle.state(), LifecycleState::Starting);
}

#[test]
fn start_after_stopped_without_reset_is_rejected() {
    // Part 2 §4 explicit case: "start after stopped". STOPPED can only
    // go to NOT_STARTED (reset) — a direct STOPPED -> STARTING jump,
    // skipping the explicit reset, must be rejected.
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Running).unwrap();
    lifecycle.transition(LifecycleState::Stopping).unwrap();
    lifecycle.transition(LifecycleState::Stopped).unwrap();

    let result = lifecycle.transition(LifecycleState::Starting);
    assert_eq!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Stopped,
            to: LifecycleState::Starting,
        })
    );
    assert_eq!(lifecycle.state(), LifecycleState::Stopped);

    // With the explicit reset, restart is permitted.
    lifecycle.transition(LifecycleState::NotStarted).unwrap();
    assert!(lifecycle.transition(LifecycleState::Starting).is_ok());
}

#[test]
fn stop_before_started_has_no_valid_direct_transition() {
    // Part 2 §4 explicit case: "stop before started". There is no
    // NOT_STARTED -> STOPPING edge in the contract at all (only
    // RUNNING -> STOPPING); the state-machine layer rejects it. (The
    // supervisor layer's request_shutdown() turns this into a no-op
    // success instead of attempting the transition at all — see
    // supervisor_tests.rs / shutdown_tests.rs for that behavior; this
    // test pins the raw state-machine layer's independent rejection.)
    let mut lifecycle = Lifecycle::new();
    let result = lifecycle.transition(LifecycleState::Stopping);
    assert_eq!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::NotStarted,
            to: LifecycleState::Stopping,
        })
    );
}

#[test]
fn stop_twice_at_the_state_machine_layer() {
    // Part 2 §4 explicit case: "stop twice". First STOPPING->STOPPED
    // succeeds; issuing it again (STOPPED->STOPPED) is not in the table.
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Running).unwrap();
    lifecycle.transition(LifecycleState::Stopping).unwrap();
    lifecycle.transition(LifecycleState::Stopped).unwrap();

    let result = lifecycle.transition(LifecycleState::Stopped);
    assert_eq!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Stopped,
            to: LifecycleState::Stopped,
        })
    );
}

#[test]
fn stop_while_stopping_at_the_state_machine_layer() {
    // Part 2 §4 explicit case: "stop while stopping" — re-issuing
    // RUNNING -> STOPPING while already STOPPING (i.e. STOPPING ->
    // STOPPING) is not a self-transition the table permits.
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Running).unwrap();
    lifecycle.transition(LifecycleState::Stopping).unwrap();

    let result = lifecycle.transition(LifecycleState::Stopping);
    assert_eq!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Stopping,
            to: LifecycleState::Stopping,
        })
    );
}

#[test]
fn no_self_transitions_are_ever_valid() {
    // General form of the start-twice/stop-twice cases: no state may
    // transition to itself, for any state.
    for state in [
        LifecycleState::NotStarted,
        LifecycleState::Starting,
        LifecycleState::Running,
        LifecycleState::Stopping,
        LifecycleState::Stopped,
        LifecycleState::Failed,
        LifecycleState::Timeout,
        LifecycleState::Crashed,
    ] {
        assert!(
            !state.can_transition_to(state),
            "{state} must not be able to transition to itself"
        );
    }
}

#[test]
fn transition_after_failure_only_permits_reset() {
    // Part 2 §4 explicit case: "transition after failure". From
    // FAILED, every state except NOT_STARTED must be rejected.
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Failed).unwrap();

    for target in [
        LifecycleState::Starting,
        LifecycleState::Running,
        LifecycleState::Stopping,
        LifecycleState::Stopped,
        LifecycleState::Failed,
        LifecycleState::Timeout,
        LifecycleState::Crashed,
    ] {
        assert!(
            lifecycle.transition(target).is_err(),
            "FAILED -> {target} must be rejected"
        );
        assert_eq!(lifecycle.state(), LifecycleState::Failed);
    }
    assert!(lifecycle.transition(LifecycleState::NotStarted).is_ok());
}

#[test]
fn transition_after_crash_only_permits_reset() {
    // Part 2 §4 explicit case: "transition after crash".
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Running).unwrap();
    lifecycle.transition(LifecycleState::Crashed).unwrap();

    for target in [
        LifecycleState::Starting,
        LifecycleState::Running,
        LifecycleState::Stopping,
        LifecycleState::Stopped,
        LifecycleState::Failed,
        LifecycleState::Timeout,
        LifecycleState::Crashed,
    ] {
        assert!(
            lifecycle.transition(target).is_err(),
            "CRASHED -> {target} must be rejected"
        );
        assert_eq!(lifecycle.state(), LifecycleState::Crashed);
    }
    assert!(lifecycle.transition(LifecycleState::NotStarted).is_ok());
}

#[test]
fn transition_after_timeout_only_permits_reset() {
    // Part 2 §4 explicit case: "transition after timeout".
    let mut lifecycle = Lifecycle::new();
    lifecycle.transition(LifecycleState::Starting).unwrap();
    lifecycle.transition(LifecycleState::Timeout).unwrap();

    for target in [
        LifecycleState::Starting,
        LifecycleState::Running,
        LifecycleState::Stopping,
        LifecycleState::Stopped,
        LifecycleState::Failed,
        LifecycleState::Timeout,
        LifecycleState::Crashed,
    ] {
        assert!(
            lifecycle.transition(target).is_err(),
            "TIMEOUT -> {target} must be rejected"
        );
        assert_eq!(lifecycle.state(), LifecycleState::Timeout);
    }
    assert!(lifecycle.transition(LifecycleState::NotStarted).is_ok());
}

#[test]
fn every_state_pair_matches_the_documented_table_exhaustively() {
    // Adversarial completeness check: for all 8x8 = 64 (from, to)
    // pairs, can_transition_to must agree with exactly the 12 edges
    // the contract documents — no more, no fewer. This pins the whole
    // transition table against silent drift in either direction.
    let all = [
        LifecycleState::NotStarted,
        LifecycleState::Starting,
        LifecycleState::Running,
        LifecycleState::Stopping,
        LifecycleState::Stopped,
        LifecycleState::Failed,
        LifecycleState::Timeout,
        LifecycleState::Crashed,
    ];
    let allowed: std::collections::HashSet<(LifecycleState, LifecycleState)> = [
        (LifecycleState::NotStarted, LifecycleState::Starting),
        (LifecycleState::Starting, LifecycleState::Running),
        (LifecycleState::Starting, LifecycleState::Failed),
        (LifecycleState::Starting, LifecycleState::Timeout),
        (LifecycleState::Running, LifecycleState::Stopping),
        (LifecycleState::Running, LifecycleState::Crashed),
        (LifecycleState::Stopping, LifecycleState::Stopped),
        (LifecycleState::Stopping, LifecycleState::Failed),
        (LifecycleState::Stopped, LifecycleState::NotStarted),
        (LifecycleState::Failed, LifecycleState::NotStarted),
        (LifecycleState::Timeout, LifecycleState::NotStarted),
        (LifecycleState::Crashed, LifecycleState::NotStarted),
    ]
    .into_iter()
    .collect();

    let mut checked = 0;
    for &from in &all {
        for &to in &all {
            let expected = allowed.contains(&(from, to));
            assert_eq!(
                from.can_transition_to(to),
                expected,
                "{from} -> {to}: expected {expected}"
            );
            checked += 1;
        }
    }
    assert_eq!(checked, 64);
    assert_eq!(allowed.len(), 12);
}

#[test]
fn display_uses_canonical_contract_names() {
    assert_eq!(LifecycleState::NotStarted.to_string(), "NOT_STARTED");
    assert_eq!(LifecycleState::Starting.to_string(), "STARTING");
    assert_eq!(LifecycleState::Running.to_string(), "RUNNING");
    assert_eq!(LifecycleState::Stopping.to_string(), "STOPPING");
    assert_eq!(LifecycleState::Stopped.to_string(), "STOPPED");
    assert_eq!(LifecycleState::Failed.to_string(), "FAILED");
    assert_eq!(LifecycleState::Timeout.to_string(), "TIMEOUT");
    assert_eq!(LifecycleState::Crashed.to_string(), "CRASHED");
}
