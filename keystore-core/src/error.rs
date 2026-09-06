//! Error type for [`crate::SecretStore`].
//!
//! Deliberately mirrors the shape of `app.secrets.exceptions` on the
//! Python side of this project (`SecretNotFoundError` vs
//! `SecretStoreUnavailableError` as genuinely distinct outcomes, not
//! collapsed into one "it didn't work" case) -- not because Part 1A
//! wires the two together (it does not; see the crate root doc), but
//! so Part 1B's eventual handoff maps cleanly onto an already-familiar
//! shape rather than inventing a second, differently-cut error
//! taxonomy for the same underlying distinctions.

use std::fmt;

/// Errors returned by [`crate::SecretStore`] methods.
///
/// **Never carries a secret value.** Every variant's [`Display`]
/// output is safe to print, log, or return to a caller as-is: none of
/// them interpolate the credential value being stored/retrieved, only
/// the `name` a secret is keyed by (an identifier like
/// `"virustotal_api_key"`, not a secret itself) and, where relevant,
/// a platform error's own message (which the `keyring` crate itself
/// documents as containing no secret material -- platform failures
/// are reported as store/backend-level failures, not value-level
/// ones).
#[derive(Debug)]
pub enum KeystoreError {
    /// No secret is currently stored under the given name. An
    /// ordinary, expected outcome (e.g. the credential was never
    /// configured) -- not evidence the store itself is broken.
    NotFound { name: String },

    /// The underlying OS credential store could not be reached or
    /// used at all (service disabled, corrupted keystore, unsupported
    /// platform backend, permission failure, a genuine backend
    /// rejection of a delete, etc.). Distinct from `NotFound`: this
    /// means the store could not be consulted, not that it was
    /// consulted and found empty.
    Unavailable { name: String, reason: String },

    /// The `name` (or other request input) failed validation before
    /// any OS credential-store call was attempted -- empty, too long,
    /// or containing characters that are not valid identifier
    /// characters. Caught here, before it ever reaches the platform
    /// backend, so a malformed request never becomes a confusing
    /// platform-level failure.
    InvalidInput { reason: String },
}

impl fmt::Display for KeystoreError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            KeystoreError::NotFound { name } => {
                write!(f, "no secret is stored under {name:?}")
            }
            KeystoreError::Unavailable { name, reason } => {
                write!(
                    f,
                    "the OS credential store could not be used for {name:?}: {reason}"
                )
            }
            KeystoreError::InvalidInput { reason } => {
                write!(f, "invalid keystore request: {reason}")
            }
        }
    }
}

impl std::error::Error for KeystoreError {}
