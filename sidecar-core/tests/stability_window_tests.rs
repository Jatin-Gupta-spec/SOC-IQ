//! `StabilityWindow`/`StabilityToken` tests (Phase 4E-P2 Part 2B-3).
//!
//! Covers exactly the pending-stability-check bookkeeping this module
//! is responsible for: at most one meaningful pending window at a
//! time, a token that confirms exactly once, and staleness/supersede
//! protection identical in shape to `restart_schedule_tests.rs`'s
//! coverage of `RestartSchedule`. No Tauri, no real timer, no real
//! clock — every test drives the pure API directly. The real timer
//! (`src-tauri`'s `StabilityScheduler`) has its own tests, colocated
//! with that adapter, using a fake/injected clock.

use sidecar_core::StabilityWindow;

// ---------------------------------------------------------------------
// Fresh window
// ---------------------------------------------------------------------

#[test]
fn fresh_window_has_nothing_pending() {
    let window = StabilityWindow::new();
    assert!(!window.is_pending());
}

#[test]
fn default_window_has_nothing_pending() {
    let window = StabilityWindow::default();
    assert!(!window.is_pending());
}

// ---------------------------------------------------------------------
// begin / confirm
// ---------------------------------------------------------------------

#[test]
fn begin_makes_a_window_pending() {
    let mut window = StabilityWindow::new();
    window.begin();
    assert!(window.is_pending());
}

#[test]
fn confirm_with_the_matching_token_succeeds_and_clears_pending() {
    let mut window = StabilityWindow::new();
    let token = window.begin();
    assert!(window.confirm(token));
    assert!(!window.is_pending());
}

#[test]
fn confirm_can_only_succeed_once_for_the_same_token() {
    let mut window = StabilityWindow::new();
    let token = window.begin();
    assert!(window.confirm(token));
    assert!(!window.confirm(token), "a token must not confirm twice");
}

#[test]
fn confirm_with_a_token_that_was_never_issued_is_a_no_op() {
    let mut a = StabilityWindow::new();
    let mut b = StabilityWindow::new();
    let token_from_b = b.begin();
    // `a` never issued `token_from_b` — confirming it against `a` must
    // fail, not accidentally succeed because both windows happen to be
    // pending.
    a.begin();
    assert!(!a.confirm(token_from_b));
    assert!(a.is_pending(), "a's own pending window must be untouched");
}

// ---------------------------------------------------------------------
// Supersession — a fresh RUNNING episode always wins, never refused
// ---------------------------------------------------------------------

#[test]
fn begin_unconditionally_supersedes_a_previously_pending_window() {
    let mut window = StabilityWindow::new();
    let first = window.begin();
    let second = window.begin();
    assert_ne!(first, second, "each begin() must mint a fresh, distinct token");
}

#[test]
fn a_token_from_a_superseded_window_never_confirms_the_later_one() {
    let mut window = StabilityWindow::new();
    let stale = window.begin();
    let _current = window.begin();
    assert!(
        !window.confirm(stale),
        "the stale token from the superseded window must not confirm"
    );
    assert!(
        window.is_pending(),
        "the current window must still be pending after the stale confirm no-op"
    );
}

#[test]
fn the_current_token_still_confirms_after_an_earlier_one_was_superseded() {
    let mut window = StabilityWindow::new();
    let _stale = window.begin();
    let current = window.begin();
    assert!(window.confirm(current));
    assert!(!window.is_pending());
}

// ---------------------------------------------------------------------
// Cancellation
// ---------------------------------------------------------------------

#[test]
fn cancel_clears_a_pending_window() {
    let mut window = StabilityWindow::new();
    window.begin();
    window.cancel();
    assert!(!window.is_pending());
}

#[test]
fn cancel_is_idempotent_and_never_panics() {
    let mut window = StabilityWindow::new();
    window.cancel();
    window.cancel();
    assert!(!window.is_pending());
}

#[test]
fn a_cancelled_tokens_later_confirm_is_a_no_op() {
    let mut window = StabilityWindow::new();
    let token = window.begin();
    window.cancel();
    assert!(!window.confirm(token));
}

#[test]
fn after_cancellation_a_fresh_window_can_begin() {
    let mut window = StabilityWindow::new();
    window.begin();
    window.cancel();
    assert!(!window.is_pending());
    let token = window.begin();
    assert!(window.is_pending());
    assert!(window.confirm(token));
}
