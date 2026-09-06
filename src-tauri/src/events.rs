//! Phase 4E-P3 Part 2A — canonical lifecycle event contract and backend
//! event adapter.
//!
//! Scope (see `docs/phase4/PHASE4E_P3_PART2A_EVENT_ADAPTER_IMPLEMENTATION.md`
//! for the full checkpoint report): this module implements exactly one
//! canonical event, [`EVENT_STATE_CHANGED`] (`sidecar:state_changed`),
//! its payload contract (architecture doc
//! `docs/phase4/PHASE4E_P3_SIDECAR_LIFECYCLE_EVENT_ARCHITECTURE.md` §10.1),
//! and the one adapter function ([`emit_state_changed`]) that
//! `lib.rs`'s existing lifecycle call sites use to emit it.
//!
//! **Phase 4E-P3 Part 2C update** (architecture doc §9.3/§12.4;
//! implementation report:
//! `docs/phase4/PHASE4E_P3_PART2C_RESTART_EVENTS_STATUS_SNAPSHOT_AUDIT.md`):
//! this module now also owns `sidecar:restart_scheduled`
//! ([`EVENT_RESTART_SCHEDULED`]/[`emit_restart_scheduled`]),
//! `sidecar:restart_exhausted`
//! ([`EVENT_RESTART_EXHAUSTED`]/[`emit_restart_exhausted`]), and the
//! [`SidecarStatus`] snapshot DTO `lib.rs`'s new `get_sidecar_status`
//! command returns — the three items originally deferred here. Still
//! explicitly out of scope, unchanged:
//!   - Full frontend-facing `sequence` drop/dedup semantics
//!     (architecture doc §12.2) — [`EventSequencer`] remains a real,
//!     monotonic, never-reset counter plus (as of this checkpoint) a
//!     non-allocating peek ([`EventSequencer::current_sequence`]); the
//!     frontend consumer side of the drop rule is still nobody's job
//!     in this crate, since there is still no frontend consumer here
//!     (frontend remains out of scope, task brief §1: "Do not build
//!     React UI").
//!   - An event-history/replay mechanism — [`SidecarStatus`] is a
//!     point-in-time snapshot only, never a log of past events (task
//!     brief §21).
//!
//! # Ownership (task brief §10/§20 of the architecture doc)
//!
//! [`emit_state_changed`] is the **one** application-boundary adapter
//! function. Every real `Lifecycle` transition `lib.rs` drives (the
//! initial launch, a crash-triggered restart, an intentional shutdown)
//! goes through this one function to reach the frontend; nothing else
//! in this crate calls `AppHandle::emit` directly, and no `.emit(`
//! call exists anywhere in `sidecar-core` (grep-confirmed — that
//! crate has no `tauri` dependency at all, see its own `Cargo.toml`).

use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};
use std::time::{SystemTime, UNIX_EPOCH};

use sidecar_core::{LifecycleState, SidecarError};
use tauri::Emitter;

/// The one canonical lifecycle event name (architecture doc §9.3).
/// Deliberately singular — no per-transition names
/// (`sidecar:started`/`sidecar:crashed`/etc.) are introduced; see the
/// architecture doc §9.2 for why that model was rejected.
pub const EVENT_STATE_CHANGED: &str = "sidecar:state_changed";

/// Phase 4E-P3 Part 2C: emitted once a restart attempt has actually
/// been **accepted** by the existing `restart_scheduler::RestartScheduler`
/// (task brief §6/§18 — never merely because the backend *intends* to
/// attempt one). See [`emit_restart_scheduled`].
pub const EVENT_RESTART_SCHEDULED: &str = "sidecar:restart_scheduled";

/// Phase 4E-P3 Part 2C: emitted once, when the existing frozen
/// `sidecar_core::restart::RestartPolicy`/`RestartTracker` pair
/// actually reports [`sidecar_core::RestartDecision::Exhausted`] (task
/// brief §13/§14 — no new exhaustion condition, no new counter). See
/// [`emit_restart_exhausted`].
pub const EVENT_RESTART_EXHAUSTED: &str = "sidecar:restart_exhausted";

/// Backend-owned, process-lifetime counters used to populate
/// `sequence`/`generation` on every emitted event (architecture doc
/// §10.4). Owned alongside `SidecarState`'s other fields in `lib.rs`
/// (single owner, no second emitter/counter anywhere).
///
/// **Part 2A boundary:** this is the minimal foundation the task
/// brief §14 calls for — a real, monotonic, never-reset counter — not
/// the full reconciliation/dedup design. The frontend drop rule that
/// makes `sequence` load-bearing for correctness (architecture doc
/// §12.2) is Part 2B's job; nothing here anticipates or partially
/// implements it beyond providing a value that will support it later.
#[derive(Debug, Default)]
pub struct EventSequencer {
    sequence: AtomicU64,
    generation: AtomicU32,
}

impl EventSequencer {
    pub fn new() -> Self {
        Self::default()
    }

    /// Strictly increasing for the life of the process; never reset,
    /// never reused (architecture doc §10.4).
    fn next_sequence(&self) -> u64 {
        self.sequence.fetch_add(1, Ordering::SeqCst) + 1
    }

    /// Called once per real `NotStarted -> Starting` transition
    /// (architecture doc §10.4: "increments by exactly one on every
    /// `NotStarted -> Starting` transition").
    fn bump_generation(&self) -> u32 {
        self.generation.fetch_add(1, Ordering::SeqCst) + 1
    }

    /// The current generation, for a transition that isn't itself a
    /// new launch attempt. Before the first launch this is `0` in the
    /// atomic, but no event is ever emitted before the first
    /// `NotStarted -> Starting` transition bumps it to `1`, so callers
    /// always observe `>= 1`.
    fn current_generation(&self) -> u32 {
        self.generation.load(Ordering::SeqCst).max(1)
    }

    /// Part 2C: read the latest allocated sequence value **without**
    /// allocating a new one — [`get_sidecar_status`](crate::get_sidecar_status)'s
    /// one hard requirement (task brief §11/§26: "NO `next_sequence()`
    /// inside the status command"). `0` before any event has ever been
    /// emitted; every real emission's `sequence` is `>= 1`, so a status
    /// snapshot's caller can distinguish "no event yet" from "the
    /// latest event's sequence" unambiguously.
    pub fn current_sequence(&self) -> u64 {
        self.sequence.load(Ordering::SeqCst)
    }
}

/// `reason` payload — present only when a transition's origin was a
/// [`SidecarError`] (architecture doc §10.1: `Starting->Failed`,
/// `Starting->Timeout`, `Running->Crashed`, `Stopping->Failed`).
/// `code` reuses [`SidecarError::code`] verbatim — no second
/// error-code vocabulary is introduced here.
#[derive(Debug, Clone, PartialEq, Eq, serde::Serialize)]
pub struct StateChangeReason {
    pub code: String,
    pub message: String,
}

impl From<&SidecarError> for StateChangeReason {
    fn from(err: &SidecarError) -> Self {
        Self {
            code: err.code().to_string(),
            message: err.to_string(),
        }
    }
}

/// `sidecar:state_changed` payload — architecture doc §10.1, exactly.
///
/// **Forbidden fields, deliberately absent** (§10.1's explicit list,
/// re-verified against `sidecar-core/src/error.rs`'s `Display` impls
/// this checkpoint, architecture doc §23): no PID, no command line,
/// no launch arguments, no environment variables, no API keys/secrets,
/// no thread IDs, no mutex internals, no OS internals, no raw stack
/// trace. `reason.message` reuses `SidecarError::to_string()` as-is —
/// every variant's `Display` impl already reports only a category, a
/// duration, an exit code, or a short caller-supplied string, so no
/// additional filtering is needed (architecture doc §23's own finding,
/// re-confirmed by direct read of `error.rs` this checkpoint).
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct StateChangedPayload {
    pub state: String,
    pub previous_state: String,
    pub reason: Option<StateChangeReason>,
    pub sequence: u64,
    pub generation: u32,
    pub timestamp: String,
}

/// Uppercase, underscore-separated wire name for a [`LifecycleState`]
/// (architecture doc §10.1's union: `"NOT_STARTED" | "STARTING" | ...`).
/// `LifecycleState`'s own `Display` impl (`sidecar-core/src/state.rs`)
/// already produces exactly this shape, reused verbatim rather than
/// duplicating the mapping table here.
fn state_name(state: LifecycleState) -> String {
    state.to_string()
}

/// Builds the payload for one `state_changed` emission. Split out
/// from [`emit_state_changed`] specifically so it is testable without
/// a real `AppHandle`/webview (this checkpoint's Test 1/Test 3/Test 4,
/// task brief §21).
fn build_state_changed_payload(
    sequencer: &EventSequencer,
    previous: LifecycleState,
    current: LifecycleState,
    reason: Option<&SidecarError>,
) -> StateChangedPayload {
    if previous == LifecycleState::NotStarted && current == LifecycleState::Starting {
        sequencer.bump_generation();
    }

    StateChangedPayload {
        state: state_name(current),
        previous_state: state_name(previous),
        reason: reason.map(StateChangeReason::from),
        sequence: sequencer.next_sequence(),
        generation: sequencer.current_generation(),
        timestamp: rfc3339_now(),
    }
}

/// The one adapter entry point (module doc above). Constructs the
/// approved payload from an **already-authoritative** transition (the
/// caller has already performed the transition and is reporting its
/// real outcome — this function never itself decides or performs a
/// transition, per architecture doc §4/§9.1: "the event system is an
/// observer of lifecycle truth, not a lifecycle authority") and emits
/// it under the one canonical event name.
///
/// A failure to emit (e.g. no listener/webview yet) is logged, not
/// propagated — an event-delivery failure must never be allowed to
/// affect sidecar lifecycle control flow, which is exactly the
/// one-way "observer, never authority" boundary this checkpoint
/// exists to enforce.
pub fn emit_state_changed(
    app_handle: &tauri::AppHandle,
    sequencer: &EventSequencer,
    previous: LifecycleState,
    current: LifecycleState,
    reason: Option<&SidecarError>,
) {
    let payload = build_state_changed_payload(sequencer, previous, current, reason);
    if let Err(err) = app_handle.emit(EVENT_STATE_CHANGED, &payload) {
        eprintln!("SOC-IQ: failed to emit {EVENT_STATE_CHANGED}: {err}");
    }
}

/// `sidecar:restart_scheduled` payload (Part 2C, task brief §8).
///
/// **Forbidden fields, deliberately absent** — same list as
/// [`StateChangedPayload`]'s doc: no PID, no process handle, no
/// command line, no launch arguments, no environment variables, no
/// secrets, no internal OS details, no private filesystem paths. This
/// payload owns its data outright: `attempt` and `delay_ms` are
/// `Copy` values read from the scheduler's already-accepted decision
/// (never a reference into `Mutex`/`SidecarProcess`/`Supervisor`/
/// `RestartScheduler` — task brief §8, "no references... may survive
/// payload construction").
///
/// `delay_ms`: the actual backoff delay the scheduler accepted for
/// this attempt (`RestartDecision::Retry::after`, as reported by
/// `RestartPolicy::backoff_for_attempt` — never independently
/// recomputed here, task brief §10).
///
/// `timestamp`: the moment this event was constructed, i.e.
/// immediately after `RestartScheduler::schedule` returned `true`
/// (the schedule was actually accepted) — not the moment the crash
/// was observed, and not a prediction of when the restart will
/// actually fire.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct RestartScheduledPayload {
    pub attempt: u32,
    pub delay_ms: u64,
    pub sequence: u64,
    pub timestamp: String,
}

/// `sidecar:restart_exhausted` payload (Part 2C, task brief §13/§14).
///
/// `attempts` reuses the exact value `RestartTracker`/`RestartPolicy`
/// (via `RestartDecision::Exhausted::attempts`) already reports —
/// always `policy.max_attempts` by construction (that type's own doc)
/// — never a second, independently-derived count. `code` reuses
/// [`SidecarError::code`] for `SidecarError::RestartExhausted`
/// verbatim, matching [`StateChangeReason`]'s existing precedent of
/// never introducing a second error-code vocabulary.
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct RestartExhaustedPayload {
    pub attempts: u32,
    pub code: String,
    pub sequence: u64,
    pub timestamp: String,
}

fn build_restart_scheduled_payload(
    sequencer: &EventSequencer,
    attempt: u32,
    delay: std::time::Duration,
) -> RestartScheduledPayload {
    RestartScheduledPayload {
        attempt,
        delay_ms: delay.as_millis().min(u128::from(u64::MAX)) as u64,
        sequence: sequencer.next_sequence(),
        timestamp: rfc3339_now(),
    }
}

fn build_restart_exhausted_payload(
    sequencer: &EventSequencer,
    attempts: u32,
) -> RestartExhaustedPayload {
    let err = SidecarError::RestartExhausted { attempts };
    RestartExhaustedPayload {
        attempts,
        code: err.code().to_string(),
        sequence: sequencer.next_sequence(),
        timestamp: rfc3339_now(),
    }
}

/// Emit `sidecar:restart_scheduled` for a restart attempt that the
/// existing `restart_scheduler::RestartScheduler` has **already
/// accepted** — callers must only invoke this after
/// `RestartScheduler::schedule` returned `true` (task brief §6/§18:
/// never emit merely because a restart was *intended*). Like
/// [`emit_state_changed`], a delivery failure is logged, never
/// propagated — the event system remains a pure observer.
pub fn emit_restart_scheduled(
    app_handle: &tauri::AppHandle,
    sequencer: &EventSequencer,
    attempt: u32,
    delay: std::time::Duration,
) {
    let payload = build_restart_scheduled_payload(sequencer, attempt, delay);
    if let Err(err) = app_handle.emit(EVENT_RESTART_SCHEDULED, &payload) {
        eprintln!("SOC-IQ: failed to emit {EVENT_RESTART_SCHEDULED}: {err}");
    }
}

/// Emit `sidecar:restart_exhausted` for a crash-loop window the
/// existing frozen `RestartPolicy`/`RestartTracker` pair has **already
/// reported** as exhausted (`RestartDecision::Exhausted`) — callers
/// must only invoke this from that decision arm (task brief §13:
/// never infer exhaustion using a new condition). The caller (this
/// checkpoint's one call site, `lib.rs`'s `handle_retry_eligible_failure`)
/// is reached at most once per real crash-loop-window exhaustion by
/// construction — see that function's doc — so no separate
/// dedup/one-shot flag is introduced here (task brief §14: "use
/// existing policy/tracker state wherever possible").
pub fn emit_restart_exhausted(
    app_handle: &tauri::AppHandle,
    sequencer: &EventSequencer,
    attempts: u32,
) {
    let payload = build_restart_exhausted_payload(sequencer, attempts);
    if let Err(err) = app_handle.emit(EVENT_RESTART_EXHAUSTED, &payload) {
        eprintln!("SOC-IQ: failed to emit {EVENT_RESTART_EXHAUSTED}: {err}");
    }
}

/// Read-only, immutable snapshot DTO for
/// [`get_sidecar_status`](crate::get_sidecar_status) (Part 2C, task
/// brief §21/§24). Frontend-facing only — never a lifecycle authority
/// (task brief §24): nothing in this crate ever constructs a
/// `Lifecycle`/`SidecarProcess` transition from a `SidecarStatus`, and
/// this type has no method that could perform one.
///
/// Fields (task brief §25 — minimum required by the architecture):
/// - `state`: the current, authoritative `LifecycleState`, same wire
///   format as [`StateChangedPayload::state`].
/// - `restart_pending` / `restart_pending_attempt`: read from the
///   existing `RestartScheduler`/`RestartSchedule` authority (task
///   brief §28) — never a second `frontend_restart_pending` source of
///   truth.
/// - `restart_attempts`: the existing `RestartTracker`'s current
///   count — the same counter `restart_scheduled`/`restart_exhausted`
///   already report from, never re-derived.
/// - `restart_exhausted`: `true` exactly when the existing frozen
///   `RestartTracker`/`RestartPolicy` pair's own exhaustion condition
///   (`attempts >= max_attempts`, task brief §13/§29 — the identical
///   comparison `RestartTracker::decide` uses, not a new one) holds
///   right now.
/// - `sequence`: the latest allocated event sequence
///   ([`EventSequencer::current_sequence`] — never a newly allocated
///   one, task brief §26).
#[derive(Debug, Clone, PartialEq, serde::Serialize)]
pub struct SidecarStatus {
    pub state: String,
    pub restart_pending: bool,
    pub restart_pending_attempt: Option<u32>,
    pub restart_attempts: u32,
    pub restart_exhausted: bool,
    pub sequence: u64,
}

/// RFC 3339 UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`), second precision.
/// No external date/time dependency is added — matching this crate's
/// existing dependency discipline (`Cargo.toml`'s own comment re:
/// deliberately no async runtime/no new dependency until an actual
/// caller needs one). Implements the standard civil-from-days
/// algorithm (Howard Hinnant's `civil_from_days`) against
/// `std::time::SystemTime` alone.
fn rfc3339_now() -> String {
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();
    format_rfc3339(secs)
}

fn format_rfc3339(unix_secs: u64) -> String {
    let days = (unix_secs / 86400) as i64;
    let rem = unix_secs % 86400;
    let (hour, minute, second) = (rem / 3600, (rem % 3600) / 60, rem % 60);

    let z = days + 719468;
    let era = (if z >= 0 { z } else { z - 146096 }) / 146097;
    let doe = (z - era * 146097) as u64; // [0, 146096]
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365; // [0, 399]
    let y = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100); // [0, 365]
    let mp = (5 * doy + 2) / 153; // [0, 11]
    let d = doy - (153 * mp + 2) / 5 + 1; // [1, 31]
    let m: u32 = if mp < 10 { (mp + 3) as u32 } else { (mp - 9) as u32 };
    let y = if m <= 2 { y + 1 } else { y };

    format!(
        "{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        y, m, d, hour, minute, second
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use sidecar_core::LifecycleState::*;

    // Test 1 — payload construction: an authoritative transition
    // produces the correct `state`/`previous_state`/`reason`.
    #[test]
    fn payload_reflects_a_clean_transition_with_no_reason() {
        let seq = EventSequencer::new();
        let payload = build_state_changed_payload(&seq, NotStarted, Starting, None);
        assert_eq!(payload.state, "STARTING");
        assert_eq!(payload.previous_state, "NOT_STARTED");
        assert_eq!(payload.reason, None);
    }

    #[test]
    fn payload_carries_reason_from_a_sidecar_error() {
        let seq = EventSequencer::new();
        let err = SidecarError::UnexpectedExit { exit_code: Some(1) };
        let payload = build_state_changed_payload(&seq, Running, Crashed, Some(&err));
        assert_eq!(payload.state, "CRASHED");
        assert_eq!(payload.previous_state, "RUNNING");
        let reason = payload.reason.expect("reason must be present for a failure transition");
        assert_eq!(reason.code, "SIDECAR_UNEXPECTED_EXIT");
        assert_eq!(reason.message, err.to_string());
    }

    // Test 2 — state event name: the canonical event name is exactly
    // `sidecar:state_changed`.
    #[test]
    fn canonical_event_name_is_exact() {
        assert_eq!(EVENT_STATE_CHANGED, "sidecar:state_changed");
    }

    // Test 3 — transition mapping: representative real transitions
    // map correctly to event payloads (architecture doc §8's table,
    // the actual frozen transition graph from `sidecar-core::state`).
    #[test]
    fn representative_real_transitions_map_correctly() {
        let seq = EventSequencer::new();

        let starting = build_state_changed_payload(&seq, NotStarted, Starting, None);
        assert_eq!((starting.previous_state.as_str(), starting.state.as_str()), ("NOT_STARTED", "STARTING"));

        let running = build_state_changed_payload(&seq, Starting, Running, None);
        assert_eq!((running.previous_state.as_str(), running.state.as_str()), ("STARTING", "RUNNING"));

        let stopping = build_state_changed_payload(&seq, Running, Stopping, None);
        assert_eq!((stopping.previous_state.as_str(), stopping.state.as_str()), ("RUNNING", "STOPPING"));

        let stopped = build_state_changed_payload(&seq, Stopping, Stopped, None);
        assert_eq!((stopped.previous_state.as_str(), stopped.state.as_str()), ("STOPPING", "STOPPED"));

        // Every one of these four transitions is a real edge in
        // `LifecycleState::can_transition_to`'s table (sidecar-core/src/state.rs).
        assert!(NotStarted.can_transition_to(Starting));
        assert!(Starting.can_transition_to(Running));
        assert!(Running.can_transition_to(Stopping));
        assert!(Stopping.can_transition_to(Stopped));
    }

    #[test]
    fn sequence_is_strictly_increasing_across_emissions() {
        let seq = EventSequencer::new();
        let p1 = build_state_changed_payload(&seq, NotStarted, Starting, None);
        let p2 = build_state_changed_payload(&seq, Starting, Running, None);
        let p3 = build_state_changed_payload(&seq, Running, Stopping, None);
        assert!(p1.sequence < p2.sequence);
        assert!(p2.sequence < p3.sequence);
    }

    #[test]
    fn generation_bumps_only_on_not_started_to_starting() {
        let seq = EventSequencer::new();
        let starting = build_state_changed_payload(&seq, NotStarted, Starting, None);
        let running = build_state_changed_payload(&seq, Starting, Running, None);
        assert_eq!(starting.generation, 1);
        assert_eq!(running.generation, 1, "generation must not bump on a non-launch transition");

        let restart_starting = build_state_changed_payload(&seq, NotStarted, Starting, None);
        assert_eq!(restart_starting.generation, 2, "a second real launch/restart bumps generation");
    }

    // --- Phase 4E-P3 Part 2B-1 additions below ---------------------
    //
    // The sequence/generation authority itself (`EventSequencer`)
    // already existed, complete, as of Part 2A (see the struct doc
    // above). Part 2B-1's own scope (task brief §6: "if an existing
    // suitable sequence authority already exists, reuse it instead of
    // creating another") is therefore satisfied by *this* type, not a
    // new one. What Part 2A's own test suite did not yet cover,
    // because it had no consumer to justify it yet, is: an explicit
    // uniqueness assertion over many allocations (as opposed to the
    // weaker "strictly increasing" pairwise check already present),
    // genuine multi-threaded concurrent allocation, and an explicit
    // "no reset across a simulated crash/restart cycle" test. Those
    // three are added here; the sequencer under test is unchanged.

    // Test 3 (task brief §22) — uniqueness: many allocations from a
    // single sequencer never repeat a value.
    #[test]
    fn many_sequential_allocations_are_all_unique() {
        let seq = EventSequencer::new();
        let mut seen = std::collections::HashSet::new();
        for _ in 0..1000 {
            let payload = build_state_changed_payload(&seq, Running, Running, None);
            assert!(
                seen.insert(payload.sequence),
                "sequence {} was allocated more than once",
                payload.sequence
            );
        }
        assert_eq!(seen.len(), 1000);
    }

    // Test 4 (task brief §22) — concurrent allocation: multiple
    // threads calling the sequencer simultaneously must each get a
    // unique value, and the resulting set must be monotonic when
    // sorted, with exactly the expected count. Uses `next_sequence`
    // directly (a private method of this module, reachable from this
    // nested `tests` submodule per ordinary Rust visibility rules) so
    // the allocation primitive itself -- not the higher-level payload
    // builder -- is what's under concurrent test.
    #[test]
    fn concurrent_allocations_are_unique_and_monotonic() {
        use std::sync::Arc;
        use std::thread;

        let seq = Arc::new(EventSequencer::new());
        let threads: usize = 8;
        let per_thread: usize = 200;

        let handles: Vec<_> = (0..threads)
            .map(|_| {
                let seq = Arc::clone(&seq);
                thread::spawn(move || {
                    (0..per_thread)
                        .map(|_| seq.next_sequence())
                        .collect::<Vec<u64>>()
                })
            })
            .collect();

        let mut all: Vec<u64> = Vec::with_capacity(threads * per_thread);
        for handle in handles {
            all.extend(handle.join().expect("allocator thread must not panic"));
        }

        // All values unique.
        let unique: std::collections::HashSet<u64> = all.iter().copied().collect();
        assert_eq!(
            unique.len(),
            threads * per_thread,
            "concurrent allocation produced a duplicate sequence value"
        );

        // Expected number of allocations.
        assert_eq!(all.len(), threads * per_thread);

        // Monotonic as a sorted set: 1..=N with no gaps, since this
        // sequencer had no other caller during the test.
        all.sort_unstable();
        let expected: Vec<u64> = (1..=(threads * per_thread) as u64).collect();
        assert_eq!(all, expected, "sequence values must form a gap-free monotonic run");
    }

    // Test 5 (task brief §22) — no reset: a simulated crash/restart
    // cycle (the same shape `attempt_restart` in `lib.rs` actually
    // drives: <terminal> -> NotStarted -> Starting -> Running, twice)
    // must never lower or reset the sequence, and `generation` must
    // advance exactly once per launch, matching architecture doc
    // §10.4 ("increments... once per real launch/restart attempt").
    // This uses the real `EventSequencer`/`build_state_changed_payload`
    // pair -- the same production code path `lib.rs` calls -- rather
    // than a fake lifecycle, per the task brief's own "use the
    // existing architecture rather than inventing a fake lifecycle
    // system" instruction.
    #[test]
    fn sequence_survives_a_simulated_crash_and_restart_cycle_without_resetting() {
        let seq = EventSequencer::new();

        // Initial launch.
        let p1 = build_state_changed_payload(&seq, NotStarted, Starting, None);
        let p2 = build_state_changed_payload(&seq, Starting, Running, None);
        assert_eq!(p1.generation, 1);
        assert_eq!(p2.generation, 1);

        // Crash.
        let err = SidecarError::UnexpectedExit { exit_code: None };
        let p3 = build_state_changed_payload(&seq, Running, Crashed, Some(&err));

        // Restart attempt 1: reset() -> NotStarted, then -> Starting -> Running.
        let p4 = build_state_changed_payload(&seq, Crashed, NotStarted, None);
        let p5 = build_state_changed_payload(&seq, NotStarted, Starting, None);
        let p6 = build_state_changed_payload(&seq, Starting, Running, None);

        // Second crash + restart, to confirm this holds across more
        // than one cycle, not just the first.
        let p7 = build_state_changed_payload(&seq, Running, Crashed, Some(&err));
        let p8 = build_state_changed_payload(&seq, Crashed, NotStarted, None);
        let p9 = build_state_changed_payload(&seq, NotStarted, Starting, None);
        let p10 = build_state_changed_payload(&seq, Starting, Running, None);

        let sequences = [
            p1.sequence, p2.sequence, p3.sequence, p4.sequence, p5.sequence,
            p6.sequence, p7.sequence, p8.sequence, p9.sequence, p10.sequence,
        ];
        for window in sequences.windows(2) {
            assert!(
                window[1] > window[0],
                "sequence must never fail to increase across a crash/restart cycle: {sequences:?}"
            );
        }
        assert_eq!(sequences.iter().copied().collect::<std::collections::HashSet<_>>().len(), 10);

        // generation: 1 for the initial launch, bumps to 2 then 3 on
        // each of the two subsequent NotStarted->Starting transitions
        // -- never reset back to 1, and never bumped by the crash or
        // reset() transitions themselves.
        assert_eq!(p1.generation, 1);
        assert_eq!(p3.generation, 1, "a crash transition must not bump generation");
        assert_eq!(p4.generation, 1, "a reset() transition must not bump generation");
        assert_eq!(p5.generation, 2, "restart's NotStarted->Starting bumps generation");
        assert_eq!(p6.generation, 2);
        assert_eq!(p9.generation, 3, "second restart's NotStarted->Starting bumps generation again");
        assert_eq!(p10.generation, 3);
    }

    // Test 6 (task brief §22) — event payload: a real, representative
    // event payload (the crash payload from the cycle above) carries
    // the allocated sequence as a plain, present field.
    #[test]
    fn event_payload_carries_the_allocated_sequence() {
        let seq = EventSequencer::new();
        let _ = build_state_changed_payload(&seq, NotStarted, Starting, None);
        let err = SidecarError::UnexpectedExit { exit_code: Some(137) };
        let crash_payload = build_state_changed_payload(&seq, Running, Crashed, Some(&err));
        assert!(crash_payload.sequence > 0);
        // Serialized form actually contains the field, not just the
        // struct -- guards against a future refactor accidentally
        // `#[serde(skip)]`-ing it.
        let serialized = serde_json::to_string(&crash_payload).expect("payload must serialize");
        assert!(serialized.contains("\"sequence\":"));
    }

    // Test 4 — forbidden data: the event representation does not
    // expose prohibited internal information.
    #[test]
    fn payload_never_exposes_forbidden_internals() {
        let seq = EventSequencer::new();
        let err = SidecarError::SpawnFailure {
            reason: "permission denied".to_string(),
        };
        let payload = build_state_changed_payload(&seq, Starting, Failed, Some(&err));
        let serialized = serde_json::to_string(&payload).expect("payload must serialize");

        for forbidden in ["pid", "PID", "command", "argv", "env", "thread", "mutex", "stack"] {
            assert!(
                !serialized.to_lowercase().contains(&forbidden.to_lowercase()),
                "payload must not mention forbidden field '{forbidden}': {serialized}"
            );
        }
    }

    #[test]
    fn timestamp_is_well_formed_rfc3339() {
        // A fixed, known Unix timestamp: 2024-01-15T00:00:00Z ==
        // 1705276800. Verifies the dependency-free formatter directly,
        // independent of the current wall clock.
        assert_eq!(format_rfc3339(1705276800), "2024-01-15T00:00:00Z");
    }

    // Test 5 — framework boundary: the domain/core layer remains free
    // of Tauri dependencies. `sidecar-core`'s own `Cargo.toml` is the
    // authoritative source for this; asserted here (rather than left
    // as a manual/structural-only check) so a future accidental
    // `tauri` dependency addition to `sidecar-core` fails this crate's
    // own test suite, not just a human re-reading the file.
    #[test]
    fn sidecar_core_cargo_toml_has_no_tauri_dependency() {
        let manifest = include_str!("../../sidecar-core/Cargo.toml");

        // Scoped to actual dependency declarations, not the whole file:
        // `sidecar-core/Cargo.toml` legitimately mentions "Tauri" in its
        // `description` field and in comments explaining *why* there is
        // no such dependency, so a whole-file substring search is a
        // false positive on that prose, not a real architecture
        // violation. Instead, isolate each dependency table's body (from
        // its `[...]` header to the next `[`-starting section or EOF)
        // and check only its non-comment lines -- i.e. the actual
        // declared dependency entries -- for a `tauri` name. This still
        // fails if a future `tauri = ...` / `tauri-plugin-... = ...`
        // line is added to any dependency table.
        let dependency_sections = ["[dependencies]", "[dev-dependencies]", "[build-dependencies]"];

        for section in dependency_sections {
            let Some(header_start) = manifest.find(section) else {
                continue;
            };
            let body_start = header_start + section.len();
            let rest = &manifest[body_start..];
            let body_end = rest.find("\n[").unwrap_or(rest.len());
            let body = &rest[..body_end];

            for line in body.lines() {
                let trimmed = line.trim();
                if trimmed.is_empty() || trimmed.starts_with('#') {
                    continue;
                }
                assert!(
                    !trimmed.to_lowercase().contains("tauri"),
                    "sidecar-core/Cargo.toml declares a tauri dependency in {section} \
                     (domain purity, architecture doc §9 item 9): {trimmed}"
                );
            }
        }
    }

    // --- Phase 4E-P3 Part 2B-2 additions below ---------------------
    //
    // Scope: previous-state integrity + event ordering. As with Part
    // 2B-1, inspection first (task brief §1/§2): every existing
    // `lib.rs` call site already reads `previous`/`current` as owned,
    // `Copy` `LifecycleState` values from the real transition under
    // `state.process`'s mutex, drops the lock, and only then builds
    // the payload -- there is no code path where `previous_state`/
    // `state` are inferred from poll history, timestamps, or cached
    // assumptions (task brief §6), and no code path where the payload
    // retains a reference to mutable lifecycle state (task brief §10).
    // This was true since Part 2A and is unchanged. What was not yet
    // covered by an explicit test is: (a) that a real invalid
    // transition, attempted directly against the frozen FSM, never
    // reaches a valid event, and (b) that an already-built payload is
    // provably unaffected by later mutation of the `Lifecycle` it was
    // built from. Both are added here.

    // Test 5 (task brief §20) — immutable payload: build a payload
    // from a real transition, then continue mutating the same
    // `Lifecycle` well past that point, and confirm the already-built
    // payload's fields never change. This exercises the actual
    // `sidecar_core::Lifecycle` FSM (not a fake), matching the task
    // brief's preference for using the existing architecture over an
    // invented one.
    #[test]
    fn already_built_payload_is_unaffected_by_later_lifecycle_mutation() {
        use sidecar_core::Lifecycle;

        let seq = EventSequencer::new();
        let mut lifecycle = Lifecycle::new(); // NotStarted

        let previous = lifecycle.state();
        let current = lifecycle
            .transition(Starting)
            .expect("NotStarted -> Starting is a real, legal transition");
        let payload = build_state_changed_payload(&seq, previous, current, None);

        // Snapshot the payload's fields for comparison.
        let snapshot = payload.clone();

        // Continue driving the *same* Lifecycle well past the point
        // the payload above was built -- Starting -> Running ->
        // Stopping -> Stopped -> NotStarted -> Starting again.
        lifecycle.transition(Running).unwrap();
        lifecycle.transition(Stopping).unwrap();
        lifecycle.transition(Stopped).unwrap();
        lifecycle.transition(NotStarted).unwrap();
        lifecycle.transition(Starting).unwrap();

        // The already-built payload is a historical fact: none of the
        // above can reach back and change it, because it was built
        // from owned `Copy` values and an owned `String`/`Option`
        // payload, never a reference into `lifecycle`.
        assert_eq!(payload, snapshot);
        assert_eq!(payload.state, "STARTING");
        assert_eq!(payload.previous_state, "NOT_STARTED");
        // The live lifecycle has moved on; the payload has not.
        assert_eq!(lifecycle.state(), Starting);
        assert_ne!(
            lifecycle.state().to_string(),
            payload.previous_state,
            "sanity check: the live lifecycle's current state must differ from the frozen payload's previous_state at this point in the test"
        );
    }

    // Test 6 (task brief §20) — invalid transition: an invalid
    // transition, attempted against the real, frozen FSM, is rejected
    // by the FSM itself (unchanged, not modified to make this test
    // pass, per the task brief's explicit instruction) and therefore
    // never produces `previous`/`current` values a caller could use to
    // build a valid `state_changed` event. This is asserted two ways:
    // the FSM's own rejection, and confirmation that no legal
    // representative transition list this module tests (§ above)
    // includes it.
    #[test]
    fn invalid_transition_is_rejected_by_the_fsm_and_never_reaches_an_event() {
        use sidecar_core::Lifecycle;

        let mut lifecycle = Lifecycle::new(); // NotStarted
        let before = lifecycle.state();

        // NotStarted -> Running is not a legal single-step transition
        // (sidecar-core/src/state.rs's own can_transition_to table);
        // only NotStarted -> Starting is.
        assert!(!before.can_transition_to(Running));
        let result = lifecycle.transition(Running);
        assert!(result.is_err(), "an invalid transition must be rejected, not silently coerced");

        // The FSM's own state is unchanged after a rejected attempt --
        // there is therefore no new `current` value for a caller to
        // (mis)report as a real transition.
        assert_eq!(lifecycle.state(), before);

        // The two transitions the task brief's own illustrative list
        // names that are NOT legal single-step edges in this frozen
        // FSM (`STOPPED -> STARTING`, `CRASHED -> STARTING` -- both
        // actually require an intermediate `-> NotStarted` step first,
        // per `can_transition_to`) are confirmed rejected the same
        // way, rather than silently tested as if they were legal:
        assert!(!Stopped.can_transition_to(Starting));
        assert!(!Crashed.can_transition_to(Starting));
        // Their real two-step equivalents, which `lib.rs` actually
        // performs and which this module's other tests already
        // exercise, remain legal:
        assert!(Stopped.can_transition_to(NotStarted));
        assert!(Crashed.can_transition_to(NotStarted));
        assert!(NotStarted.can_transition_to(Starting));
    }

    // Test 2 (task brief §20) extended — every transition
    // `lib.rs`'s real call sites actually drive, checked directly
    // against the frozen FSM's own `can_transition_to`, with a
    // `state_changed` payload built for each and its
    // `previous_state`/`state` pair asserted to match exactly. This
    // supersedes relying solely on the task brief's own illustrative
    // list (which names two edges, noted above, that are not legal
    // single steps in this FSM) by testing what the FSM and `lib.rs`
    // actually do.
    #[test]
    fn every_real_lib_rs_transition_is_legal_and_produces_a_matching_payload() {
        let seq = EventSequencer::new();
        let real_transitions: &[(LifecycleState, LifecycleState)] = &[
            (NotStarted, Starting),   // initial launch / restart, first step
            (Starting, Running),      // successful launch
            (Starting, Failed),       // startup failure
            (Starting, Timeout),      // startup handshake timeout
            (Running, Stopping),      // intentional shutdown, first step
            (Running, Crashed),       // runtime crash (poll_for_crash)
            (Stopping, Stopped),      // clean shutdown
            (Stopping, Failed),       // shutdown timeout
            (Stopped, NotStarted),    // not driven by lib.rs today, but a legal recovery edge
            (Failed, NotStarted),     // attempt_restart's reset()
            (Timeout, NotStarted),    // attempt_restart's reset()
            (Crashed, NotStarted),    // attempt_restart's reset()
        ];

        for &(previous, current) in real_transitions {
            assert!(
                previous.can_transition_to(current),
                "{previous:?} -> {current:?} must be a real edge in the frozen FSM"
            );
            let payload = build_state_changed_payload(&seq, previous, current, None);
            assert_eq!(payload.previous_state, previous.to_string());
            assert_eq!(payload.state, current.to_string());
        }
    }

    // -----------------------------------------------------------------
    // Phase 4E-P3 Part 2C — restart_scheduled / restart_exhausted /
    // status-snapshot-sequence tests
    // -----------------------------------------------------------------
    //
    // `emit_restart_scheduled`/`emit_restart_exhausted` themselves
    // require a real `tauri::AppHandle`, same limitation noted at the
    // top of this file for `emit_state_changed` -- so, matching that
    // existing precedent exactly, what is tested directly here is the
    // pure payload-construction layer underneath them
    // (`build_restart_scheduled_payload`/`build_restart_exhausted_payload`),
    // which is where every actual field-correctness guarantee lives.

    use std::time::Duration;

    // Test 33 (task brief) — accepted-schedule payload: correct
    // attempt, correct accepted delay (never independently
    // recalculated), a real sequence value, and the exact event name.
    #[test]
    fn restart_scheduled_payload_reflects_the_accepted_attempt_and_delay() {
        let seq = EventSequencer::new();
        let payload = build_restart_scheduled_payload(&seq, 3, Duration::from_millis(4000));
        assert_eq!(payload.attempt, 3);
        assert_eq!(payload.delay_ms, 4000);
        assert_eq!(payload.sequence, 1);
        assert_eq!(EVENT_RESTART_SCHEDULED, "sidecar:restart_scheduled");
    }

    // Test 33/37 — immutable payload: `RestartScheduledPayload` is
    // built from owned `Copy` values (`u32`/`Duration`) and an owned
    // `String` timestamp -- there is no reference into
    // `RestartScheduler`/`RestartSchedule` for a later mutation to
    // reach back through. Verified the same way Test 5 (above) verifies
    // it for `StateChangedPayload`: snapshot immediately after
    // construction, confirm equality.
    #[test]
    fn restart_scheduled_payload_is_owned_and_stable_once_built() {
        let seq = EventSequencer::new();
        let payload = build_restart_scheduled_payload(&seq, 1, Duration::from_secs(1));
        let snapshot = payload.clone();
        // Continue allocating more sequence values from the same
        // sequencer -- the already-built payload above must not change.
        let _ = seq.next_sequence();
        let _ = seq.next_sequence();
        assert_eq!(payload, snapshot);
    }

    // Test 35 — exhaustion payload: correct `attempts`, the reused
    // `SidecarError::RestartExhausted` code (no second error-code
    // vocabulary), and a real sequence value.
    #[test]
    fn restart_exhausted_payload_reflects_the_final_attempt_count() {
        let seq = EventSequencer::new();
        let payload = build_restart_exhausted_payload(&seq, 5);
        assert_eq!(payload.attempts, 5);
        assert_eq!(payload.code, "SIDECAR_RESTART_EXHAUSTED");
        assert_eq!(payload.sequence, 1);
        assert_eq!(EVENT_RESTART_EXHAUSTED, "sidecar:restart_exhausted");
    }

    // Test 37 — sequence: unique, strictly increasing across every
    // mixed event kind this checkpoint adds, none of them resetting or
    // reusing a value the others already allocated.
    #[test]
    fn sequence_is_unique_and_strictly_increasing_across_every_event_kind() {
        let seq = EventSequencer::new();

        let state_changed =
            build_state_changed_payload(&seq, LifecycleState::Running, LifecycleState::Crashed, None);
        let scheduled = build_restart_scheduled_payload(&seq, 1, Duration::from_secs(1));
        let state_changed_2 = build_state_changed_payload(
            &seq,
            LifecycleState::NotStarted,
            LifecycleState::Starting,
            None,
        );
        let exhausted = build_restart_exhausted_payload(&seq, 5);

        let sequences = [
            state_changed.sequence,
            scheduled.sequence,
            state_changed_2.sequence,
            exhausted.sequence,
        ];
        assert_eq!(sequences, [1, 2, 3, 4]);

        let mut seen = std::collections::HashSet::new();
        for &s in &sequences {
            assert!(seen.insert(s), "sequence {s} was allocated more than once");
        }
        for pair in sequences.windows(2) {
            assert!(
                pair[1] > pair[0],
                "sequence must strictly increase: {} then {}",
                pair[0],
                pair[1]
            );
        }
    }

    // Test 26/39 — `EventSequencer::current_sequence` (the one
    // `get_sidecar_status` is allowed to call) never itself allocates:
    // calling it any number of times returns the same value, and it
    // only ever changes when `next_sequence` is separately called by
    // real event construction.
    #[test]
    fn current_sequence_never_allocates_and_only_reflects_real_emissions() {
        let seq = EventSequencer::new();
        assert_eq!(seq.current_sequence(), 0, "no event emitted yet");
        assert_eq!(seq.current_sequence(), 0, "a second read must not allocate");

        let payload = build_state_changed_payload(
            &seq,
            LifecycleState::NotStarted,
            LifecycleState::Starting,
            None,
        );
        assert_eq!(payload.sequence, 1);
        assert_eq!(seq.current_sequence(), 1);
        assert_eq!(seq.current_sequence(), 1, "reading again must not allocate");
    }
}
