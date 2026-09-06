//! [`SecretStore`] trait and its real, `keyring`-backed implementation.
//!
//! Mirrors `app/secrets/store.py`'s `SecretStore` protocol /
//! `KeyringSecretStore` class on the Python side of this project --
//! same four operations, same "no plaintext fallback path, ever"
//! guarantee, same `NotFound` vs `Unavailable` distinction. This
//! module does not implement, wrap, or invent any cryptography of its
//! own; like its Python counterpart, it only adapts the third-party
//! `keyring` crate's API to this project's shape and translates its
//! errors into [`KeystoreError`].

use crate::error::KeystoreError;

/// The `keyring` "service name" namespace every SOC-IQ secret is
/// stored under.
///
/// Deliberately identical to `app/secrets/store.py`'s
/// `_SERVICE_NAME` (`"SOC-IQ"`). The Python `keyring` library and the
/// Rust `keyring` crate both ultimately delegate to the same
/// platform-native store (Windows Credential Manager / macOS
/// Keychain / Secret Service), keyed by a `(service, account)` pair
/// at the OS level -- using the same service name means any
/// credential a user already stored via the current Python
/// implementation remains reachable, unchanged, once Part 1B routes
/// reads/writes through this Rust store instead. Changing this value
/// would silently orphan every credential stored before that cutover.
pub const SERVICE_NAME: &str = "SOC-IQ";

/// Maximum accepted length, in bytes, for a secret's `name` (the key
/// it is stored under, e.g. `"virustotal_api_key"` -- not the secret
/// value itself). Names in this project are short, static, code-level
/// identifiers, never user-supplied free text, so this is a
/// generous-but-real ceiling meant to catch malformed/unexpected
/// input before it reaches the platform backend (some of which have
/// their own, lower, platform-specific attribute-length limits that
/// surface as a less legible platform error if hit directly).
pub const MAX_NAME_LEN: usize = 256;

/// Structural contract for a secure, name-keyed secret store.
///
/// Every method is keyed by `name` -- a short, stable identifier for
/// *which* secret is being read or written, analogous to a dict key.
/// The store itself decides how (and where) the underlying value is
/// actually persisted; callers never see or choose that detail.
///
/// A trait (rather than a single concrete struct) so a future
/// integration test or caller can substitute a fake implementation
/// without depending on `keyring` at all -- the same reason
/// `app/secrets/store.py` defines `SecretStore` as a `Protocol`
/// rather than only shipping `KeyringSecretStore`.
pub trait SecretStore {
    /// Store `value` under `name`, replacing any existing value.
    ///
    /// Must not fail merely because a prior value already exists
    /// under `name` -- that is the normal "update" case, not an
    /// error.
    fn set_secret(&self, name: &str, value: &str) -> Result<(), KeystoreError>;

    /// Return the secret stored under `name`.
    ///
    /// # Errors
    /// - [`KeystoreError::NotFound`] -- no secret is currently stored
    ///   under `name`.
    /// - [`KeystoreError::Unavailable`] -- the underlying credential
    ///   store could not be consulted at all.
    fn get_secret(&self, name: &str) -> Result<String, KeystoreError>;

    /// Remove the secret stored under `name`, if any.
    ///
    /// Deleting a secret that was never configured is not an error --
    /// the end state (no secret stored under `name`) is identical
    /// either way, so this is idempotent by design.
    fn delete_secret(&self, name: &str) -> Result<(), KeystoreError>;

    /// Return whether a secret is currently stored under `name`,
    /// without exposing its value.
    fn has_secret(&self, name: &str) -> Result<bool, KeystoreError>;
}

/// [`SecretStore`] implementation backed by the OS-native credential
/// store, via the third-party `keyring` crate.
///
/// Holds no secret state itself -- every call is a direct pass-
/// through to `keyring`, which in turn delegates to whichever
/// platform backend is active (Windows Credential Manager / macOS
/// Keychain / Secret Service). There is no plaintext fallback path
/// anywhere in this struct: if `keyring` cannot reach a working
/// backend, every method returns
/// [`KeystoreError::Unavailable`] rather than silently degrading to
/// an insecure storage mechanism.
#[derive(Debug, Clone, Copy, Default)]
pub struct RustSecretStore;

impl RustSecretStore {
    /// Construct a store using the default `SOC-IQ` service
    /// namespace.
    pub fn new() -> Self {
        Self
    }

    fn entry(&self, name: &str) -> Result<keyring::Entry, KeystoreError> {
        validate_name(name)?;
        keyring::Entry::new(SERVICE_NAME, name).map_err(|error| KeystoreError::Unavailable {
            name: name.to_string(),
            reason: format!("could not construct a credential-store entry: {error}"),
        })
    }
}

impl SecretStore for RustSecretStore {
    fn set_secret(&self, name: &str, value: &str) -> Result<(), KeystoreError> {
        if value.is_empty() {
            return Err(KeystoreError::InvalidInput {
                reason: "secret value must not be empty".to_string(),
            });
        }

        let entry = self.entry(name)?;
        entry
            .set_password(value)
            .map_err(|error| KeystoreError::Unavailable {
                name: name.to_string(),
                reason: format!("the OS credential store rejected the write: {error}"),
            })
    }

    fn get_secret(&self, name: &str) -> Result<String, KeystoreError> {
        let entry = self.entry(name)?;
        match entry.get_password() {
            Ok(value) => Ok(value),
            Err(keyring::Error::NoEntry) => Err(KeystoreError::NotFound {
                name: name.to_string(),
            }),
            Err(error) => Err(KeystoreError::Unavailable {
                name: name.to_string(),
                reason: format!("the OS credential store could not be reached: {error}"),
            }),
        }
    }

    fn delete_secret(&self, name: &str) -> Result<(), KeystoreError> {
        let entry = self.entry(name)?;
        match entry.delete_password() {
            // Deleting an unconfigured secret is a defined no-op --
            // mirrors `app/secrets/store.py::KeyringSecretStore.
            // delete_secret`'s identical `NoEntry`-is-not-an-error
            // handling (with the same reasoning: `keyring`-family
            // libraries do not reliably distinguish "nothing to
            // delete" from certain backend rejections across every
            // platform backend, in either language's binding).
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(error) => Err(KeystoreError::Unavailable {
                name: name.to_string(),
                reason: format!("the OS credential store rejected the deletion: {error}"),
            }),
        }
    }

    fn has_secret(&self, name: &str) -> Result<bool, KeystoreError> {
        let entry = self.entry(name)?;
        match entry.get_password() {
            Ok(_) => Ok(true),
            Err(keyring::Error::NoEntry) => Ok(false),
            Err(error) => Err(KeystoreError::Unavailable {
                name: name.to_string(),
                reason: format!("the OS credential store could not be reached: {error}"),
            }),
        }
    }
}

/// Validate a secret `name` before it reaches the platform backend.
///
/// Rejects:
/// - empty names (a missing/blank identifier is always a caller bug,
///   never a legitimate "no name" request -- there is no operation
///   this trait defines that takes an optional name);
/// - names longer than [`MAX_NAME_LEN`];
/// - names containing anything other than ASCII alphanumerics, `_`,
///   `-`, or `.` -- names in this project are static, code-level
///   identifiers (e.g. `"virustotal_api_key"`), never user-supplied
///   free text, so this is deliberately narrow rather than
///   permissive: it exists specifically to reject malformed or
///   unexpected input (including control characters or embedded
///   null bytes that some platform C APIs handle unpredictably)
///   before any OS-keystore call is attempted, per the Part 1A
///   security-boundary requirement to validate the service/account
///   identifier and reject malformed input up front.
fn validate_name(name: &str) -> Result<(), KeystoreError> {
    if name.is_empty() {
        return Err(KeystoreError::InvalidInput {
            reason: "secret name must not be empty".to_string(),
        });
    }
    if name.len() > MAX_NAME_LEN {
        return Err(KeystoreError::InvalidInput {
            reason: format!(
                "secret name is {} bytes, exceeding the {MAX_NAME_LEN}-byte limit",
                name.len()
            ),
        });
    }
    if !name
        .chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '_' || c == '-' || c == '.')
    {
        return Err(KeystoreError::InvalidInput {
            reason: "secret name must contain only ASCII letters, digits, '_', '-', or '.'"
                .to_string(),
        });
    }
    Ok(())
}

// ---------------------------------------------------------------------
// Unit tests -- run against an in-process fake credential backend,
// never a real OS keystore.
//
// Mirrors `tests/fixtures/fake_secret_store.py`'s approach on the
// Python side of this project: a deterministic, in-memory test
// double with a `fail_next` escape hatch for simulating a real
// backend failure, rather than depending on a real OS credential
// store (unavailable in this sandbox -- see the existing Python-side
// environment note in `tests/test_integration_e2e.py`, which this
// crate's own `tests/real_backend_integration.rs` mirrors on the
// Rust side).
//
// This is a custom `keyring::CredentialBuilder`/`Credential`
// implementation, not `keyring::mock`, for one specific reason:
// `keyring::mock`'s `MockCredentialBuilder::build` returns a brand
// new, unlinked `MockCredential` on every call, with no persistence
// across separate `Entry::new()` calls for the same
// service/account. `RustSecretStore` (correctly, matching how a
// real OS credential store actually behaves -- persistence lives at
// the OS level, not in any particular `Entry` handle) constructs a
// fresh `keyring::Entry` inside every `SecretStore` method call, so
// a round trip through `RustSecretStore::set_secret` then
// `RustSecretStore::get_secret` exercises two different `Entry`
// instances. Against `keyring::mock` that would never see its own
// write. This fake keeps its state in a shared, process-wide map
// keyed by `(service, account)` instead, matching a real backend's
// actual persistence model.
// ---------------------------------------------------------------------
#[cfg(test)]
mod tests {
    use super::*;
    use std::any::Any;
    use std::collections::HashMap;
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::sync::{Mutex, OnceLock};

    /// Per-entry state in the fake backend: the persisted value (if
    /// any) and an optional one-shot simulated failure.
    #[derive(Default)]
    struct FakeSlot {
        value: Option<String>,
        fail_next_with: Option<String>,
    }

    type FakeMap = Mutex<HashMap<(String, String), FakeSlot>>;

    /// The single, process-wide fake backend store. A `OnceLock`
    /// (not one map per test) deliberately: `RustSecretStore`
    /// constructs a fresh `keyring::Entry` per call, and those calls
    /// must all resolve to the *same* underlying fake store for a
    /// round trip to be observable at all -- see the module doc
    /// above. Safe to share across every test in this module without
    /// collisions because every test asks for its own globally
    /// unique `name` via [`unique_name`], so distinct tests never
    /// address the same map key even though they share one map.
    fn fake_map() -> &'static FakeMap {
        static MAP: OnceLock<FakeMap> = OnceLock::new();
        MAP.get_or_init(|| Mutex::new(HashMap::new()))
    }

    /// Queue a one-shot simulated backend failure for the given
    /// `name`, consumed by whichever `RustSecretStore` method call
    /// (against the current `SERVICE_NAME`) touches it next.
    fn fail_next(name: &str, reason: &str) {
        let mut map = fake_map().lock().unwrap_or_else(|e| e.into_inner());
        map.entry((SERVICE_NAME.to_string(), name.to_string()))
            .or_default()
            .fail_next_with = Some(reason.to_string());
    }

    struct FakeCredential {
        key: (String, String),
    }

    impl keyring::credential::CredentialApi for FakeCredential {
        fn set_password(&self, password: &str) -> keyring::Result<()> {
            let mut map = fake_map().lock().unwrap_or_else(|e| e.into_inner());
            let slot = map.entry(self.key.clone()).or_default();
            if let Some(reason) = slot.fail_next_with.take() {
                return Err(keyring::Error::NoStorageAccess(reason.into()));
            }
            slot.value = Some(password.to_string());
            Ok(())
        }

        fn get_password(&self) -> keyring::Result<String> {
            let mut map = fake_map().lock().unwrap_or_else(|e| e.into_inner());
            let slot = map.entry(self.key.clone()).or_default();
            if let Some(reason) = slot.fail_next_with.take() {
                return Err(keyring::Error::NoStorageAccess(reason.into()));
            }
            slot.value.clone().ok_or(keyring::Error::NoEntry)
        }

        fn delete_password(&self) -> keyring::Result<()> {
            let mut map = fake_map().lock().unwrap_or_else(|e| e.into_inner());
            let slot = map.entry(self.key.clone()).or_default();
            if let Some(reason) = slot.fail_next_with.take() {
                return Err(keyring::Error::NoStorageAccess(reason.into()));
            }
            if slot.value.take().is_some() {
                Ok(())
            } else {
                Err(keyring::Error::NoEntry)
            }
        }

        fn as_any(&self) -> &dyn Any {
            self
        }
    }

    struct FakeCredentialBuilder;

    impl keyring::credential::CredentialBuilderApi for FakeCredentialBuilder {
        fn build(
            &self,
            _target: Option<&str>,
            service: &str,
            user: &str,
        ) -> keyring::Result<Box<keyring::credential::Credential>> {
            Ok(Box::new(FakeCredential {
                key: (service.to_string(), user.to_string()),
            }))
        }

        fn as_any(&self) -> &dyn Any {
            self
        }
    }

    /// Installs the fake credential builder exactly once for the
    /// whole test binary (`Once`, not per-test): every test needing a
    /// fresh install would race to overwrite the global default
    /// builder `keyring` itself uses
    /// (`set_default_credential_builder`'s own doc: "this will block
    /// waiting for all other threads currently creating entries to
    /// complete"), and a swap mid-run could hand two different
    /// `Entry`s created by the same logical round trip to two
    /// different builder instances. One install, shared
    /// [`fake_map`], globally unique [`unique_name`]s per test is
    /// both simpler and race-free.
    fn use_fake_backend() {
        static INIT: std::sync::Once = std::sync::Once::new();
        INIT.call_once(|| {
            keyring::set_default_credential_builder(Box::new(FakeCredentialBuilder));
        });
    }

    /// Every test needs its own, non-colliding `name` so tests
    /// sharing one process-wide [`fake_map`] never address the same
    /// key.
    fn unique_name(label: &str) -> String {
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let n = COUNTER.fetch_add(1, Ordering::Relaxed);
        format!("test_{label}_{n}")
    }

    #[test]
    fn set_then_get_round_trips_the_value() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("round_trip");

        store.set_secret(&name, "s3cr3t-value").unwrap();
        let value = store.get_secret(&name).unwrap();

        assert_eq!(value, "s3cr3t-value");
    }

    #[test]
    fn get_on_missing_secret_is_not_found() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("missing_get");

        let err = store.get_secret(&name).unwrap_err();

        assert!(matches!(err, KeystoreError::NotFound { .. }));
    }

    #[test]
    fn has_secret_reflects_presence_without_erroring() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("has_secret");

        assert_eq!(store.has_secret(&name).unwrap(), false);

        store.set_secret(&name, "value").unwrap();
        assert_eq!(store.has_secret(&name).unwrap(), true);
    }

    #[test]
    fn delete_removes_the_secret() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("delete");

        store.set_secret(&name, "value").unwrap();
        store.delete_secret(&name).unwrap();

        assert!(matches!(
            store.get_secret(&name).unwrap_err(),
            KeystoreError::NotFound { .. }
        ));
    }

    #[test]
    fn delete_on_missing_secret_is_a_no_op_not_an_error() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("delete_missing");

        // Idempotent by design -- see `SecretStore::delete_secret`'s
        // own doc comment.
        store.delete_secret(&name).unwrap();
        store.delete_secret(&name).unwrap();
    }

    #[test]
    fn set_then_overwrite_replaces_the_value() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("overwrite");

        store.set_secret(&name, "first").unwrap();
        store.set_secret(&name, "second").unwrap();

        assert_eq!(store.get_secret(&name).unwrap(), "second");
    }

    #[test]
    fn empty_name_is_rejected_before_touching_the_backend() {
        use_fake_backend();
        let store = RustSecretStore::new();

        let err = store.set_secret("", "value").unwrap_err();
        assert!(matches!(err, KeystoreError::InvalidInput { .. }));

        let err = store.get_secret("").unwrap_err();
        assert!(matches!(err, KeystoreError::InvalidInput { .. }));
    }

    #[test]
    fn oversized_name_is_rejected() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = "x".repeat(MAX_NAME_LEN + 1);

        let err = store.set_secret(&name, "value").unwrap_err();
        assert!(matches!(err, KeystoreError::InvalidInput { .. }));
    }

    #[test]
    fn name_with_invalid_characters_is_rejected() {
        use_fake_backend();
        let store = RustSecretStore::new();

        for bad_name in ["has space", "has/slash", "has\nnewline", "has\0null"] {
            let err = store.set_secret(bad_name, "value").unwrap_err();
            assert!(
                matches!(err, KeystoreError::InvalidInput { .. }),
                "expected {bad_name:?} to be rejected"
            );
        }
    }

    #[test]
    fn empty_value_is_rejected_on_set() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("empty_value");

        let err = store.set_secret(&name, "").unwrap_err();

        assert!(matches!(err, KeystoreError::InvalidInput { .. }));
    }

    #[test]
    fn backend_failure_on_get_surfaces_as_unavailable_not_not_found() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("backend_failure_get");

        fail_next(&name, "simulated backend failure");

        let err = store.get_secret(&name).unwrap_err();

        assert!(matches!(err, KeystoreError::Unavailable { .. }));
    }

    #[test]
    fn backend_failure_on_set_surfaces_as_unavailable() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("backend_failure_set");

        fail_next(&name, "simulated backend failure");

        let err = store.set_secret(&name, "value").unwrap_err();

        assert!(matches!(err, KeystoreError::Unavailable { .. }));
    }

    #[test]
    fn backend_failure_on_delete_of_an_existing_secret_surfaces_as_unavailable() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("backend_failure_delete");

        store.set_secret(&name, "value").unwrap();
        fail_next(&name, "simulated backend failure");

        let err = store.delete_secret(&name).unwrap_err();

        assert!(matches!(err, KeystoreError::Unavailable { .. }));
    }

    #[test]
    fn error_display_never_contains_the_secret_value() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("no_leak");
        let secret_value = "super-secret-do-not-leak-XJ9Q";

        store.set_secret(&name, secret_value).unwrap();
        fail_next(&name, "simulated backend failure");

        let err = store.get_secret(&name).unwrap_err();
        let rendered = err.to_string();

        assert!(!rendered.contains(secret_value));
    }

    #[test]
    fn not_found_error_display_never_contains_a_stray_secret_value() {
        use_fake_backend();
        let store = RustSecretStore::new();
        let name = unique_name("not_found_display");

        let err = store.get_secret(&name).unwrap_err();
        let rendered = err.to_string();

        // Nothing secret was ever set for this name -- this asserts
        // the *shape* of the message (contains the identifying name,
        // not a value) rather than the absence of a specific string.
        assert!(rendered.contains(&name));
    }
}
