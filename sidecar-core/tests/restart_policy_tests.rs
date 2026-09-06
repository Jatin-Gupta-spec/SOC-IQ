//! `RestartPolicy`/`RestartTracker` tests (Phase 4E-P2 Part 2B-1).
//!
//! Covers exactly the task brief's required minimum (§15/§16/§17):
//! policy defaults/backoff, tracker accounting, exhaustion, reset, and
//! dedicated off-by-one boundary tests at `max_attempts - 1`,
//! `max_attempts`, `max_attempts + 1`. No Tauri, no real subprocess, no
//! real timer, no real clock — every test drives the pure API directly,
//! matching the rest of this crate's existing test style
//! (`supervisor_tests.rs`, `shutdown_tests.rs`).

use sidecar_core::{RestartDecision, RestartPolicy, RestartTracker};
use std::time::Duration;

// ---------------------------------------------------------------------
// RestartPolicy — defaults
// ---------------------------------------------------------------------

#[test]
fn default_policy_matches_architecture_7_3_through_7_5() {
    let policy = RestartPolicy::default();
    assert_eq!(policy.max_attempts, 5);
    assert_eq!(policy.base_delay, Duration::from_secs(1));
    assert_eq!(policy.max_delay, Duration::from_secs(30));
    assert_eq!(policy.reset_after_stable, Duration::from_secs(60));
}

#[test]
fn explicit_policy_construction() {
    let policy = RestartPolicy::new(
        3,
        Duration::from_millis(500),
        Duration::from_secs(10),
        Duration::from_secs(30),
    );
    assert_eq!(policy.max_attempts, 3);
    assert_eq!(policy.base_delay, Duration::from_millis(500));
    assert_eq!(policy.max_delay, Duration::from_secs(10));
    assert_eq!(policy.reset_after_stable, Duration::from_secs(30));
}

// ---------------------------------------------------------------------
// RestartPolicy — backoff calculation (§7.4)
// ---------------------------------------------------------------------

#[test]
fn backoff_sequence_matches_architecture_7_4_exactly() {
    // "1s, 2s, 4s, 8s, 16s, 30s, 30s, ..." for attempts 1..7, per §7.4's
    // own documented sequence, using the default policy.
    let policy = RestartPolicy::default();
    let expected = [
        (1, Duration::from_secs(1)),
        (2, Duration::from_secs(2)),
        (3, Duration::from_secs(4)),
        (4, Duration::from_secs(8)),
        (5, Duration::from_secs(16)),
        (6, Duration::from_secs(30)), // 32s uncapped -> capped to 30s
        (7, Duration::from_secs(30)), // 64s uncapped -> capped to 30s
    ];
    for (attempt, want) in expected {
        assert_eq!(
            policy.backoff_for_attempt(attempt),
            want,
            "attempt {attempt}"
        );
    }
}

#[test]
fn backoff_never_exceeds_max_delay_far_past_the_cap() {
    let policy = RestartPolicy::default();
    // Attempt 20 would be 2^19 seconds uncapped -- must still clamp to
    // max_delay, not overflow or panic.
    assert_eq!(policy.backoff_for_attempt(20), Duration::from_secs(30));
    assert_eq!(policy.backoff_for_attempt(1000), Duration::from_secs(30));
}

#[test]
fn backoff_for_attempt_zero_behaves_like_attempt_one() {
    let policy = RestartPolicy::default();
    assert_eq!(policy.backoff_for_attempt(0), policy.backoff_for_attempt(1));
}

#[test]
fn backoff_respects_a_custom_base_and_cap() {
    let policy = RestartPolicy::new(
        5,
        Duration::from_millis(100),
        Duration::from_millis(350),
        Duration::from_secs(60),
    );
    assert_eq!(policy.backoff_for_attempt(1), Duration::from_millis(100));
    assert_eq!(policy.backoff_for_attempt(2), Duration::from_millis(200));
    assert_eq!(policy.backoff_for_attempt(3), Duration::from_millis(350)); // 400ms capped
    assert_eq!(policy.backoff_for_attempt(4), Duration::from_millis(350));
}

// ---------------------------------------------------------------------
// RestartTracker — initial state / basic accounting (§16)
// ---------------------------------------------------------------------

#[test]
fn fresh_tracker_has_zero_attempts() {
    let tracker = RestartTracker::new();
    assert_eq!(tracker.attempts(), 0);
}

#[test]
fn default_tracker_has_zero_attempts() {
    let tracker = RestartTracker::default();
    assert_eq!(tracker.attempts(), 0);
}

#[test]
fn record_one_attempt_increments_by_one() {
    let mut tracker = RestartTracker::new();
    let count = tracker.record_attempt();
    assert_eq!(count, 1);
    assert_eq!(tracker.attempts(), 1);
}

#[test]
fn record_multiple_attempts_accumulates() {
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    let count = tracker.record_attempt();
    assert_eq!(count, 3);
    assert_eq!(tracker.attempts(), 3);
}

// ---------------------------------------------------------------------
// RestartTracker::decide — allowed attempt (§15)
// ---------------------------------------------------------------------

#[test]
fn decide_allows_first_attempt_from_fresh_tracker() {
    let policy = RestartPolicy::default();
    let tracker = RestartTracker::new();
    let decision = tracker.decide(&policy);
    assert_eq!(
        decision,
        RestartDecision::Retry {
            attempt: 1,
            after: Duration::from_secs(1),
        }
    );
    assert!(decision.is_retry());
    assert!(!decision.is_exhausted());
}

#[test]
fn decide_reports_correct_attempt_number_and_backoff_mid_sequence() {
    let policy = RestartPolicy::default();
    let mut tracker = RestartTracker::new();
    tracker.record_attempt(); // 1
    tracker.record_attempt(); // 2
    let decision = tracker.decide(&policy);
    assert_eq!(
        decision,
        RestartDecision::Retry {
            attempt: 3,
            after: Duration::from_secs(4),
        }
    );
}

#[test]
fn decide_does_not_mutate_the_tracker() {
    let policy = RestartPolicy::default();
    let tracker = RestartTracker::new();
    tracker.decide(&policy);
    tracker.decide(&policy);
    // decide() is &self, not &mut self -- calling it repeatedly must
    // not change the recorded attempt count.
    assert_eq!(tracker.attempts(), 0);
}

// ---------------------------------------------------------------------
// RestartTracker::decide — exhaustion (§15)
// ---------------------------------------------------------------------

#[test]
fn decide_reports_exhausted_once_max_attempts_reached() {
    let policy = RestartPolicy::new(
        2,
        Duration::from_secs(1),
        Duration::from_secs(30),
        Duration::from_secs(60),
    );
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    let decision = tracker.decide(&policy);
    assert_eq!(decision, RestartDecision::Exhausted { attempts: 2 });
    assert!(decision.is_exhausted());
    assert!(!decision.is_retry());
}

// ---------------------------------------------------------------------
// RestartTracker — reset behavior (§15/§16, task brief §10)
// ---------------------------------------------------------------------

#[test]
fn reset_returns_attempts_to_zero() {
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    tracker.reset();
    assert_eq!(tracker.attempts(), 0);
}

#[test]
fn reset_is_a_no_op_on_an_already_fresh_tracker() {
    let mut tracker = RestartTracker::new();
    tracker.reset();
    assert_eq!(tracker.attempts(), 0);
}

#[test]
fn record_after_reset_starts_from_one_again() {
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    tracker.reset();
    let count = tracker.record_attempt();
    assert_eq!(count, 1);
    assert_eq!(tracker.attempts(), 1);
}

#[test]
fn decide_allows_a_fresh_full_budget_after_reset() {
    let policy = RestartPolicy::new(
        2,
        Duration::from_secs(1),
        Duration::from_secs(30),
        Duration::from_secs(60),
    );
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    assert_eq!(
        tracker.decide(&policy),
        RestartDecision::Exhausted { attempts: 2 }
    );
    tracker.reset();
    assert_eq!(
        tracker.decide(&policy),
        RestartDecision::Retry {
            attempt: 1,
            after: Duration::from_secs(1),
        }
    );
}

// ---------------------------------------------------------------------
// Dedicated off-by-one boundary tests (§17, mandatory)
//
// Explicitly prove maximum - 1, maximum, and maximum + 1 for a policy
// with max_attempts = N (using both the architecture's own default,
// N = 5, and a second smaller N to show the boundary is general, not
// coincidental to 5).
// ---------------------------------------------------------------------

#[test]
fn boundary_default_max_attempts_minus_one_still_allows_retry() {
    // max_attempts = 5 (default). attempts = 4 (N - 1): the 5th
    // (final) attempt must still be allowed.
    let policy = RestartPolicy::default();
    let mut tracker = RestartTracker::new();
    for _ in 0..4 {
        tracker.record_attempt();
    }
    assert_eq!(tracker.attempts(), 4);
    let decision = tracker.decide(&policy);
    assert_eq!(
        decision,
        RestartDecision::Retry {
            attempt: 5,
            after: Duration::from_secs(16),
        }
    );
}

#[test]
fn boundary_default_max_attempts_exactly_is_exhausted() {
    // max_attempts = 5 (default). attempts = 5 (N): no further
    // automatic attempt is allowed -- this is the exact point
    // exhaustion must first appear, never earlier.
    let policy = RestartPolicy::default();
    let mut tracker = RestartTracker::new();
    for _ in 0..5 {
        tracker.record_attempt();
    }
    assert_eq!(tracker.attempts(), 5);
    let decision = tracker.decide(&policy);
    assert_eq!(decision, RestartDecision::Exhausted { attempts: 5 });
}

#[test]
fn boundary_default_max_attempts_plus_one_remains_exhausted() {
    // max_attempts = 5 (default). attempts = 6 (N + 1, beyond the
    // ceiling): must remain Exhausted, never re-open, never panic or
    // underflow.
    let policy = RestartPolicy::default();
    let mut tracker = RestartTracker::new();
    for _ in 0..6 {
        tracker.record_attempt();
    }
    assert_eq!(tracker.attempts(), 6);
    let decision = tracker.decide(&policy);
    assert_eq!(decision, RestartDecision::Exhausted { attempts: 6 });
}

#[test]
fn boundary_custom_max_attempts_minus_one_still_allows_retry() {
    // Same three-point boundary with a smaller, non-default N = 3, to
    // show the logic is general rather than hard-coded to 5.
    let policy = RestartPolicy::new(
        3,
        Duration::from_secs(1),
        Duration::from_secs(30),
        Duration::from_secs(60),
    );
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    assert_eq!(tracker.attempts(), 2); // N - 1
    assert!(tracker.decide(&policy).is_retry());
}

#[test]
fn boundary_custom_max_attempts_exactly_is_exhausted() {
    let policy = RestartPolicy::new(
        3,
        Duration::from_secs(1),
        Duration::from_secs(30),
        Duration::from_secs(60),
    );
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    tracker.record_attempt();
    assert_eq!(tracker.attempts(), 3); // N
    assert!(tracker.decide(&policy).is_exhausted());
}

#[test]
fn boundary_custom_max_attempts_plus_one_remains_exhausted() {
    let policy = RestartPolicy::new(
        3,
        Duration::from_secs(1),
        Duration::from_secs(30),
        Duration::from_secs(60),
    );
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    tracker.record_attempt();
    tracker.record_attempt();
    tracker.record_attempt();
    assert_eq!(tracker.attempts(), 4); // N + 1
    assert!(tracker.decide(&policy).is_exhausted());
}

// ---------------------------------------------------------------------
// No automatic restart execution (§12 of the task brief / §7.6)
// ---------------------------------------------------------------------

#[test]
fn decide_never_mutates_state_even_when_repeatedly_exhausted() {
    // A pure decide() call, called many times in a row on an exhausted
    // tracker, must keep returning the identical decision -- there is
    // no hidden internal counter advancing on its own, and nothing
    // here performs or schedules a restart.
    let policy = RestartPolicy::new(
        1,
        Duration::from_secs(1),
        Duration::from_secs(30),
        Duration::from_secs(60),
    );
    let mut tracker = RestartTracker::new();
    tracker.record_attempt();
    for _ in 0..5 {
        assert_eq!(
            tracker.decide(&policy),
            RestartDecision::Exhausted { attempts: 1 }
        );
    }
}
