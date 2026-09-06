//! `sidecar-core` — framework-independent sidecar lifecycle core.
//!
//! # Scope (Phase 2A, Parts 1 and 2 — hardening, no new features)
//!
//! This crate implements the lifecycle state machine, typed error
//! model, startup/handshake contract, timeout configuration, shutdown
//! semantics, and a minimal supervisor abstraction defined by
//! `docs/phase4/PHASE4_PRE_2A_CONTRACT.md`. Part 2 is an adversarial
//! hardening pass over Part 1's architecture — no new capability was
//! added; see `docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md` for the
//! full implemented-vs-deferred breakdown and its Part 2 hardening
//! addendum.
//!
//! **Part 2B note:** the handshake wire format `parse_handshake_line`
//! accepts was corrected to match the real Python sidecar's actual
//! stdout output (a bare decimal port, not a `SOCIQ_SIDECAR_PORT=`
//! prefixed line) — see `startup.rs`'s module doc for the full
//! rationale. This is the one Part 2A surface Part 2B was required to
//! touch; everything else in this crate (state machine, supervisor,
//! error model, timeouts) is unchanged from the Part 2 hardening
//! freeze.
//!
//! **Phase 4E-P2 Part 2B-1 note:** added the [`restart`] module
//! (`RestartPolicy`/`RestartTracker`) per
//! `docs/phase4/PHASE4E_P2_SIDECAR_CRASH_RESTART_ARCHITECTURE.md` §7 —
//! restart *decision/accounting* only, still no real timing, no real
//! process control, and no automatic restart wired to anything (see
//! that module's own doc for the exact scope boundary). No other
//! module in this crate was changed by Part 2B-1.
//!
//! **Phase 4E-P2 Part 2B-2 note:** added [`RestartSchedule`]/
//! [`RestartToken`] to the same [`restart`] module — pure "at most one
//! pending restart" bookkeeping (task brief §6/§9/§15/§16/§17/§19/§21),
//! still no real timer/clock/I-O. The *real* timer lives in
//! `src-tauri`'s `RestartScheduler`, a new adapter type that composes
//! this bookkeeping with an actual background-thread sleep — this
//! crate's hard architectural boundary (below) is unchanged. No other
//! module in this crate was changed by Part 2B-2.
//!
//! **Phase 4E-P2 Part 2B-3 note:** added the `SIDECAR_RESTART_EXHAUSTED`
//! error variant (`SidecarError::RestartExhausted`, §11) and
//! [`StabilityWindow`]/[`StabilityToken`] to the same [`restart`]
//! module — the `reset_after_stable` stability-check bookkeeping Part
//! 2B-2 explicitly deferred. Still no real clock/timer/I-O in this
//! crate; the real stability timer lives in `src-tauri`'s new
//! `StabilityScheduler`, composing this bookkeeping with the same
//! `DelayRunner` abstraction `RestartScheduler` already uses.
//! `state.rs`'s transition table is unchanged — restart exhaustion
//! leaves the `Lifecycle` in whichever terminal state it was already in
//! (`Crashed`/`Failed`/`Timeout`); "FAILED" as used elsewhere for this
//! outcome is the *synthesized* external status (architecture doc
//! §5/§6.5/§12), not a new core-FSM transition — see
//! `docs/phase4/PHASE4E_P2_PART2B3_IMPLEMENTATION.md` §0 for the
//! discrepancy this resolves against the task brief's own illustrative
//! diagram.
//!
//! # Hard architectural boundary
//!
//! This crate has **no Tauri dependency** and performs **no real
//! process spawning, no real I/O, and no real timing**. The dependency
//! direction is:
//!
//! ```text
//! sidecar-core
//!     -> abstract process/supervisor contracts (this crate)
//!     -> future Tauri/native adapter (a later phase, depends on this
//!        crate — never the reverse)
//! ```
//!
//! Every observation the [`supervisor::Supervisor`] reacts to (spawn
//! failed, handshake line received, health check result, process
//! exited, timeout elapsed) is supplied explicitly by the caller. A
//! later phase's real adapter supplies real observations; this crate's
//! own tests supply literal/fake ones. Nothing in this crate blocks,
//! sleeps, or spawns anything.

pub mod error;
pub mod process;
pub mod restart;
pub mod startup;
pub mod state;
pub mod supervisor;
pub mod timeout;

pub use error::SidecarError;
pub use process::ExitStatus;
pub use restart::{
    RestartDecision, RestartPolicy, RestartSchedule, RestartToken, RestartTracker,
    StabilityToken, StabilityWindow,
};
pub use startup::{parse_handshake_line, StartupInfo};
pub use state::{Lifecycle, LifecycleState};
pub use supervisor::{ShutdownOutcome, Supervisor};
pub use timeout::TimeoutConfig;
