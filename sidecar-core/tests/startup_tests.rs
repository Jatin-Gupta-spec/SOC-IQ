//! Startup tests.
//!
//! Part 1 minimum coverage (task brief §11 "Startup"): valid startup
//! information, malformed startup information, invalid startup
//! information, startup timeout, handshake success, handshake failure.
//!
//! Part 2 adversarial coverage (task brief §5): empty payload,
//! malformed payload, missing field, wrong field type, invalid port,
//! unexpected values, duplicate/repeated readiness information,
//! handshake rejection, handshake after timeout, handshake after
//! shutdown.
//!
//! **Part 2B note:** every literal handshake line in this file was
//! rewritten from the old `SOCIQ_SIDECAR_PORT=<port>` format to the
//! real sidecar's actual bare-decimal-port format (see
//! `src/startup.rs`'s module doc). The coverage matrix itself — which
//! cases are tested — is unchanged from Part 2; only the wire format
//! each case exercises was corrected. `handshake_prefix_constant_...`
//! is removed because there is no longer a prefix constant to test.
//!
//! Note on "invalid address" (task brief §5): `StartupInfo` has only a
//! `port` field — the contract (§2) names the port as the only
//! required startup field ("the bound loopback port"); the loopback
//! address itself (`127.0.0.1`) is a fixed security invariant
//! (`docs/security/ipc-security-model.md`), not something the
//! handshake transmits. There is no address field to adversarially
//! test without inventing one, which would be scope creep beyond what
//! Part 1 defined — this is a reviewed non-finding, not a gap.

use sidecar_core::{parse_handshake_line, SidecarError, StartupInfo};
use std::time::Duration;

#[test]
fn valid_handshake_line_parses_to_startup_info() {
    let info = parse_handshake_line("54321").unwrap();
    assert_eq!(info, StartupInfo { port: 54321 });
}

#[test]
fn valid_handshake_line_tolerates_trailing_newline() {
    let info = parse_handshake_line("8080\n").unwrap();
    assert_eq!(info, StartupInfo { port: 8080 });
}

#[test]
fn valid_handshake_line_tolerates_leading_and_trailing_whitespace() {
    // Real subprocess stdout lines can carry surrounding whitespace
    // depending on how the caller reads them; the real Python
    // entrypoint's own print() adds only a trailing '\n', but the
    // parser tolerates whitespace on either side to avoid being
    // brittle to how a given adapter reads lines.
    let info = parse_handshake_line("  9999  \n").unwrap();
    assert_eq!(info, StartupInfo { port: 9999 });
}

#[test]
fn malformed_startup_output_non_numeric_prefix_is_handshake_failure() {
    // A line carrying the OLD Part 1 wire format is now itself a
    // malformed-input case, since it is not a bare integer.
    let result = parse_handshake_line("SOCIQ_SIDECAR_PORT=54321");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn malformed_startup_output_arbitrary_text_is_handshake_failure() {
    let result = parse_handshake_line("READY 54321");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn malformed_startup_output_empty_line_is_handshake_failure() {
    let result = parse_handshake_line("");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn malformed_startup_output_whitespace_only_is_handshake_failure() {
    let result = parse_handshake_line("   ");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn malformed_startup_output_non_numeric_is_handshake_failure() {
    let result = parse_handshake_line("not-a-port");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn invalid_startup_output_zero_port_is_distinct_from_handshake_failure() {
    // Parses fine as an integer, but zero is not a valid bound port —
    // contract §3 distinguishes this as InvalidStartupOutput, not a
    // generic HandshakeFailure.
    let result = parse_handshake_line("0");
    assert!(matches!(
        result,
        Err(SidecarError::InvalidStartupOutput { .. })
    ));
}

#[test]
fn invalid_startup_output_out_of_range_port() {
    let result = parse_handshake_line("99999999");
    assert!(matches!(
        result,
        Err(SidecarError::InvalidStartupOutput { .. })
    ));
}

#[test]
fn handshake_success_drives_supervisor_from_starting_to_running() {
    use sidecar_core::{LifecycleState, Supervisor};

    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    let info = supervisor.validate_handshake("12345").unwrap();
    assert_eq!(info.port, 12345);
    // Handshake validation alone does not change state (contract §2).
    assert_eq!(supervisor.state(), LifecycleState::Starting);
    supervisor.health_check_succeeded().unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Running);
}

#[test]
fn handshake_failure_drives_supervisor_to_timeout_state() {
    use sidecar_core::{LifecycleState, Supervisor};

    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    let err = supervisor.validate_handshake("garbage").unwrap_err();
    let result = supervisor.handshake_failed(err);
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
    assert_eq!(supervisor.state(), LifecycleState::Timeout);
}

#[test]
fn startup_timeout_carries_elapsed_and_limit() {
    use sidecar_core::{LifecycleState, Supervisor, TimeoutConfig};

    let mut supervisor = Supervisor::new(TimeoutConfig::new(
        Duration::from_secs(10),
        Duration::from_secs(5),
    ));
    supervisor.request_start().unwrap();
    let err = supervisor
        .startup_timed_out(Duration::from_secs(11))
        .unwrap_err();
    match err {
        SidecarError::StartupTimeout {
            elapsed_ms,
            limit_ms,
        } => {
            assert_eq!(elapsed_ms, 11_000);
            assert_eq!(limit_ms, 10_000);
        }
        other => panic!("expected StartupTimeout, got {other:?}"),
    }
    assert_eq!(supervisor.state(), LifecycleState::Timeout);
}

#[test]
fn startup_timeout_boundary_elapsed_equals_limit_exactly() {
    // Part 2 §6 boundary case: elapsed == limit exactly.
    use sidecar_core::{Supervisor, TimeoutConfig};
    let mut supervisor = Supervisor::new(TimeoutConfig::new(
        Duration::from_secs(10),
        Duration::from_secs(5),
    ));
    supervisor.request_start().unwrap();
    let err = supervisor
        .startup_timed_out(Duration::from_secs(10))
        .unwrap_err();
    assert_eq!(
        err,
        SidecarError::StartupTimeout {
            elapsed_ms: 10_000,
            limit_ms: 10_000,
        }
    );
}

#[test]
fn startup_timeout_boundary_immediate_zero_elapsed() {
    // Part 2 §6 boundary case: "immediate timeout" (elapsed == 0).
    // sidecar-core owns no clock (see supervisor.rs's Part 2 review
    // note), so it records exactly what the caller asserts, including
    // this degenerate case, deterministically.
    use sidecar_core::{Supervisor, TimeoutConfig};
    let mut supervisor = Supervisor::new(TimeoutConfig::new(
        Duration::from_secs(10),
        Duration::from_secs(5),
    ));
    supervisor.request_start().unwrap();
    let err = supervisor
        .startup_timed_out(Duration::from_secs(0))
        .unwrap_err();
    assert_eq!(
        err,
        SidecarError::StartupTimeout {
            elapsed_ms: 0,
            limit_ms: 10_000,
        }
    );
}

#[test]
fn startup_timeout_boundary_already_expired_far_past_limit() {
    // Part 2 §6 boundary case: "already-expired timeout" (elapsed far
    // exceeds limit).
    use sidecar_core::{Supervisor, TimeoutConfig};
    let mut supervisor = Supervisor::new(TimeoutConfig::new(
        Duration::from_secs(10),
        Duration::from_secs(5),
    ));
    supervisor.request_start().unwrap();
    let err = supervisor
        .startup_timed_out(Duration::from_secs(3_600))
        .unwrap_err();
    assert_eq!(
        err,
        SidecarError::StartupTimeout {
            elapsed_ms: 3_600_000,
            limit_ms: 10_000,
        }
    );
}

#[test]
fn negative_looking_port_value_is_a_handshake_failure_not_a_panic() {
    // Part 2 §5 "unexpected values": a leading '-' is not a valid u32,
    // so it fails at the same parse step as any other non-numeric
    // value — not a special-cased panic or silent acceptance.
    let result = parse_handshake_line("-1");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn decimal_looking_port_value_is_a_handshake_failure() {
    // Part 2B addition: a float-shaped value must not be silently
    // truncated to an integer.
    let result = parse_handshake_line("8080.5");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn extra_trailing_garbage_after_port_is_a_handshake_failure() {
    // Part 2 §5 "unexpected values": trailing garbage must not be
    // silently truncated/ignored — the whole value must parse cleanly.
    let result = parse_handshake_line("8080extra");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn multiple_lines_in_one_string_is_a_handshake_failure() {
    // Part 2B addition: parse_handshake_line takes one already-split
    // line; if a caller accidentally hands it unsplit multi-line input,
    // it must fail rather than parse only the first token.
    let result = parse_handshake_line("8080\n9090");
    assert!(matches!(result, Err(SidecarError::HandshakeFailure { .. })));
}

#[test]
fn repeated_handshake_parsing_is_pure_and_deterministic() {
    // Part 2 §5 "duplicate readiness information" / "repeated
    // handshake": parse_handshake_line has no side effects and no
    // internal state, so calling it many times on the same or
    // different lines is always deterministic and never mutates
    // anything hidden.
    for _ in 0..5 {
        assert_eq!(
            parse_handshake_line("4242").unwrap(),
            StartupInfo { port: 4242 }
        );
    }
    // A different line afterward is unaffected by the prior calls.
    assert!(parse_handshake_line("garbage").is_err());
    assert_eq!(
        parse_handshake_line("4242").unwrap(),
        StartupInfo { port: 4242 }
    );
}

#[test]
fn handshake_after_startup_timeout_cannot_transition_state_again() {
    // Part 2 §5 "handshake after timeout": once STARTING -> TIMEOUT has
    // already happened, a late-arriving handshake result must not be
    // able to silently move the state again (TIMEOUT -> TIMEOUT is not
    // a valid transition; TIMEOUT -> RUNNING isn't either).
    use sidecar_core::{LifecycleState, Supervisor};
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor
        .startup_timed_out(Duration::from_secs(99))
        .ok();
    assert_eq!(supervisor.state(), LifecycleState::Timeout);

    // A late "handshake failed" observation arriving after the timeout
    // already fired must be rejected as an invalid transition, not
    // silently re-applied.
    let bad = parse_handshake_line("garbage").unwrap_err();
    let result = supervisor.handshake_failed(bad);
    assert!(matches!(
        result,
        Err(SidecarError::InvalidTransition {
            from: LifecycleState::Timeout,
            to: LifecycleState::Timeout,
        })
    ));
    assert_eq!(supervisor.state(), LifecycleState::Timeout);

    // Nor can a late-arriving success move it to RUNNING.
    assert!(supervisor.health_check_succeeded().is_err());
    assert_eq!(supervisor.state(), LifecycleState::Timeout);
}

#[test]
fn handshake_after_shutdown_cannot_transition_state_again() {
    // Part 2 §5 "handshake after shutdown": a handshake-related event
    // arriving after the sidecar has already fully stopped must not
    // resurrect it.
    use sidecar_core::{ExitStatus, LifecycleState, Supervisor};
    let mut supervisor = Supervisor::default();
    supervisor.request_start().unwrap();
    supervisor.health_check_succeeded().unwrap();
    supervisor.request_shutdown().unwrap();
    supervisor.process_exited(ExitStatus::with_code(0)).unwrap();
    assert_eq!(supervisor.state(), LifecycleState::Stopped);

    assert!(supervisor.health_check_succeeded().is_err());
    assert_eq!(supervisor.state(), LifecycleState::Stopped);
}
