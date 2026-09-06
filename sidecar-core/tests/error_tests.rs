//! Error tests.
//!
//! Part 1 minimum coverage (task brief §11 "Errors"): typed errors,
//! error context, deterministic behavior.
//!
//! Part 2 adversarial coverage (task brief §8 "Error model
//! hardening"): confirms `SidecarError` implements the standard
//! `std::error::Error` trait (so it composes with ordinary Rust error
//! handling), and that structurally similar variants (e.g.
//! `StartupTimeout` and `ShutdownFailure` both carry
//! `{ elapsed_ms, limit_ms }`) remain distinguishable by type rather
//! than collapsing into one generic "timeout" shape. The `unwrap()`/
//! `expect()`/`panic!()` audit itself (task brief §8) is a static
//! grep-based review documented in
//! `docs/phase4/PHASE4_2A_PART1_SIDECAR_CORE.md` rather than a runtime
//! test — zero occurrences were found in `sidecar-core/src/`.

use sidecar_core::{LifecycleState, SidecarError};

#[test]
fn every_contract_category_has_a_stable_code() {
    // Contract §3's exact category list, plus InvalidTransition for the
    // state machine itself.
    let cases: Vec<(SidecarError, &str)> = vec![
        (
            SidecarError::InvalidTransition {
                from: LifecycleState::NotStarted,
                to: LifecycleState::Running,
            },
            "SIDECAR_INVALID_TRANSITION",
        ),
        (
            SidecarError::SpawnFailure {
                reason: "x".into(),
            },
            "SIDECAR_SPAWN_FAILURE",
        ),
        (
            SidecarError::StartupTimeout {
                elapsed_ms: 1,
                limit_ms: 1,
            },
            "SIDECAR_STARTUP_TIMEOUT",
        ),
        (
            SidecarError::HandshakeFailure { detail: "x".into() },
            "SIDECAR_HANDSHAKE_FAILURE",
        ),
        (
            SidecarError::HealthCheckFailure { detail: "x".into() },
            "SIDECAR_HEALTH_CHECK_FAILURE",
        ),
        (
            SidecarError::UnexpectedExit { exit_code: None },
            "SIDECAR_UNEXPECTED_EXIT",
        ),
        (
            SidecarError::ShutdownFailure {
                elapsed_ms: 1,
                limit_ms: 1,
            },
            "SIDECAR_SHUTDOWN_FAILURE",
        ),
        (
            SidecarError::InvalidStartupOutput { detail: "x".into() },
            "SIDECAR_INVALID_STARTUP_OUTPUT",
        ),
        (
            SidecarError::RestartExhausted { attempts: 5 },
            "SIDECAR_RESTART_EXHAUSTED",
        ),
    ];

    for (err, expected_code) in cases {
        assert_eq!(err.code(), expected_code);
    }
}

#[test]
fn errors_carry_useful_context_in_their_message() {
    let err = SidecarError::SpawnFailure {
        reason: "permission denied".to_string(),
    };
    assert!(err.to_string().contains("permission denied"));

    let err = SidecarError::InvalidTransition {
        from: LifecycleState::Running,
        to: LifecycleState::NotStarted,
    };
    let message = err.to_string();
    assert!(message.contains("RUNNING"));
    assert!(message.contains("NOT_STARTED"));
}

#[test]
fn restart_exhausted_carries_the_final_attempt_count_in_its_message() {
    let err = SidecarError::RestartExhausted { attempts: 5 };
    assert!(err.to_string().contains('5'));
}

#[test]
fn same_inputs_produce_equal_errors_deterministically() {
    let a = SidecarError::HandshakeFailure {
        detail: "bad line".to_string(),
    };
    let b = SidecarError::HandshakeFailure {
        detail: "bad line".to_string(),
    };
    assert_eq!(a, b);

    let c = SidecarError::HandshakeFailure {
        detail: "different".to_string(),
    };
    assert_ne!(a, c);
}

#[test]
fn error_variants_are_distinguishable_by_matching() {
    let errors = vec![
        SidecarError::SpawnFailure {
            reason: "r".into(),
        },
        SidecarError::HandshakeFailure { detail: "d".into() },
        SidecarError::InvalidStartupOutput { detail: "d".into() },
    ];
    let mut spawn_count = 0;
    let mut handshake_count = 0;
    let mut invalid_output_count = 0;
    for err in &errors {
        match err {
            SidecarError::SpawnFailure { .. } => spawn_count += 1,
            SidecarError::HandshakeFailure { .. } => handshake_count += 1,
            SidecarError::InvalidStartupOutput { .. } => invalid_output_count += 1,
            _ => {}
        }
    }
    assert_eq!(spawn_count, 1);
    assert_eq!(handshake_count, 1);
    assert_eq!(invalid_output_count, 1);
}

#[test]
fn sidecar_error_implements_the_standard_error_trait() {
    // Part 2 §8: errors must compose with ordinary Rust error handling
    // (e.g. `Box<dyn std::error::Error>`), not just be a bag of data.
    fn assert_is_std_error<E: std::error::Error>(_: &E) {}
    let err = SidecarError::SpawnFailure {
        reason: "x".into(),
    };
    assert_is_std_error(&err);

    let boxed: Box<dyn std::error::Error> = Box::new(err);
    assert!(!boxed.to_string().is_empty());
}

#[test]
fn structurally_similar_variants_stay_distinguishable_by_type() {
    // Part 2 §8: StartupTimeout and ShutdownFailure both carry the
    // same field shape ({ elapsed_ms, limit_ms }) — confirm they are
    // still distinct variants a caller can match on, not collapsed
    // into one generic "timeout" error that would make "callers
    // reliably distinguish timeout vs failure vs invalid state"
    // (task brief §8) impossible.
    let startup = SidecarError::StartupTimeout {
        elapsed_ms: 1_000,
        limit_ms: 1_000,
    };
    let shutdown = SidecarError::ShutdownFailure {
        elapsed_ms: 1_000,
        limit_ms: 1_000,
    };
    // Identical field values, still not equal — different variants.
    assert_ne!(startup, shutdown);
    assert!(matches!(startup, SidecarError::StartupTimeout { .. }));
    assert!(matches!(shutdown, SidecarError::ShutdownFailure { .. }));
}

#[test]
fn invalid_transition_is_distinguishable_from_every_domain_error() {
    // Part 2 §8: a caller must be able to tell "the state machine
    // itself rejected this call" (a programmer/sequencing error) apart
    // from every contract-defined domain-failure category.
    let invalid = SidecarError::InvalidTransition {
        from: LifecycleState::NotStarted,
        to: LifecycleState::Running,
    };
    let domain_errors = [
        SidecarError::SpawnFailure {
            reason: "x".into(),
        },
        SidecarError::StartupTimeout {
            elapsed_ms: 1,
            limit_ms: 1,
        },
        SidecarError::HandshakeFailure { detail: "x".into() },
        SidecarError::HealthCheckFailure { detail: "x".into() },
        SidecarError::UnexpectedExit { exit_code: None },
        SidecarError::ShutdownFailure {
            elapsed_ms: 1,
            limit_ms: 1,
        },
        SidecarError::InvalidStartupOutput { detail: "x".into() },
    ];
    for err in &domain_errors {
        assert_ne!(&invalid, err);
        assert_ne!(invalid.code(), err.code());
    }
}
