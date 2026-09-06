//! Startup / handshake contract.
//!
//! Represents and validates the synchronous startup handshake described
//! by `docs/phase4/PHASE4_PRE_2A_CONTRACT.md` §2 ("print-then-flush on
//! the child's stdout, read by the parent before polling begins").
//! Part 1 implemented only the CORE representation and pure validation
//! logic — it never read a real child process's stdout (task brief §6);
//! all inputs here are plain `&str` supplied by the caller (a real
//! stdout line from Part 2B's adapter, a literal in a unit test today).
//!
//! **Part 2B compatibility fix:** Part 1's `parse_handshake_line`
//! expected a `SOCIQ_SIDECAR_PORT=<port>` prefixed line. That literal
//! was Part 1's own invented wire format, documented at the time as
//! "this exact literal is Part 1's own implementation decision" — never
//! cross-checked against the actual Python sidecar. Part 2B's
//! adversarial inspection (task brief §1 "verify the current tree
//! really corresponds to the frozen checkpoint" / §12 "contract
//! violations") found the already-frozen, already-tested Python
//! entrypoint (`app/api/entrypoint.py`, verified by
//! `tests/test_sidecar_entrypoint.py`'s real-subprocess integration
//! test) does not emit that format at all — it does
//! `print(bound_port, flush=True)`, i.e. a bare decimal integer with no
//! prefix. Wiring a real adapter to the old parser would therefore
//! never succeed against the real process it must supervise. This is
//! exactly the "minimal compatibility change" the Part 2B task brief
//! anticipates as unavoidable: the parser is corrected to match the
//! real, already-shipped Python contract (the side with an actual
//! running process and a real integration test) rather than the Rust
//! side's un-cross-checked invention. No lifecycle/state-machine/
//! error-model behavior changes — only the wire format
//! `parse_handshake_line` accepts.

use crate::error::SidecarError;

/// Startup information the supervisor needs before it can consider the
/// sidecar reachable: the bound loopback port (contract §2). Only the
/// port is required at Part 1 — the contract does not name any other
/// required startup field, and Part 1 does not invent one.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct StartupInfo {
    pub port: u16,
}

/// Parse and validate one line of handshake output.
///
/// The real sidecar (`app/api/entrypoint.py`) writes exactly one line
/// to stdout before serving: the bound port as a bare decimal integer
/// (`print(bound_port, flush=True)`), with no prefix or other tokens.
/// This parser accepts that format, tolerating surrounding whitespace
/// (a trailing `\n` in particular, since callers read a line at a
/// time).
///
/// - A line that is not a bare, cleanly-parseable integer at all is
///   unparseable -> [`SidecarError::HandshakeFailure`], per contract
///   §2's "malformed startup output" case ("the supervisor treats this
///   as StartupTimeout/HandshakeFailure rather than guessing a port or
///   retrying indefinitely").
/// - A line that parses as an integer but carries an out-of-range value
///   is the more specific case the contract's error table (§3)
///   distinguishes -> [`SidecarError::InvalidStartupOutput`].
pub fn parse_handshake_line(line: &str) -> Result<StartupInfo, SidecarError> {
    let trimmed = line.trim();

    if trimmed.is_empty() {
        return Err(SidecarError::HandshakeFailure {
            detail: "handshake line is empty".to_string(),
        });
    }

    let parsed: u32 = trimmed.parse().map_err(|_| SidecarError::HandshakeFailure {
        detail: format!("handshake line is not a bare decimal port number: {trimmed:?}"),
    })?;

    // Port 0 means "any/unspecified" at the OS level, never a real
    // bound port a handshake could legitimately announce, so it is
    // treated as an out-of-range value here, not a valid port.
    if parsed == 0 || parsed > u16::MAX as u32 {
        return Err(SidecarError::InvalidStartupOutput {
            detail: format!("port {parsed} is outside the valid 1-65535 range"),
        });
    }

    Ok(StartupInfo {
        port: parsed as u16,
    })
}
