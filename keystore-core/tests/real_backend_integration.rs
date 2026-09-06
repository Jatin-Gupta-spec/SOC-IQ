//! Environment-dependent integration tests -- exercise
//! [`keystore_core::RustSecretStore`] against a **real** OS
//! credential-store backend (Windows Credential Manager / macOS
//! Keychain / Secret Service), not the in-process fake used by
//! `src/store.rs`'s unit tests.
//!
//! Deliberately kept in a separate test binary (`tests/`, not
//! `#[cfg(test)] mod tests` inside `src/store.rs`) and every test
//! here is `#[ignore]`, per the Part 1A brief's instruction to keep
//! unit tests and environment-dependent integration tests separate
//! rather than faking an integration test. `cargo test` (this
//! checkpoint's regression check) does **not** run these; they
//! require `cargo test -- --ignored` on a machine with a real,
//! working, unlocked OS credential-store backend.
//!
//! This sandbox has no such backend at all -- the identical
//! environment limitation already documented on the Python side, in
//! `tests/test_integration_e2e.py`:
//! > this sandbox has no OS keyring backend at all
//! > (`keyring.errors.NoKeyringError`...)
//! These tests were written but **not run** in this environment for
//! that reason; see the Part 1A report's "Tests" section for the
//! exact `PASS`/`FAIL`/`BLOCKED` accounting.
//!
//! Every test cleans up after itself (`delete_secret` at the end,
//! even on assertion failure paths where feasible) so repeated runs
//! against a real backend do not accumulate leftover `SOC-IQ`
//! credential-store entries.

use keystore_core::{RustSecretStore, SecretStore};

fn unique_name(label: &str) -> String {
    // Real backends persist across process runs (unlike the unit
    // tests' in-process fake), so a timestamp-based suffix is used
    // rather than a process-local counter, to avoid colliding with
    // a leftover entry from a previous run that failed before its
    // own cleanup ran.
    let nanos = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_nanos())
        .unwrap_or(0);
    format!("integration_test_{label}_{nanos}")
}

#[test]
#[ignore = "requires a real OS credential-store backend; run with `cargo test -- --ignored`"]
fn set_then_get_round_trips_against_the_real_backend() {
    let store = RustSecretStore::new();
    let name = unique_name("round_trip");

    store.set_secret(&name, "integration-test-value").unwrap();
    let result = store.get_secret(&name);

    // Clean up before asserting, so a failed assertion still doesn't
    // leave the entry behind.
    let _ = store.delete_secret(&name);

    assert_eq!(result.unwrap(), "integration-test-value");
}

#[test]
#[ignore = "requires a real OS credential-store backend; run with `cargo test -- --ignored`"]
fn delete_against_the_real_backend_removes_the_entry() {
    let store = RustSecretStore::new();
    let name = unique_name("delete");

    store.set_secret(&name, "value").unwrap();
    store.delete_secret(&name).unwrap();

    assert!(!store.has_secret(&name).unwrap());
}

#[test]
#[ignore = "requires a real OS credential-store backend; run with `cargo test -- --ignored`"]
fn get_on_a_name_never_stored_on_this_backend_is_not_found() {
    let store = RustSecretStore::new();
    let name = unique_name("never_stored");

    let result = store.get_secret(&name);

    assert!(matches!(
        result,
        Err(keystore_core::KeystoreError::NotFound { .. })
    ));
}
