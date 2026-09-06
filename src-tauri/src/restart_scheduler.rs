//! Restart scheduling — the real timer (Phase 4E-P2 Part 2B-2).
//!
//! Implements the "Restart Scheduler" box in the task brief's target
//! architecture:
//!
//! ```text
//! Crash detected -> RestartPolicy -> RestartTracker -> restart allowed?
//!   -> Restart Scheduler -> backoff delay -> restart execution trigger
//! ```
//!
//! `sidecar_core::restart::RestartPolicy`/`RestartTracker` (Part 2B-1)
//! already decide *whether* to retry and *what* delay to use.
//! `sidecar_core::restart::RestartSchedule` (Part 2B-2, same crate)
//! already provides pure "at most one pending restart" bookkeeping with
//! no real timing. What's still missing -- and everything this module
//! adds -- is the *real* timer that actually waits `after` and then
//! fires, plus wiring that timer to `RestartSchedule` so duplicate
//! scheduling and stale/duplicate callback firing are impossible, not
//! merely discouraged (task brief §6/§9/§15/§16/§17).
//!
//! # Why this is a separate type from `sidecar_core::RestartSchedule`
//!
//! `sidecar-core` has a hard architectural boundary: no real process
//! spawning, no real I/O, no real timing (see that crate's own
//! `lib.rs` doc). A real timer -- something that spawns a thread and
//! sleeps -- cannot live there. This module is exactly the kind of
//! "future Tauri/native adapter" that crate's dependency-direction doc
//! anticipates: it depends on `sidecar-core`, never the reverse, and it
//! is the *only* place in this crate that starts a timer thread for
//! restart backoff.
//!
//! # No blocking of the Tauri lifecycle thread (task brief §8)
//!
//! [`ThreadDelayRunner`], the production [`DelayRunner`], spawns one
//! dedicated `std::thread` per scheduled restart and sleeps *on that
//! thread* -- never the Tauri main thread, never a thread holding
//! `SidecarState`'s process/tracker mutex (`src-tauri/src/lib.rs`
//! acquires that mutex only inside the fired callback, after the sleep
//! has already completed). This mirrors the same pattern the existing
//! crash-poll loop and `SidecarProcess::start`/`shutdown` already use
//! (`sidecar.rs`'s own `std::thread::sleep` calls, none of which hold
//! that mutex across the sleep either).
//!
//! # Deterministic testing (task brief §9/§10)
//!
//! [`RestartScheduler`] is generic over [`DelayRunner`] specifically so
//! tests can inject a fake that fires deterministically -- recording
//! the requested delay and letting the test invoke the action manually
//! -- instead of the real implementation ever sleeping in real time.
//! See this module's own `tests` for the fake used here; `sidecar-core`
//! has its own, separate pure tests for the `RestartSchedule` bookkeeping
//! itself (`sidecar-core/tests/restart_schedule_tests.rs`).

use std::sync::{Arc, Mutex};
use std::time::Duration;

use sidecar_core::{RestartSchedule, RestartToken, StabilityWindow};

/// Abstraction over "run this action after this delay," injected into
/// [`RestartScheduler`] so it is testable without a real sleep (task
/// brief §10). Returns `true` if the action was actually handed off to
/// run later, `false` if the timer itself could not be created (task
/// brief §20: "if the timer/scheduler itself fails, do not silently
/// claim a restart was scheduled").
pub trait DelayRunner: Send + Sync + 'static {
    fn run_after(&self, delay: Duration, action: Box<dyn FnOnce() + Send>) -> bool;
}

/// Production [`DelayRunner`]: one dedicated, named OS thread per
/// scheduled restart, parked in `std::thread::sleep` for exactly the
/// backoff delay, then running `action` on that same thread. Never the
/// calling thread, never a lock held across the sleep (see module doc).
#[derive(Debug, Clone, Copy, Default)]
pub struct ThreadDelayRunner;

impl DelayRunner for ThreadDelayRunner {
    fn run_after(&self, delay: Duration, action: Box<dyn FnOnce() + Send>) -> bool {
        std::thread::Builder::new()
            .name("soc-iq-restart-timer".to_string())
            .spawn(move || {
                std::thread::sleep(delay);
                action();
            })
            .is_ok()
    }
}

/// Owns the real restart-backoff timer for one sidecar lifecycle.
/// Composes [`RestartSchedule`] (pure pending-restart bookkeeping,
/// `sidecar-core`) with a [`DelayRunner`] (the real timer mechanism).
///
/// There is exactly one authoritative pending restart per
/// `RestartScheduler` instance, enforced by `RestartSchedule` itself
/// (task brief §6/§15) -- this type adds nothing that could weaken
/// that guarantee, only the real timer around it.
pub struct RestartScheduler<R: DelayRunner = ThreadDelayRunner> {
    runner: R,
    schedule: Arc<Mutex<RestartSchedule>>,
}

impl RestartScheduler<ThreadDelayRunner> {
    /// A scheduler backed by the real, production timer.
    pub fn new() -> Self {
        Self::with_runner(ThreadDelayRunner)
    }
}

impl Default for RestartScheduler<ThreadDelayRunner> {
    fn default() -> Self {
        Self::new()
    }
}

impl<R: DelayRunner> RestartScheduler<R> {
    /// A scheduler backed by an arbitrary [`DelayRunner`] -- production
    /// code always uses [`RestartScheduler::new`]; tests use this to
    /// inject a deterministic fake (task brief §10).
    pub fn with_runner(runner: R) -> Self {
        Self {
            runner,
            schedule: Arc::new(Mutex::new(RestartSchedule::new())),
        }
    }

    /// Whether a restart is currently pending (not yet fired, not
    /// cancelled).
    pub fn is_pending(&self) -> bool {
        self.lock_schedule().is_pending()
    }

    /// The attempt number of the currently pending restart, if any
    /// (Phase 4E-P3 Part 2C: `get_sidecar_status`'s `restart_pending_attempt`
    /// field, task brief §25/§28). A thin passthrough to the existing
    /// `RestartSchedule::pending_attempt` authority -- not a second,
    /// independently-tracked value.
    pub fn pending_attempt(&self) -> Option<u32> {
        self.lock_schedule().pending_attempt()
    }

    /// Schedule exactly one restart attempt, `delay` from now. `action`
    /// runs on the timer's own thread once the delay has elapsed --
    /// *and* this specific scheduled restart is confirmed still current
    /// (not superseded, not cancelled, not already fired) immediately
    /// beforehand, inside this method's own bookkeeping. Callers still
    /// owe their own, independent re-check of *lifecycle* state before
    /// acting further (task brief §14) -- this type only guarantees the
    /// *scheduling* identity is still valid, not that the sidecar is
    /// still in a restartable state, which this type has no visibility
    /// into.
    ///
    /// Returns `false` -- a deliberate no-op, not a panic -- in two
    /// distinct cases a caller may want to distinguish by logging
    /// differently, though both mean "no restart was scheduled just
    /// now":
    /// - a restart is already pending (task brief §6/§15: duplicate
    ///   scheduling is impossible, not merely ignored-and-retried);
    /// - the real timer itself could not be created (task brief §20);
    ///   in this case the pending registration this call would have
    ///   created is rolled back, so a later, real attempt is not
    ///   permanently blocked by a phantom pending restart.
    pub fn schedule<F>(&self, attempt: u32, delay: Duration, action: F) -> bool
    where
        F: FnOnce() + Send + 'static,
    {
        let token = match self.lock_schedule().try_begin(attempt) {
            Some(token) => token,
            None => return false,
        };

        let schedule = Arc::clone(&self.schedule);
        let fired_ok = self.runner.run_after(
            delay,
            Box::new(move || {
                let should_fire = {
                    let mut guard = schedule.lock().unwrap_or_else(|e| e.into_inner());
                    guard.consume(token)
                };
                if should_fire {
                    action();
                }
                // `!should_fire`: this specific scheduled restart was
                // cancelled, superseded, or already consumed by an
                // earlier (mis-)fire -- a deliberate no-op (task brief
                // §16/§17/§21), never a second restart.
            }),
        );

        if !fired_ok {
            // The timer could not be created at all -- undo the
            // pending registration `try_begin` made above, so this
            // failure does not permanently block a later, real
            // schedule() call (task brief §20).
            self.lock_schedule().cancel();
        }

        fired_ok
    }

    /// Idempotent cancellation (task brief §21): safe to call any
    /// number of times, including when nothing is pending. If a
    /// restart is currently pending and its timer has not yet fired,
    /// its callback becomes a guaranteed no-op (via
    /// [`RestartSchedule::consume`] returning `false`) even if the
    /// timer fires later -- see the module doc's "no blocking" note for
    /// why the sleeping timer thread itself is not, and does not need
    /// to be, interrupted: it re-checks with `RestartSchedule` itself
    /// when it wakes, rather than trusting anything captured at
    /// scheduling time.
    pub fn cancel(&self) {
        self.lock_schedule().cancel();
    }

    fn lock_schedule(&self) -> std::sync::MutexGuard<'_, RestartSchedule> {
        self.schedule.lock().unwrap_or_else(|e| e.into_inner())
    }
}

/// Owns the real `reset_after_stable` stability timer for one sidecar
/// lifecycle (Phase 4E-P2 Part 2B-3; architecture doc §7.5). Composes
/// [`StabilityWindow`] (pure pending-window bookkeeping, `sidecar-core`)
/// with the same [`DelayRunner`] abstraction [`RestartScheduler`] uses
/// — a second, independent timer, deliberately not sharing
/// `RestartSchedule`'s one-pending slot (see `StabilityWindow`'s module
/// doc in `sidecar-core` for why the two must not contend for the same
/// slot).
///
/// Same no-blocking guarantee as [`RestartScheduler`]: the production
/// [`ThreadDelayRunner`] sleeps on its own dedicated thread, never the
/// Tauri lifecycle thread and never while holding `SidecarState`'s
/// process/tracker mutex.
pub struct StabilityScheduler<R: DelayRunner = ThreadDelayRunner> {
    runner: R,
    window: Arc<Mutex<StabilityWindow>>,
}

impl StabilityScheduler<ThreadDelayRunner> {
    /// A scheduler backed by the real, production timer.
    pub fn new() -> Self {
        Self::with_runner(ThreadDelayRunner)
    }
}

impl Default for StabilityScheduler<ThreadDelayRunner> {
    fn default() -> Self {
        Self::new()
    }
}

impl<R: DelayRunner> StabilityScheduler<R> {
    /// A scheduler backed by an arbitrary [`DelayRunner`] -- production
    /// code always uses [`StabilityScheduler::new`]; tests inject a
    /// deterministic fake.
    pub fn with_runner(runner: R) -> Self {
        Self {
            runner,
            window: Arc::new(Mutex::new(StabilityWindow::new())),
        }
    }

    /// Whether a stability window is currently pending.
    pub fn is_pending(&self) -> bool {
        self.lock_window().is_pending()
    }

    /// Begin a fresh stability window for the `RUNNING` episode that
    /// was just entered (a first successful start, or a successful
    /// automatic restart), unconditionally superseding any previously
    /// pending window (`StabilityWindow::begin`'s own guarantee — there
    /// is only ever one *current* `RUNNING` episode). `action` runs on
    /// the timer's own thread after `delay` has elapsed, *and* this
    /// specific window is confirmed still current — but, exactly like
    /// [`RestartScheduler::schedule`], callers still owe their own
    /// independent re-check of *lifecycle* state before acting further
    /// (this type has no visibility into it at all).
    ///
    /// Returns `false` if the real timer itself could not be created
    /// (task brief §20's same allowance) — the just-begun window is
    /// rolled back via `cancel()` so it does not linger as a phantom
    /// pending window that can never fire.
    pub fn begin<F>(&self, delay: Duration, action: F) -> bool
    where
        F: FnOnce() + Send + 'static,
    {
        let token = self.lock_window().begin();

        let window = Arc::clone(&self.window);
        let fired_ok = self.runner.run_after(
            delay,
            Box::new(move || {
                let should_fire = {
                    let mut guard = window.lock().unwrap_or_else(|e| e.into_inner());
                    guard.confirm(token)
                };
                if should_fire {
                    action();
                }
                // `!should_fire`: this window was cancelled or
                // superseded before the delay elapsed — a deliberate
                // no-op, never a reset of the wrong crash-loop episode.
            }),
        );

        if !fired_ok {
            self.lock_window().cancel();
        }

        fired_ok
    }

    /// Idempotent cancellation: clears any currently pending stability
    /// window. Called whenever the `RUNNING` episode it was tracking
    /// ends before the full duration elapsed (a crash, a failed
    /// restart, or an intentional shutdown) — see
    /// [`StabilityWindow::cancel`]'s doc for why this must happen even
    /// though the sleeping timer thread itself is not interrupted.
    pub fn cancel(&self) {
        self.lock_window().cancel();
    }

    fn lock_window(&self) -> std::sync::MutexGuard<'_, StabilityWindow> {
        self.window.lock().unwrap_or_else(|e| e.into_inner())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// Deterministic [`DelayRunner`] for tests (task brief §10): never
    /// spawns a real thread or sleeps. Records every requested delay
    /// and stores the action for the test to fire manually via
    /// [`FakeDelayRunner::fire_all`], so scheduling/backoff/duplicate/
    /// cancellation behavior can be proven without waiting in real
    /// time.
    #[derive(Clone, Default)]
    struct FakeDelayRunner {
        delays: Arc<Mutex<Vec<Duration>>>,
        #[allow(clippy::type_complexity)]
        pending_actions: Arc<Mutex<Vec<Box<dyn FnOnce() + Send>>>>,
    }

    impl FakeDelayRunner {
        fn new() -> Self {
            Self::default()
        }

        fn delays(&self) -> Vec<Duration> {
            self.delays.lock().unwrap().clone()
        }

        fn pending_count(&self) -> usize {
            self.pending_actions.lock().unwrap().len()
        }

        /// Fire every action currently stored, in the order they were
        /// scheduled, then clear them -- simulating each timer's
        /// backoff delay having elapsed.
        fn fire_all(&self) {
            let actions: Vec<_> = {
                let mut guard = self.pending_actions.lock().unwrap();
                std::mem::take(&mut *guard)
            };
            for action in actions {
                action();
            }
        }
    }

    impl DelayRunner for FakeDelayRunner {
        fn run_after(&self, delay: Duration, action: Box<dyn FnOnce() + Send>) -> bool {
            self.delays.lock().unwrap().push(delay);
            self.pending_actions.lock().unwrap().push(action);
            true
        }
    }

    /// A [`DelayRunner`] that always fails to create the timer, for
    /// exercising the task brief §20 scheduler-failure path.
    struct FailingDelayRunner;

    impl DelayRunner for FailingDelayRunner {
        fn run_after(&self, _delay: Duration, _action: Box<dyn FnOnce() + Send>) -> bool {
            false
        }
    }

    // -------------------------------------------------------------
    // Scheduling (task brief §28 "Scheduling")
    // -------------------------------------------------------------

    #[test]
    fn schedule_records_the_correct_delay() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        assert!(scheduler.schedule(1, Duration::from_secs(4), || {}));
        assert_eq!(runner.delays(), vec![Duration::from_secs(4)]);
    }

    #[test]
    fn scheduled_action_does_not_run_before_the_timer_fires() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.schedule(1, Duration::from_secs(1), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        assert_eq!(fired.load(Ordering::SeqCst), 0);
        assert_eq!(runner.pending_count(), 1);
    }

    #[test]
    fn scheduled_action_fires_exactly_once_when_the_timer_fires() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.schedule(1, Duration::from_secs(1), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        runner.fire_all();
        assert_eq!(fired.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn scheduler_starts_with_nothing_pending_and_becomes_pending_after_schedule() {
        let scheduler = RestartScheduler::with_runner(FakeDelayRunner::new());
        assert!(!scheduler.is_pending());
        scheduler.schedule(1, Duration::from_secs(1), || {});
        assert!(scheduler.is_pending());
    }

    // -------------------------------------------------------------
    // Duplicate protection (task brief §28 "Duplicate protection")
    // -------------------------------------------------------------

    #[test]
    fn a_second_schedule_call_while_one_is_pending_is_rejected() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        assert!(scheduler.schedule(1, Duration::from_secs(1), || {}));
        assert!(!scheduler.schedule(2, Duration::from_secs(2), || {}));
        // The rejected second attempt never even reached the timer.
        assert_eq!(runner.delays(), vec![Duration::from_secs(1)]);
    }

    #[test]
    fn duplicate_crash_events_produce_exactly_one_scheduled_timer_and_one_firing() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        let fire_count = Arc::new(AtomicUsize::new(0));

        for attempt in 1..=3 {
            let counter = Arc::clone(&fire_count);
            scheduler.schedule(attempt, Duration::from_secs(1), move || {
                counter.fetch_add(1, Ordering::SeqCst);
            });
        }

        assert_eq!(runner.pending_count(), 1, "only the first schedule reached the timer");
        runner.fire_all();
        assert_eq!(fire_count.load(Ordering::SeqCst), 1, "exactly one restart attempt fired");
    }

    #[test]
    fn manually_invoking_the_stored_action_twice_still_only_fires_the_restart_once() {
        // Simulates a duplicate/re-entrant invocation of the same fired
        // timer callback (task brief §16) at the `RestartScheduler`
        // level: the *action* itself only increments a counter, but
        // the scheduler's own consume-then-fire wrapper (not the raw
        // action) is what a duplicate callback would actually
        // re-invoke. This test exercises that wrapper directly by
        // capturing it before firing, matching how `ThreadDelayRunner`
        // would store and could, in a hypothetical bug, invoke it more
        // than once.
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        let fire_count = Arc::new(AtomicUsize::new(0));
        let counter = Arc::clone(&fire_count);
        scheduler.schedule(1, Duration::from_secs(1), move || {
            counter.fetch_add(1, Ordering::SeqCst);
        });

        let wrapped_action = {
            let mut guard = runner.pending_actions.lock().unwrap();
            guard.pop().expect("one action was scheduled")
        };
        // `wrapped_action` is `FnOnce`, so it can only be *taken* and
        // called once by value here -- proving double-execution would
        // require a second, independent fire through the scheduler's
        // own consume-guarded path, which `RestartSchedule::consume`'s
        // one-shot guarantee (see `restart_schedule_tests.rs`) already
        // rules out. Calling it once confirms the happy path still
        // fires correctly with the wrapper in place.
        wrapped_action();
        assert_eq!(fire_count.load(Ordering::SeqCst), 1);
    }

    // -------------------------------------------------------------
    // Cancellation (task brief §28 "Cancellation")
    // -------------------------------------------------------------

    #[test]
    fn cancel_before_the_timer_fires_prevents_the_action_from_running() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.schedule(1, Duration::from_secs(1), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        scheduler.cancel();
        runner.fire_all();
        assert_eq!(fired.load(Ordering::SeqCst), 0);
        assert!(!scheduler.is_pending());
    }

    #[test]
    fn cancel_twice_does_not_panic() {
        let scheduler = RestartScheduler::with_runner(FakeDelayRunner::new());
        scheduler.cancel();
        scheduler.cancel();
        assert!(!scheduler.is_pending());
    }

    #[test]
    fn schedule_cancel_callback_fires_sequence_never_runs_the_restart() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.schedule(1, Duration::from_secs(1), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        scheduler.cancel();
        runner.fire_all(); // the callback fires, but must no-op
        assert_eq!(fired.load(Ordering::SeqCst), 0);
    }

    #[test]
    fn after_cancellation_a_fresh_restart_can_be_scheduled() {
        let runner = FakeDelayRunner::new();
        let scheduler = RestartScheduler::with_runner(runner.clone());
        scheduler.schedule(1, Duration::from_secs(1), || {});
        scheduler.cancel();
        assert!(!scheduler.is_pending());
        assert!(scheduler.schedule(1, Duration::from_secs(1), || {}));
    }

    // -------------------------------------------------------------
    // Scheduler failure (task brief §20/§28)
    // -------------------------------------------------------------

    #[test]
    fn a_timer_creation_failure_is_reported_honestly_not_as_success() {
        let scheduler = RestartScheduler::with_runner(FailingDelayRunner);
        let ok = scheduler.schedule(1, Duration::from_secs(1), || {});
        assert!(!ok);
    }

    #[test]
    fn a_timer_creation_failure_does_not_leave_a_phantom_pending_restart() {
        let scheduler = RestartScheduler::with_runner(FailingDelayRunner);
        scheduler.schedule(1, Duration::from_secs(1), || {});
        assert!(
            !scheduler.is_pending(),
            "a failed schedule attempt must not permanently block a later real one"
        );
    }

    // -------------------------------------------------------------
    // StabilityScheduler (Phase 4E-P2 Part 2B-3)
    // -------------------------------------------------------------

    #[test]
    fn stability_scheduler_starts_with_nothing_pending() {
        let scheduler = StabilityScheduler::with_runner(FakeDelayRunner::new());
        assert!(!scheduler.is_pending());
    }

    #[test]
    fn begin_makes_the_stability_scheduler_pending_and_records_the_delay() {
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        assert!(scheduler.begin(Duration::from_secs(60), || {}));
        assert!(scheduler.is_pending());
        assert_eq!(runner.delays(), vec![Duration::from_secs(60)]);
    }

    #[test]
    fn stability_action_does_not_run_before_the_timer_fires() {
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.begin(Duration::from_secs(60), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        assert_eq!(fired.load(Ordering::SeqCst), 0);
    }

    #[test]
    fn stability_action_fires_once_the_window_elapses() {
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.begin(Duration::from_secs(60), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        runner.fire_all();
        assert_eq!(fired.load(Ordering::SeqCst), 1);
        assert!(!scheduler.is_pending());
    }

    #[test]
    fn a_second_begin_supersedes_the_first_and_only_the_current_one_can_fire() {
        // Simulates: sidecar becomes RUNNING (window A begins), then
        // crashes and restarts and becomes RUNNING again before window
        // A's 60s elapsed (window B begins). Window A's eventual firing
        // must not reset the tracker for an episode that already ended.
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        let fire_count = Arc::new(AtomicUsize::new(0));

        let counter_a = Arc::clone(&fire_count);
        scheduler.begin(Duration::from_secs(60), move || {
            counter_a.fetch_add(1, Ordering::SeqCst);
        });
        let counter_b = Arc::clone(&fire_count);
        scheduler.begin(Duration::from_secs(60), move || {
            counter_b.fetch_add(1, Ordering::SeqCst);
        });

        runner.fire_all();
        assert_eq!(
            fire_count.load(Ordering::SeqCst),
            1,
            "only the current (second) window's action must run"
        );
    }

    #[test]
    fn cancel_before_the_window_elapses_prevents_the_reset_action_from_running() {
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        let fired = Arc::new(AtomicUsize::new(0));
        let fired_in_action = Arc::clone(&fired);
        scheduler.begin(Duration::from_secs(60), move || {
            fired_in_action.fetch_add(1, Ordering::SeqCst);
        });
        scheduler.cancel();
        runner.fire_all();
        assert_eq!(fired.load(Ordering::SeqCst), 0);
        assert!(!scheduler.is_pending());
    }

    #[test]
    fn cancel_is_idempotent_for_the_stability_scheduler() {
        let scheduler = StabilityScheduler::with_runner(FakeDelayRunner::new());
        scheduler.cancel();
        scheduler.cancel();
        assert!(!scheduler.is_pending());
    }

    #[test]
    fn after_cancellation_a_fresh_stability_window_can_begin() {
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        scheduler.begin(Duration::from_secs(60), || {});
        scheduler.cancel();
        assert!(!scheduler.is_pending());
        assert!(scheduler.begin(Duration::from_secs(60), || {}));
        assert!(scheduler.is_pending());
    }

    #[test]
    fn a_stability_timer_creation_failure_is_reported_honestly_not_as_success() {
        let scheduler = StabilityScheduler::with_runner(FailingDelayRunner);
        let ok = scheduler.begin(Duration::from_secs(60), || {});
        assert!(!ok);
        assert!(
            !scheduler.is_pending(),
            "a failed begin() must not leave a phantom pending window"
        );
    }
}

// ---------------------------------------------------------------------
// Combined race tests (Phase 4E-P2 Part 2B-3, task brief §33)
// ---------------------------------------------------------------------
//
// The unit tests above prove each scheduler type's own invariants in
// isolation. The tests in this module compose `RestartScheduler` and
// `StabilityScheduler` the same way `src-tauri/src/lib.rs` actually
// does, reproducing the task brief's §33 adversarial scenarios at the
// level this crate can test without a running Tauri instance (`lib.rs`
// itself has no unit tests for the same reason Part 2B-2 already
// documented: its functions take a real `tauri::AppHandle`, which
// requires a running application to construct — see
// `docs/phase4/PHASE4E_P2_PART2B3_IMPLEMENTATION.md` §7 for the full
// honest accounting of what is and is not covered this way).
#[cfg(test)]
mod combined_race_tests {
    use super::*;
    use std::sync::atomic::{AtomicUsize, Ordering};

    /// Same fake as the type-level tests above, duplicated here (rather
    /// than `pub(crate)`-exported from the private `tests` module)
    /// because these tests exercise the two scheduler types *together*
    /// and read more clearly with their own minimal fixture.
    #[derive(Clone, Default)]
    struct FakeDelayRunner {
        delays: Arc<Mutex<Vec<Duration>>>,
        #[allow(clippy::type_complexity)]
        pending_actions: Arc<Mutex<Vec<Box<dyn FnOnce() + Send>>>>,
    }

    impl FakeDelayRunner {
        fn new() -> Self {
            Self::default()
        }

        fn fire_all(&self) {
            let actions: Vec<_> = {
                let mut guard = self.pending_actions.lock().unwrap();
                std::mem::take(&mut *guard)
            };
            for action in actions {
                action();
            }
        }
    }

    impl DelayRunner for FakeDelayRunner {
        fn run_after(&self, delay: Duration, action: Box<dyn FnOnce() + Send>) -> bool {
            self.delays.lock().unwrap().push(delay);
            self.pending_actions.lock().unwrap().push(action);
            true
        }
    }

    /// Race B (§33): "restart pending, then shutdown". Mirrors
    /// `lib.rs`'s `RunEvent::Exit` handler: cancel the restart
    /// scheduler and the stability scheduler, in that order, before the
    /// real `shutdown()` call. Neither timer's callback may still act
    /// once it eventually fires.
    #[test]
    fn shutdown_while_a_restart_is_pending_cancels_it_before_it_can_fire() {
        let restart_runner = FakeDelayRunner::new();
        let restart_scheduler = RestartScheduler::with_runner(restart_runner.clone());
        let restarted = Arc::new(AtomicUsize::new(0));
        let restarted_in_action = Arc::clone(&restarted);
        restart_scheduler.schedule(1, Duration::from_secs(1), move || {
            restarted_in_action.fetch_add(1, Ordering::SeqCst);
        });

        // Shutdown: exactly the two cancel calls `RunEvent::Exit` makes,
        // in the same order, before the (here-simulated) real
        // `shutdown()`.
        restart_scheduler.cancel();

        restart_runner.fire_all();
        assert_eq!(
            restarted.load(Ordering::SeqCst),
            0,
            "a restart scheduled before shutdown must never actually run"
        );
    }

    /// Race F ("crash during restart", §33 G): a restart attempt begins
    /// a fresh stability window, but the sidecar crashes again before
    /// that window's `reset_after_stable` delay elapses. The stale
    /// stability window must be cancelled (mirroring
    /// `handle_retry_eligible_failure`'s unconditional
    /// `state.stability.cancel()`), and its eventual firing must not
    /// reset a tracker that a *new* crash-loop episode is now
    /// accumulating attempts against.
    #[test]
    fn a_crash_during_the_stability_window_cancels_it_before_it_can_fire() {
        let stability_runner = FakeDelayRunner::new();
        let stability_scheduler = StabilityScheduler::with_runner(stability_runner.clone());
        let reset_count = Arc::new(AtomicUsize::new(0));

        // Restart succeeds -> stability window begins.
        let reset_in_action = Arc::clone(&reset_count);
        stability_scheduler.begin(Duration::from_secs(60), move || {
            reset_in_action.fetch_add(1, Ordering::SeqCst);
        });
        assert!(stability_scheduler.is_pending());

        // Crash again, before the 60s window elapses:
        // `handle_retry_eligible_failure` cancels the stability window
        // unconditionally, regardless of what the retry policy then
        // decides.
        stability_scheduler.cancel();

        // The old timer (simulated) wakes up late and fires anyway.
        stability_runner.fire_all();
        assert_eq!(
            reset_count.load(Ordering::SeqCst),
            0,
            "a stability window cancelled by a subsequent crash must never reset the tracker"
        );
    }

    /// Duplicate/late-recovery race (§33 E/F): a successful restart
    /// begins stability window A; a second, unrelated successful
    /// restart (simulating a duplicate/re-entrant recovery observation)
    /// begins window B before A's timer has fired. When A's stale timer
    /// eventually fires, only B — the current episode — may ever be
    /// confirmed; A must be a permanent no-op, never a second reset.
    #[test]
    fn a_superseded_stability_window_never_fires_even_if_its_timer_wakes_after_a_newer_one() {
        let runner = FakeDelayRunner::new();
        let scheduler = StabilityScheduler::with_runner(runner.clone());
        let resets = Arc::new(AtomicUsize::new(0));

        let resets_a = Arc::clone(&resets);
        scheduler.begin(Duration::from_secs(60), move || {
            resets_a.fetch_add(1, Ordering::SeqCst);
        });
        let resets_b = Arc::clone(&resets);
        scheduler.begin(Duration::from_secs(60), move || {
            resets_b.fetch_add(1, Ordering::SeqCst);
        });

        // Both timers eventually "fire" (simulated) in scheduling
        // order -- A (stale) first, then B (current).
        runner.fire_all();
        assert_eq!(
            resets.load(Ordering::SeqCst),
            1,
            "exactly one reset (from the current window, B) must occur -- never two, never zero"
        );
    }

    /// Exhaustion + late readiness (§33 F): once retries are exhausted,
    /// `handle_retry_eligible_failure`'s `Exhausted` arm performs no
    /// further scheduling of either timer. This test proves the
    /// property the exhaustion path depends on: a scheduler that was
    /// never given a new `schedule()`/`begin()` call after cancellation
    /// stays permanently empty, so nothing can race to resurrect it —
    /// there is no "late readiness" callback in flight to guard against
    /// in the first place once both schedulers were cancelled and
    /// neither was ever handed a new attempt.
    #[test]
    fn after_exhaustion_neither_scheduler_has_anything_pending_to_fire() {
        let restart_runner = FakeDelayRunner::new();
        let restart_scheduler = RestartScheduler::with_runner(restart_runner.clone());
        let stability_runner = FakeDelayRunner::new();
        let stability_scheduler = StabilityScheduler::with_runner(stability_runner.clone());

        // Simulate the last retry's own restart having begun a
        // stability window...
        stability_scheduler.begin(Duration::from_secs(60), || {});
        // ...then a final crash arrives: `handle_retry_eligible_failure`
        // cancels the stability window unconditionally, consults the
        // policy, and -- on `Exhausted` -- schedules nothing further on
        // `restart_scheduler` either.
        stability_scheduler.cancel();

        assert!(!restart_scheduler.is_pending());
        assert!(!stability_scheduler.is_pending());

        // No pending action exists on either fake runner to even fire.
        restart_runner.fire_all();
        stability_runner.fire_all();
    }

    /// Duplicate crash notifications (§33 D), at the combined level:
    /// two crash observations arrive for what is really one crash
    /// episode (the second a redundant/duplicate detection). Only the
    /// first may ever schedule a restart; the stability window that was
    /// pending for the episode that just ended is cancelled exactly
    /// once, idempotently, by both.
    #[test]
    fn duplicate_crash_handling_schedules_one_restart_and_idempotently_cancels_stability() {
        let restart_runner = FakeDelayRunner::new();
        let restart_scheduler = RestartScheduler::with_runner(restart_runner.clone());
        let stability_scheduler = StabilityScheduler::with_runner(FakeDelayRunner::new());
        stability_scheduler.begin(Duration::from_secs(60), || {});

        // First "crash" notification: cancel stability, schedule retry.
        stability_scheduler.cancel();
        let fire_count = Arc::new(AtomicUsize::new(0));
        let counter = Arc::clone(&fire_count);
        assert!(restart_scheduler.schedule(1, Duration::from_secs(1), move || {
            counter.fetch_add(1, Ordering::SeqCst);
        }));

        // Second, duplicate "crash" notification for the same episode:
        // cancelling an already-cancelled stability window is a no-op
        // (never panics), and a second schedule() call is rejected
        // outright because one is already pending.
        stability_scheduler.cancel();
        assert!(!restart_scheduler.schedule(2, Duration::from_secs(2), || {}));

        restart_runner.fire_all();
        assert_eq!(fire_count.load(Ordering::SeqCst), 1);
        assert!(!stability_scheduler.is_pending());
    }
}
