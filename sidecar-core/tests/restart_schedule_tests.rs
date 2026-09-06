//! `RestartSchedule`/`RestartToken` tests (Phase 4E-P2 Part 2B-2).
//!
//! Covers exactly the pending-restart bookkeeping this module is
//! responsible for (task brief §6/§9/§15/§16/§17/§19/§21): one pending
//! restart at a time, idempotent cancellation, and a token that fires
//! exactly once and never for a stale/superseded/cancelled schedule.
//! No Tauri, no real timer, no real thread — every test drives the
//! pure API directly, matching `restart_policy_tests.rs`'s existing
//! style. The real timer (`src-tauri`'s `RestartScheduler`) has its own
//! tests, using a fake/injected clock, colocated with that adapter.

use sidecar_core::RestartSchedule;

// ---------------------------------------------------------------------
// Fresh schedule
// ---------------------------------------------------------------------

#[test]
fn fresh_schedule_has_nothing_pending() {
    let schedule = RestartSchedule::new();
    assert!(!schedule.is_pending());
    assert_eq!(schedule.pending_attempt(), None);
}

#[test]
fn default_schedule_has_nothing_pending() {
    let schedule = RestartSchedule::default();
    assert!(!schedule.is_pending());
}

// ---------------------------------------------------------------------
// try_begin — happy path
// ---------------------------------------------------------------------

#[test]
fn try_begin_on_a_fresh_schedule_succeeds_and_marks_pending() {
    let mut schedule = RestartSchedule::new();
    let token = schedule.try_begin(1);
    assert!(token.is_some());
    assert!(schedule.is_pending());
    assert_eq!(schedule.pending_attempt(), Some(1));
}

// ---------------------------------------------------------------------
// Duplicate scheduling protection (task brief §6/§15)
// ---------------------------------------------------------------------

#[test]
fn try_begin_while_already_pending_is_rejected() {
    let mut schedule = RestartSchedule::new();
    let first = schedule.try_begin(1);
    assert!(first.is_some());

    // A second crash/schedule request arriving while the first is
    // still pending must not create a second pending restart.
    let second = schedule.try_begin(2);
    assert!(second.is_none());

    // The original pending restart (attempt 1) is untouched.
    assert!(schedule.is_pending());
    assert_eq!(schedule.pending_attempt(), Some(1));
}

#[test]
fn try_begin_after_a_successful_consume_is_allowed() {
    let mut schedule = RestartSchedule::new();
    let token = schedule.try_begin(1).expect("first begin succeeds");
    assert!(schedule.consume(token));
    assert!(!schedule.is_pending());

    // A fresh attempt is a brand-new schedule, not blocked by the one
    // that already fired.
    let next = schedule.try_begin(2);
    assert!(next.is_some());
    assert_eq!(schedule.pending_attempt(), Some(2));
}

// ---------------------------------------------------------------------
// consume — correct token (task brief §19)
// ---------------------------------------------------------------------

#[test]
fn consume_with_the_correct_token_succeeds_and_clears_pending() {
    let mut schedule = RestartSchedule::new();
    let token = schedule.try_begin(3).expect("begin succeeds");
    assert!(schedule.consume(token));
    assert!(!schedule.is_pending());
    assert_eq!(schedule.pending_attempt(), None);
}

// ---------------------------------------------------------------------
// Duplicate callback protection (task brief §16)
// ---------------------------------------------------------------------

#[test]
fn consuming_the_same_token_twice_only_succeeds_once() {
    let mut schedule = RestartSchedule::new();
    let token = schedule.try_begin(1).expect("begin succeeds");
    assert!(schedule.consume(token)); // first (real) fire
    assert!(!schedule.consume(token)); // duplicate/re-entrant callback
}

// ---------------------------------------------------------------------
// Cancellation (task brief §21)
// ---------------------------------------------------------------------

#[test]
fn cancel_clears_a_pending_restart() {
    let mut schedule = RestartSchedule::new();
    schedule.try_begin(1);
    assert!(schedule.is_pending());
    schedule.cancel();
    assert!(!schedule.is_pending());
}

#[test]
fn cancel_is_idempotent_when_nothing_is_pending() {
    let mut schedule = RestartSchedule::new();
    schedule.cancel();
    schedule.cancel();
    assert!(!schedule.is_pending());
}

#[test]
fn cancel_twice_after_a_pending_restart_does_not_panic() {
    let mut schedule = RestartSchedule::new();
    schedule.try_begin(1);
    schedule.cancel();
    schedule.cancel();
    assert!(!schedule.is_pending());
}

#[test]
fn callback_does_not_fire_after_successful_cancellation() {
    let mut schedule = RestartSchedule::new();
    let token = schedule.try_begin(1).expect("begin succeeds");
    schedule.cancel();
    // The timer "fires" (in a real caller, after the backoff delay)
    // and presents the token it was given -- it must not be honored.
    assert!(!schedule.consume(token));
}

#[test]
fn cancel_after_a_fresh_reschedule_only_cancels_the_new_one() {
    let mut schedule = RestartSchedule::new();
    let stale_token = schedule.try_begin(1).expect("begin succeeds");
    schedule.cancel();
    let fresh_token = schedule.try_begin(1).expect("fresh begin succeeds");
    schedule.cancel();
    // Neither the stale nor the fresh token can fire now.
    assert!(!schedule.consume(stale_token));
    assert!(!schedule.consume(fresh_token));
}

// ---------------------------------------------------------------------
// Stale callback protection (task brief §17)
// ---------------------------------------------------------------------

#[test]
fn a_token_from_a_superseded_schedule_never_matches_a_later_one() {
    let mut schedule = RestartSchedule::new();
    let old_token = schedule.try_begin(1).expect("begin succeeds");
    assert!(schedule.consume(old_token)); // the first restart fires and completes
    let new_token = schedule.try_begin(2).expect("fresh begin succeeds");

    // A stale callback carrying the old token must not affect the new,
    // unrelated pending restart.
    assert!(!schedule.consume(old_token));
    assert!(schedule.is_pending());
    assert_eq!(schedule.pending_attempt(), Some(2));

    // The new token still works correctly.
    assert!(schedule.consume(new_token));
    assert!(!schedule.is_pending());
}

#[test]
fn consume_with_a_token_that_was_never_issued_is_a_no_op() {
    let mut schedule = RestartSchedule::new();
    let real_token = schedule.try_begin(1).expect("begin succeeds");
    // Obtain a token that was issued and cancelled, to get a distinct
    // (never-matching) value without depending on unstable internals.
    let mut other = RestartSchedule::new();
    let unrelated_token = other.try_begin(1).expect("begin succeeds");
    other.cancel();

    assert!(!schedule.consume(unrelated_token));
    assert!(schedule.is_pending());
    assert!(schedule.consume(real_token));
}

// ---------------------------------------------------------------------
// One pending restart across duplicate crash events (task brief §15)
// ---------------------------------------------------------------------

#[test]
fn only_one_restart_is_ever_pending_across_repeated_begin_attempts() {
    let mut schedule = RestartSchedule::new();
    assert!(schedule.try_begin(1).is_some());
    for attempt in 2..10 {
        assert!(
            schedule.try_begin(attempt).is_none(),
            "attempt {attempt} must not create a second pending restart"
        );
    }
    assert_eq!(schedule.pending_attempt(), Some(1));
}
