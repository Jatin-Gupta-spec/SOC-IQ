// Thin Tauri command adapter over `keystore_core` (ADR-008: "Rust
// owns OS keystore access").
//
// Phase 4O Security Part 1A scope only. This module exposes the four
// `keystore_core::SecretStore` operations as `#[tauri::command]`s so
// Part 1B has a real, callable target to migrate
// `app/secrets/store.py` onto. It deliberately does NOT:
//   - call these commands from anywhere in this checkpoint (no
//     frontend wiring, no `SettingsService`/`VirusTotalClient`
//     integration on the Rust or Python side) -- establishing the
//     capability is Part 1A's job; using it to replace the existing
//     Python `keyring` flow is Part 1B's (see the Part 1A brief,
//     "PART 1A SCOPE");
//   - implement the Rust -> Python short-lived handoff ADR-008
//     describes for sidecar startup -- also Part 1B;
//   - hold any credential-related state in `SidecarState` or
//     anywhere else -- `keystore_core::RustSecretStore` is a
//     zero-sized, stateless adapter over the OS credential store
//     (the store's actual persistence lives entirely in the OS, not
//     in this process), so each command constructs one locally
//     rather than adding a fifth field to `SidecarState` for no
//     reason (ADR-004: Rust's credential-store responsibility is
//     narrow and does not imply it needs to become a shared,
//     managed piece of application state).
//
// Real Rust-side behavior (validation, the `NotFound`/`Unavailable`
// distinction, "never log a secret value") lives in `keystore_core`
// itself and is unit-tested there (see that crate's `src/store.rs`).
// This file's only job is the IPC boundary: accept/return plain
// `String`/`bool` values Tauri's `invoke_handler` can (de)serialize,
// and turn `keystore_core::KeystoreError` into a `String` a frontend
// caller can display -- `KeystoreError`'s own `Display` impl already
// guarantees that string never contains a secret value (see that
// type's doc comment), so no additional redaction is needed here.
//
// Per `docs/contracts/ipc-rules.md` rule 3 / ADR-004: this file
// performs a native-capability operation and nothing else -- no
// domain logic, no decision about *which* secret name to use for
// *what* (that remains an application-layer concern, on whichever
// side of the IPC boundary Part 1B ultimately puts it).

use keystore_core::{KeystoreError, RustSecretStore, SecretStore};

fn store() -> RustSecretStore {
    RustSecretStore::new()
}

/// Store `value` under `name` in the OS-native credential store,
/// replacing any existing value under that name.
///
/// `value` is passed through Tauri's IPC boundary as a plain
/// `String`, exactly the way `analyze_report`'s existing
/// `report_path` payload already is (`docs/contracts/ipc-rules.md`) --
/// consistent with the rest of this crate's command surface, not a
/// new pattern. Tauri IPC is process-local (webview <-> the app's
/// own Rust process, over the OS's own inter-process channel, not a
/// network socket), the same boundary every other command in this
/// crate already crosses.
#[tauri::command]
pub fn keystore_set_secret(name: String, value: String) -> Result<(), String> {
    store()
        .set_secret(&name, &value)
        .map_err(describe_error)
}

/// Retrieve the secret currently stored under `name`.
///
/// Returns `Err` (not a magic sentinel value) when nothing is stored
/// under `name` -- callers that only need to know *whether* a
/// credential is configured should use [`keystore_has_secret`]
/// instead, exactly as `app/secrets/store.py`'s `SecretStore`
/// protocol already documents on the Python side, so a "just
/// checking" caller never needlessly pulls the plaintext secret
/// across the IPC boundary at all.
#[tauri::command]
pub fn keystore_get_secret(name: String) -> Result<String, String> {
    store().get_secret(&name).map_err(describe_error)
}

/// Remove the secret stored under `name`, if any. Idempotent: deleting
/// an unconfigured secret is not an error (see
/// `keystore_core::SecretStore::delete_secret`'s doc comment).
#[tauri::command]
pub fn keystore_delete_secret(name: String) -> Result<(), String> {
    store()
        .delete_secret(&name)
        .map_err(describe_error)
}

/// Return whether a secret is currently stored under `name`, without
/// exposing its value.
#[tauri::command]
pub fn keystore_has_secret(name: String) -> Result<bool, String> {
    store().has_secret(&name).map_err(describe_error)
}

/// Render a [`KeystoreError`] as a frontend-displayable `String`.
///
/// A thin wrapper around `KeystoreError`'s own `Display` impl (rather
/// than inlining `.to_string()` at all four call sites above) so
/// there is exactly one place this crate's IPC boundary turns a
/// keystore error into IPC-safe text, matching this file's own
/// module-doc claim about where that guarantee lives.
fn describe_error(error: KeystoreError) -> String {
    error.to_string()
}

// `generate_handler!` requires each command to be named directly at
// its own call site in `lib.rs` (it is a macro, not a runtime list),
// so the four commands above are registered there, alongside this
// crate's two existing commands -- see `lib.rs`'s
// `.invoke_handler(tauri::generate_handler![...])` call.

#[cfg(test)]
mod tests {
    use super::*;

    // These exercise the IPC-boundary error formatting only --
    // `keystore_core`'s own test suite (that crate's `src/store.rs`)
    // is what actually proves store/retrieve/delete/validation
    // behavior; duplicating that here would test the same thing
    // twice through a thinner interface. What *is* this module's own
    // responsibility, and so what belongs here, is: does invoking
    // these commands' underlying logic produce the same
    // `Result<_, String>` shape the frontend actually receives, and
    // does that `String` still contain no secret value.
    //
    // Note: like `keystore_core`'s own unit tests, these run against
    // whatever `keyring` credential builder is currently installed
    // process-wide. This crate does not install a fake backend
    // itself (it has no test-only dependency for one, deliberately,
    // per this checkpoint's "smallest necessary abstraction"
    // instruction) -- these tests are therefore validation-path-only
    // assertions that do not require a real OS keystore to be
    // meaningful, not full round-trip coverage (that coverage
    // already exists, and is real, in `keystore_core`).
    #[test]
    fn set_secret_rejects_empty_name_without_touching_any_backend() {
        let result = keystore_set_secret(String::new(), "value".to_string());
        assert!(result.is_err());
    }

    #[test]
    fn get_secret_rejects_empty_name_without_touching_any_backend() {
        let result = keystore_get_secret(String::new());
        assert!(result.is_err());
    }

    #[test]
    fn error_strings_from_invalid_input_never_contain_the_attempted_value() {
        let secret_value = "do-not-leak-this-value-9F3K";
        let result = keystore_set_secret(String::new(), secret_value.to_string());
        let message = result.unwrap_err();
        assert!(!message.contains(secret_value));
    }
}
