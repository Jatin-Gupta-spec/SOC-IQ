//! Minimal process abstraction.
//!
//! Part 1 does not spawn, poll, or kill an operating-system process
//! (task brief §3/§6) — the supervisor is driven entirely by explicit
//! event methods (see [`crate::supervisor::Supervisor`]) representing
//! observations a real process adapter would make. The one thing worth
//! naming at this layer is the shape of "how a process exited", since
//! both the normal-shutdown path and the crash path need to carry it —
//! this is that shape, and nothing more.

/// How a supervised process exited, as reported by whatever observed it
/// (a real OS wait-call in a later phase; a literal value in a test
/// today). Deliberately narrow: no OS-specific signal/status types, no
/// process handle, no way to spawn or kill anything — those belong to
/// the Part 2 native/Tauri adapter (task brief §2's dependency
/// direction: sidecar-core has no reverse dependency on that adapter).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct ExitStatus {
    /// The process's exit code, where known. `None` covers cases such
    /// as termination by signal, where no ordinary exit code exists.
    pub code: Option<i32>,
}

impl ExitStatus {
    pub fn with_code(code: i32) -> Self {
        Self { code: Some(code) }
    }

    pub fn unknown() -> Self {
        Self { code: None }
    }
}
