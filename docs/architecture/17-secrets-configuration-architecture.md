# Secrets / Configuration Architecture

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §22, §1.6 (current-state fact), ADR-008, and
`docs/security/secret-management-model.md`.

## CURRENT STATE (CONFIRMED from source)

`app/settings/models.py::ApplicationSettings.virustotal_api_key` is a plain `str` field. A
custom `__repr__` override redacts it (`<redacted>`) from anywhere the dataclass's default
repr would otherwise appear — logs, debuggers, exception tracebacks. This is a real, working
mitigation for *accidental* leakage via logging. However, the underlying **persisted** value
is still plaintext JSON on disk — nothing in `app/settings/repository.py` encrypts the
written file. Precise characterization: **log-safe, disk-unsafe** (CONFIRMED by direct source
read; more precise than "no protection at all," and the existing redaction work is preserved,
not discarded, in the target design below).

## TARGET STATE (PROPOSED)

- The API key moves from plaintext settings JSON to the OS secure store — Windows Credential
  Manager on Windows (the confirmed primary packaging target, see
  `18-packaging-release-architecture.md`), with a keychain/libsecret path noted for future
  macOS/Linux support.
- Rust owns the credential-store read/write (a native capability — see
  `04-tauri-rust-architecture.md` and `docs/security/tauri-capability-model.md`); Python
  receives the key at sidecar startup via a local, short-lived handoff (e.g. an environment
  variable set only for the child process, never written to a Python-owned file) rather than
  Python touching the OS keystore API directly — this keeps "who can read the keystore" to
  one, audited, native layer.
- A `.env`-style local override remains available for running the Python backend standalone
  during development, explicitly excluded from production packaging.
- The existing redacted `__repr__` on `ApplicationSettings` is **preserved unchanged**
  regardless of where the value is ultimately sourced from — it remains a defense-in-depth
  measure even after the underlying storage mechanism improves.

## MIGRATION NOTES

Secret-store wiring is part of Phase 4M (security hardening, Master Plan §26), alongside the
Tauri capability manifest finalization.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding — the current plaintext-storage/redacted-repr behavior was directly
confirmed by source read of `app/settings/models.py`.
