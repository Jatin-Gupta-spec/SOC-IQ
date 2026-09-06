//! Restart decision/accounting (Phase 4E-P2 Part 2B-1).
//!
//! Implements exactly `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md`
//! §7 ("Restart Policy"): a small, pure, `sidecar-core`-resident module
//! that decides *whether* another automatic restart attempt is allowed
//! and, if so, *what backoff delay* it should use — nothing more.
//!
//! # Scope boundary (read this before changing this file)
//!
//! This module answers exactly one question: **"can another automatic
//! restart be attempted, and after how long?"** It does not, and must
//! not, do any of the following (§7.2/§7.6, task brief §12/§19):
//!
//! - spawn, kill, or otherwise touch a real process
//! - sleep, start a timer, or read a real clock
//! - call [`crate::supervisor::Supervisor`] or mutate `Lifecycle` state
//! - decide *when* a backoff timer fires (that is Part 2B-2's job)
//! - decide *when* `reset_after_stable` has actually elapsed (that
//!   requires a real clock the caller owns — Part 2B-2's job); this
//!   module only exposes the explicit, deterministic [`RestartTracker::reset`]
//!   that a future timer-owning caller invokes once it has independently
//!   confirmed the sidecar has been continuously `RUNNING` for that long
//!
//! This mirrors the same "caller supplies the clock" boundary every
//! other module in this crate already uses (`supervisor.rs`'s own doc:
//! "this crate performs no real process spawning, no real I/O, and no
//! real timing"; see `Supervisor::startup_timed_out`'s review note for
//! the identical trust boundary applied to timeouts).
//!
//! # Two separate types, per §7.2
//!
//! - [`RestartPolicy`]: **configuration** — the four values from §7.2's
//!   struct, with §7.3/§7.4/§7.5's defaults (5 attempts, 1s/30s
//!   exponential backoff, 60s stability reset). Also owns the pure
//!   backoff calculation (§7.4/§11 of the task brief: "if the
//!   architecture explicitly places [backoff] here, it may be
//!   implemented and tested here").
//! - [`RestartTracker`]: **accounting** — the single authoritative
//!   owner of "how many restart attempts have happened in the current
//!   crash-loop window" (§7.5). It is deliberately the only counter in
//!   the crate for this; nothing else in `sidecar-core` or (as of this
//!   checkpoint) `src-tauri` tracks restart attempts.
//!
//! # Attempt semantics (§7.5, determined — not guessed)
//!
//! - **Initial startup does not count.** A `RestartTracker` starts at
//!   zero attempts. Only a *retry* — a restart the policy decided to
//!   allow after a startup failure or a runtime crash — increments the
//!   counter. This follows directly from §7.5's own wording ("consume
//!   attempts from the same bounded counter" refers to startup failure
//!   and runtime crash, i.e. failures, not the first launch) and from
//!   §6.5 ("no further automatic `reset()`... a permanent, user-visible
//!   'sidecar unavailable'" only makes sense as a count of *failed
//!   recovery attempts*, not of launches in general).
//! - **Both startup failure and runtime crash increment the same
//!   counter** (§6.2: "there is no reason to give a
//!   crash-immediately-after-launch a separate, more lenient budget").
//!   This module does not distinguish the two — the caller (Part 2B-2)
//!   is responsible for classifying the failure; `RestartTracker` only
//!   ever sees "one more retry-eligible failure occurred."
//! - **Increment happens exactly when the policy decides to retry**
//!   (§7.5: "on every `RUNNING -> CRASHED` or a failed startup attempt
//!   ... that the policy decides to retry" — an `Exhausted` decision
//!   does *not* increment the counter further; the counter's final
//!   value after exhaustion is exactly `max_attempts`, never more,
//!   because the caller has no reason to call
//!   [`RestartTracker::record_attempt`] again once
//!   [`RestartTracker::decide`] has already reported [`RestartDecision::Exhausted`]).
//! - **Reset is explicit and deterministic** (task brief §10): calling
//!   [`RestartTracker::reset`] is the only way the counter returns to
//!   zero. This module does not call it automatically, does not infer
//!   "the process spawned" as recovery, and does not read a clock to
//!   decide the 60s stability window has elapsed — per §7.5, that
//!   determination belongs to a future real-time-owning caller
//!   (Part 2B-2), which will call `reset()` once it has independently
//!   confirmed continuous `RUNNING` for `reset_after_stable`.
//!
//! # No automatic restart (§12 of the task brief, §7.6 of the architecture)
//!
//! Nothing in this module calls [`crate::supervisor::Supervisor::reset`]
//! or [`crate::supervisor::Supervisor::request_start`]. [`RestartTracker::decide`]
//! only ever returns a value describing what *could* happen next; no
//! code path here performs it.

use std::sync::atomic::{AtomicU64, Ordering};
use std::time::Duration;

/// Restart policy configuration (§7.2/§7.3/§7.4/§7.5). Pure
/// configuration plus the one pure calculation (backoff) the
/// architecture explicitly places here (§7.4) — no I/O, no timing, no
/// mutable state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RestartPolicy {
    /// Hard ceiling on restart attempts within one crash-loop window
    /// (§7.3). Exceeding this yields [`RestartDecision::Exhausted`].
    pub max_attempts: u32,
    /// First backoff delay (§7.4): the delay before the 1st restart
    /// attempt.
    pub base_delay: Duration,
    /// Backoff cap (§7.4): no computed delay ever exceeds this.
    pub max_delay: Duration,
    /// Sustained `RUNNING` duration that resets the attempt counter
    /// (§7.5). Not enforced by this module — see the module doc's
    /// scope boundary. Carried here only as policy configuration for
    /// the future real-time-owning caller (Part 2B-2) to read.
    pub reset_after_stable: Duration,
}

impl RestartPolicy {
    /// Construct an explicit policy. Does not validate the values —
    /// §7.2 of the architecture specifies no validation requirement,
    /// and the task brief §15/§21 warns against inventing one
    /// ("Do not invent validation requirements" / "Do not add
    /// speculative configuration").
    pub fn new(
        max_attempts: u32,
        base_delay: Duration,
        max_delay: Duration,
        reset_after_stable: Duration,
    ) -> Self {
        Self {
            max_attempts,
            base_delay,
            max_delay,
            reset_after_stable,
        }
    }

    /// Pure backoff calculation (§7.4): capped exponential backoff,
    /// doubling per attempt, no jitter. `attempt` is the 1-based
    /// number of the restart attempt this delay precedes (the 1st
    /// retry's delay is `backoff_for_attempt(1)`, the 2nd's is
    /// `backoff_for_attempt(2)`, etc.) — matching
    /// [`RestartDecision::Retry`]'s `attempt` field.
    ///
    /// `attempt = 0` is treated the same as `attempt = 1` (the base
    /// delay) rather than panicking or underflowing, since it is not a
    /// value [`RestartTracker::decide`] ever actually produces (attempt
    /// numbers start at 1) but is not worth making this function
    /// partial over.
    ///
    /// Sequence for the §7.4/§7.3 defaults (1s base, 30s cap): `1s, 2s,
    /// 4s, 8s, 16s, 30s, 30s, ...` for attempts `1, 2, 3, 4, 5, 6, 7,
    /// ...` — exactly §7.4's documented sequence.
    pub fn backoff_for_attempt(&self, attempt: u32) -> Duration {
        let exponent = attempt.saturating_sub(1).min(63);
        let base_ms = self.base_delay.as_millis().min(u128::from(u64::MAX));
        let scaled_ms = base_ms.saturating_mul(1u128 << exponent);
        let capped_ms = scaled_ms.min(self.max_delay.as_millis());
        Duration::from_millis(capped_ms.min(u128::from(u64::MAX)) as u64)
    }
}

impl Default for RestartPolicy {
    /// §7.3/§7.4/§7.5's chosen defaults: 5 attempts, 1s->30s capped
    /// exponential backoff, 60s stability reset.
    fn default() -> Self {
        Self {
            max_attempts: 5,
            base_delay: Duration::from_secs(1),
            max_delay: Duration::from_secs(30),
            reset_after_stable: Duration::from_secs(60),
        }
    }
}

/// The decision [`RestartTracker::decide`] returns — mirrors §7.2's
/// pseudocode exactly (`Retry { after: Duration }` / `Exhausted`), with
/// an added `attempt` field on `Retry` (the attempt number the backoff
/// delay was computed for) and an added `attempts` field on `Exhausted`
/// (the final attempt count), since both are needed by any caller that
/// wants to log or emit them (§13/§10 of the architecture) without
/// re-deriving them.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum RestartDecision {
    /// Another automatic restart attempt is allowed. `attempt` is its
    /// 1-based number; `after` is the backoff delay a future
    /// timer-owning caller (Part 2B-2) should wait before making it.
    /// This checkpoint does not start that timer (§12 of the task
    /// brief) — the decision is data, not an action.
    Retry { attempt: u32, after: Duration },
    /// No further automatic restart attempt is allowed:
    /// `max_attempts` has already been reached. `attempts` is the
    /// tracker's attempt count at the time of the decision (always
    /// exactly `policy.max_attempts` when this variant is produced by
    /// a tracker whose count only ever advances one at a time via
    /// [`RestartTracker::record_attempt`]).
    Exhausted { attempts: u32 },
}

impl RestartDecision {
    /// Convenience predicate, for callers that only care whether
    /// retrying is possible at all.
    pub fn is_retry(&self) -> bool {
        matches!(self, RestartDecision::Retry { .. })
    }

    /// Convenience predicate, the inverse of [`RestartDecision::is_retry`].
    pub fn is_exhausted(&self) -> bool {
        matches!(self, RestartDecision::Exhausted { .. })
    }
}

/// Restart-attempt accounting (§7.2/§7.5). The single authoritative
/// owner of "how many restart attempts have happened in the current
/// crash-loop window" — see the module doc for why nothing else in the
/// crate duplicates this counter.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub struct RestartTracker {
    attempts: u32,
}

impl RestartTracker {
    /// A fresh tracker: zero attempts recorded. Per the module doc's
    /// attempt semantics, this represents "no restart has been
    /// attempted yet" — it is also the correct initial state for a
    /// sidecar that has not yet had its first (non-restart) launch,
    /// since initial startup never itself counts as an attempt.
    pub fn new() -> Self {
        Self { attempts: 0 }
    }

    /// Current attempt count in the active crash-loop window.
    pub fn attempts(&self) -> u32 {
        self.attempts
    }

    /// Decide whether another automatic restart attempt is allowed
    /// under `policy`, given this tracker's current attempt count.
    /// Pure: does not mutate the tracker, does not touch a clock, does
    /// not perform or schedule anything (§7.6/§12).
    ///
    /// `self.attempts >= policy.max_attempts` is the exhaustion
    /// condition: once `max_attempts` retries have already been
    /// recorded, no further one is allowed. Otherwise the next attempt
    /// (`self.attempts + 1`) is allowed, with its backoff delay
    /// computed by [`RestartPolicy::backoff_for_attempt`].
    pub fn decide(&self, policy: &RestartPolicy) -> RestartDecision {
        if self.attempts >= policy.max_attempts {
            return RestartDecision::Exhausted {
                attempts: self.attempts,
            };
        }
        let attempt = self.attempts + 1;
        RestartDecision::Retry {
            attempt,
            after: policy.backoff_for_attempt(attempt),
        }
    }

    /// Record that a retry-eligible failure occurred and the policy
    /// decided to retry (§7.5: "on every `RUNNING -> CRASHED` or a
    /// failed startup attempt ... that the policy decides to retry").
    /// Increments the attempt count by exactly one and returns the new
    /// count.
    ///
    /// Callers should only call this after a corresponding
    /// [`RestartTracker::decide`] returned [`RestartDecision::Retry`] —
    /// this method itself does not consult a [`RestartPolicy`] or
    /// refuse to increment past `max_attempts`, matching §7.2's
    /// division of labor: the *policy* decides eligibility; the
    /// *tracker* only accounts. (Part 2B-1 does not wire this
    /// division into an automatic caller — see the module doc.)
    pub fn record_attempt(&mut self) -> u32 {
        self.attempts += 1;
        self.attempts
    }

    /// Explicit, deterministic reset of the attempt count to zero
    /// (§7.5, task brief §10). Never called automatically by this
    /// module — see the module doc's scope boundary and attempt
    /// semantics.
    pub fn reset(&mut self) {
        self.attempts = 0;
    }
}

// ---------------------------------------------------------------------
// RestartSchedule / RestartToken (Phase 4E-P2 Part 2B-2)
// ---------------------------------------------------------------------
//
// Pure "at most one pending restart" bookkeeping — no real timer, no
// real clock, no I/O, matching this crate's existing boundary
// (`RestartPolicy`/`RestartTracker`'s own doc above). The *real* timer
// that actually waits and fires lives in `src-tauri`'s
// `RestartScheduler` (task brief §9), which composes one of these per
// sidecar lifecycle. This type only answers three questions, all
// synchronously and deterministically:
//
// - is a restart currently pending? (`is_pending`/`pending_attempt`)
// - can a new one begin? (`try_begin`) — at most one at a time (task
//   brief §6/§15), enforced here, not merely by caller discipline
// - does *this* fired timer still correspond to the currently pending
//   restart, or has it been superseded/cancelled/already consumed?
//   (`consume`) — the mechanism behind duplicate-callback (§16) and
//   stale-callback (§17) protection

/// Uniquely identifies one `try_begin` call, across every
/// `RestartSchedule` instance in the process — deliberately a
/// globally, not per-instance, monotonic id (a plain per-instance
/// counter starting at the same value in two different schedules would
/// let a token from one collide with a token from another). Opaque:
/// callers only ever obtain one from `try_begin` and hand it back to
/// `consume`, never construct or inspect one directly.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct RestartToken(u64);

/// Process-wide token counter. A plain global atomic, not a per-`RestartSchedule`
/// field, specifically so tokens minted by two different `RestartSchedule`
/// instances (e.g. two independent sidecars, or a test's own throwaway
/// instance) can never collide — see [`RestartToken`]'s doc.
static NEXT_RESTART_TOKEN: AtomicU64 = AtomicU64::new(1);

/// At-most-one-pending-restart bookkeeping (task brief §6/§9/§15/§19).
/// Pure: no timer, no clock, no I/O — see this module's Part 2B-2
/// section doc above.
#[derive(Debug, Default)]
pub struct RestartSchedule {
    pending: Option<(RestartToken, u32)>,
}

impl RestartSchedule {
    /// A fresh schedule: nothing pending.
    pub fn new() -> Self {
        Self::default()
    }

    /// Whether a restart is currently pending (begun, not yet consumed
    /// or cancelled).
    pub fn is_pending(&self) -> bool {
        self.pending.is_some()
    }

    /// The attempt number of the currently pending restart, if any —
    /// for logging/observability callers that want it without also
    /// needing the opaque token.
    pub fn pending_attempt(&self) -> Option<u32> {
        self.pending.map(|(_, attempt)| attempt)
    }

    /// Attempt to begin scheduling restart attempt number `attempt`.
    /// Returns the [`RestartToken`] the caller must present back to
    /// [`RestartSchedule::consume`] when its timer fires, or `None` if
    /// a restart is already pending (task brief §6/§15: duplicate
    /// scheduling is impossible, not merely discouraged) — the caller
    /// must not start a second timer in that case.
    pub fn try_begin(&mut self, attempt: u32) -> Option<RestartToken> {
        if self.pending.is_some() {
            return None;
        }
        let token = RestartToken(NEXT_RESTART_TOKEN.fetch_add(1, Ordering::Relaxed));
        self.pending = Some((token, attempt));
        Some(token)
    }

    /// Present a token when its timer fires. Returns `true` — and
    /// clears the pending restart — exactly once per successful
    /// `try_begin`: only when `token` matches the currently pending
    /// restart's token. Returns `false` (a deliberate no-op, task brief
    /// §16/§17/§21) for:
    /// - a duplicate/re-entrant presentation of a token already
    ///   consumed,
    /// - a token from a schedule that was since cancelled,
    /// - a stale token from a superseded (already-consumed-and-replaced)
    ///   restart,
    /// - a token that was never issued by this schedule at all.
    pub fn consume(&mut self, token: RestartToken) -> bool {
        match self.pending {
            Some((pending_token, _)) if pending_token == token => {
                self.pending = None;
                true
            }
            _ => false,
        }
    }

    /// Explicit, idempotent cancellation (task brief §21): clears any
    /// currently pending restart. Safe to call any number of times,
    /// including when nothing is pending — never panics, never errors.
    /// A token from a cancelled restart can never later be
    /// [`RestartSchedule::consume`]d successfully, even if the caller's
    /// real timer still fires afterward (the timer itself is not, and
    /// does not need to be, interrupted — see `src-tauri`'s
    /// `RestartScheduler` module doc for why).
    pub fn cancel(&mut self) {
        self.pending = None;
    }
}

// ---------------------------------------------------------------------
// StabilityWindow / StabilityToken (Phase 4E-P2 Part 2B-3)
// ---------------------------------------------------------------------
//
// Pure "is a stability-reset window currently pending" bookkeeping —
// the `reset_after_stable` half of §7.5 that Part 2B-2 explicitly left
// unimplemented (`PHASE4E_P2_PART2B2_IMPLEMENTATION.md` §5: "requires a
// real-time-owning caller that confirms *continuous* RUNNING for 60s").
// Same boundary as `RestartSchedule` above: no real clock, no I/O, no
// timer — only token-based identity so a caller (`src-tauri`'s
// `StabilityScheduler`, composing this with a real `DelayRunner`) can
// tell "this fired stability check still corresponds to the RUNNING
// episode it was started for" from "the sidecar has since crashed,
// been restarted, or been intentionally shut down, and a stale timer
// from an earlier episode just woke up."
//
// `RestartTracker::reset` (§7.5) is only ever safe to call once a
// caller has independently confirmed *continuous* RUNNING for the
// full `reset_after_stable` duration — this type is exactly that
// confirmation mechanism, deliberately separate from `RestartSchedule`
// (which tracks pending *retries*, not pending *stability checks*;
// conflating the two would let a stability timer and a restart timer
// contend for the same one-pending slot, which they must not, since
// both a stability check and a subsequent crash's retry can
// legitimately be in flight-adjacent states).

/// Uniquely identifies one [`StabilityWindow::begin`] call, process-wide
/// (not per-instance) — same rationale as [`RestartToken`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StabilityToken(u64);

static NEXT_STABILITY_TOKEN: AtomicU64 = AtomicU64::new(1);

/// At-most-one-pending-stability-check bookkeeping (Part 2B-3). Pure —
/// see this module's Part 2B-3 section doc above.
#[derive(Debug, Default)]
pub struct StabilityWindow {
    pending: Option<StabilityToken>,
}

impl StabilityWindow {
    /// A fresh window: nothing pending.
    pub fn new() -> Self {
        Self::default()
    }

    /// Whether a stability check is currently pending (begun, not yet
    /// confirmed or cancelled).
    pub fn is_pending(&self) -> bool {
        self.pending.is_some()
    }

    /// Begin a new stability window, superseding any previously pending
    /// one unconditionally. Unlike [`RestartSchedule::try_begin`], this
    /// never refuses: every fresh `RUNNING` episode (an initial start or
    /// a successful restart) legitimately supersedes whatever stability
    /// window an earlier episode may have left pending — there is only
    /// ever one *current* `RUNNING` episode at a time (the single
    /// `process` mutex already guarantees that), so the old token
    /// simply becomes permanently unconfirmable (see
    /// [`StabilityWindow::confirm`]), exactly like an old
    /// [`RestartToken`] becomes stale once superseded.
    pub fn begin(&mut self) -> StabilityToken {
        let token = StabilityToken(NEXT_STABILITY_TOKEN.fetch_add(1, Ordering::Relaxed));
        self.pending = Some(token);
        token
    }

    /// Present a token when its timer fires. Returns `true` — and
    /// clears the pending window — exactly once per successful
    /// `begin`: only when `token` matches the currently pending
    /// window's token. Returns `false` (a deliberate no-op) for a
    /// stale token from a superseded or cancelled window, or a token
    /// never issued by this window at all — the same three cases
    /// [`RestartSchedule::consume`] guards against.
    pub fn confirm(&mut self, token: StabilityToken) -> bool {
        match self.pending {
            Some(pending) if pending == token => {
                self.pending = None;
                true
            }
            _ => false,
        }
    }

    /// Explicit, idempotent cancellation: clears any currently pending
    /// stability window. Called whenever the `RUNNING` episode it was
    /// tracking ends for any reason other than reaching the full
    /// `reset_after_stable` duration — a crash, a failed restart, or an
    /// intentional shutdown — so a stale timer from that ended episode
    /// can never later reset the attempt counter (task brief §21/§24:
    /// "a failed restart must not erase the crash history").
    pub fn cancel(&mut self) {
        self.pending = None;
    }
}
