//! Framework-independent Rust-owned OS-keystore core.
//!
//! Phase 4O Security Part 1A -- audit + Rust ownership implementation
//! (ADR-008: "Rust owns OS keystore access").
//!
//! # Why this is its own crate
//!
//! This crate follows the exact split already established by
//! `sidecar-core` in this project: a framework-independent core with
//! no Tauri dependency, buildable and testable on its own, plus a
//! thin adapter (`src-tauri/src/keystore.rs`) that exposes it as
//! `#[tauri::command]`s. That split exists here for the identical
//! reason it already exists for `sidecar-core` -- see that crate's
//! own module doc -- and additionally because `src-tauri`'s
//! `tauri = "2"` dependency graph does not currently build under
//! this workspace's floor toolchain in this environment (a
//! pre-existing condition, not introduced by this checkpoint; see
//! this crate's Cargo.toml `rust-version` comment and the Phase 4O
//! Security Part 1A report's "Environment" section). Keeping the
//! real keystore logic in a crate that *does* build here means it
//! has real, run `cargo test` coverage rather than being written
//! blind against a graph nothing in this environment can compile.
//!
//! # Scope (Part 1A)
//!
//! This crate establishes the Rust side of ADR-008 only:
//!
//! - a narrow [`SecretStore`] trait (store / retrieve / delete /
//!   check-existence), deliberately shaped to match the seam
//!   `app/secrets/store.py`'s `SecretStore` protocol already uses on
//!   the Python side, so Part 1B's eventual Python-to-Rust handoff
//!   has a matching vocabulary on both ends;
//! - [`RustSecretStore`], the real implementation, backed by the
//!   `keyring` crate (the same third-party, platform-appropriate
//!   abstraction Python's `keyring` library already wraps -- see
//!   Cargo.toml for the exact platform backends selected and why);
//! - input validation and an error type that never carries a secret
//!   value in its `Display` output.
//!
//! It does **not** implement the Tauri command surface's actual
//! wiring into application state, does not touch
//! `app/secrets/store.py` or any other Python file, and does not
//! implement the Part 1B Python-to-Rust handoff itself. See
//! `src-tauri/src/keystore.rs` for the thin command adapter that
//! *does* exist in this checkpoint, and the Part 1A report for the
//! full list of what is deliberately deferred to Part 1B.

mod error;
mod store;

pub use error::KeystoreError;
pub use store::{RustSecretStore, SecretStore, MAX_NAME_LEN, SERVICE_NAME};
