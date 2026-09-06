# ADR-008: API Keys Stored via OS Secure Storage

**Status:** Proposed
**Implementation note (added during later documentation reconciliation):** ADR status
(Proposed) and implementation state are two different things. Source inspection in later
sessions confirms the decision this ADR describes has been implemented: `keystore-core`
(Rust) owns OS-keystore read and write; `src-tauri/src/keystore.rs` registers
`keystore_get_secret`/`keystore_set_secret`/`keystore_delete_secret`/`keystore_has_secret`
as Tauri commands; the modern Settings UI (`VirustotalControl.tsx` →
`useVirustotalKeySave.ts`) calls the write path; Python is read-only by construction
(`app/secrets/store.py`), observing only a process-scoped environment-variable handoff at
sidecar startup — no `keyring` dependency remains in `requirements.txt` or `app/`; no
plaintext credential persistence remains in `config/settings.json`. This note records
implementation reality; it does not change this ADR's governance status.
**Related:** Master Plan §28, §22, §1.6, and
`docs/architecture/17-secrets-configuration-architecture.md`,
`docs/security/secret-management-model.md`.

## Context

`ApplicationSettings.virustotal_api_key` is currently a plaintext `str` field, persisted to
disk as plaintext JSON, with a `__repr__` override that redacts it from logs/tracebacks only
(CONFIRMED — log-safe, disk-unsafe; matches baseline problem #8, precisely characterized).

## Problem

Plaintext-on-disk API key storage means any process or user with filesystem read access to
the settings file can read the key, regardless of how well logging is protected.

## Decision

The API key moves to OS-native secure storage (Windows Credential Manager as the primary
target, with a keychain/libsecret path noted for future macOS/Linux support). Rust, as the
sole native-capability layer (ADR-004), owns the credential-store read/write. Python receives
the key at sidecar startup via a short-lived process-scoped handoff (e.g. an environment
variable set only for the child process), never reading the OS keystore itself and never
writing the key to a Python-owned file.

## Alternatives Considered

- **Encrypt the settings JSON file with a locally-generated key.** Rejected as strictly worse
  than OS secure storage — an application-managed encryption key has to be stored somewhere
  too, which just relocates the problem rather than solving it; OS credential stores exist
  specifically to avoid this circularity.
- **Python reads the OS keystore directly (e.g. via a cross-platform Python keyring
  library).** Rejected in favor of routing through Rust — keeping "who can read the keystore"
  to one, audited, native layer is simpler to reason about and test than allowing two
  languages independent keystore access.

## Rejected Alternatives (explicit)

Leaving the key in plaintext settings JSON and relying solely on OS-level file permissions —
rejected; file permissions are a weaker, more easily misconfigured guarantee than a
purpose-built OS credential store.

## Consequences

- Positive: closes baseline problem #8 with a standard, well-understood mechanism rather than
  a custom one.
- Negative: adds a Rust↔Python handoff step at sidecar startup that doesn't exist in the
  current architecture, and ties key storage to the Tauri/Rust layer being functional.

## Security Implications

This is itself a security architecture decision — see
`docs/security/secret-management-model.md` for the full model, including the development-mode
`.env` fallback and its explicit exclusion from production builds.

## Migration Implications

Implemented in Phase 4M (security hardening, Master Plan §26). The existing redacted
`__repr__` on `ApplicationSettings` is preserved unchanged throughout — it remains a valid
defense-in-depth measure independent of where the underlying value is sourced from.
