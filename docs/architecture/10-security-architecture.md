# Security Architecture (Overview)

**Status:** Documentation Foundation (Phase 4A). This document is a short entry point;
full detail lives in `docs/security/`.
**Related:** Master Plan §6, ADR-010.

## Purpose

This overview exists so a reader doesn't have to open eight separate `docs/security/`
documents to understand the shape of SOC-IQ's security posture. Each row below links to the
document with full detail.

## CURRENT STATE

CONFIRMED (prior audit + this pass): no `subprocess`/`eval`/`exec`/`pickle`/`shell=True`
usage in `app/`; parameterized SQL throughout the database repository; API key redacted from
the settings dataclass's `__repr__` (log-safe) but stored in plaintext JSON on disk
(disk-unsafe) — see `17-secrets-configuration-architecture.md`. There is currently no
cross-process trust boundary at all, because there is currently no cross-process architecture
(single Python process, PySide6 in-process UI).

## TARGET STATE (PROPOSED) — summary table

| Document | Covers |
|---|---|
| `docs/security/threat-model.md` | Enumerated threats and their owning mitigation layer |
| `docs/security/trust-boundary-model.md` | What each layer (React/Tauri/Python) is trusted vs. untrusted to do |
| `docs/security/tauri-capability-model.md` | Explicit least-privilege Tauri permission manifest |
| `docs/security/secret-management-model.md` | OS-backed API key storage |
| `docs/security/ipc-security-model.md` | Loopback binding, command validation, no frontend network access |
| `docs/security/filesystem-security-model.md` | Path-traversal prevention, native-dialog-only writes |
| `docs/security/report-ingestion-security-model.md` | Untrusted-file handling, size caps, regex-DoS posture |
| `docs/security/dependency-supply-chain-security-model.md` | Lockfiles, auditing, SBOM |

**Two invariants preserved from the Master Plan, explicitly, in every one of the above:**

1. **`NOT_FOUND != CLEAN`** — a threat-intel provider's "no record found" must never be
   displayed or stored as equivalent to "checked and clean." See
   `08-threat-intelligence-architecture.md` and `docs/security/threat-model.md`.
2. **The frontend has no direct filesystem or network access** — every filesystem write goes
   through a Tauri command behind a native dialog; every network call goes through the Python
   sidecar's allow-listed provider endpoints. See `docs/security/trust-boundary-model.md` and
   `docs/security/filesystem-security-model.md`.

## MIGRATION NOTES

Security hardening (capability manifest finalization, secret-store wiring, security test
suite) is Phase 4M (Master Plan §26) — after the IPC contract and Tauri foundation exist, but
before full frontend/backend integration (Phase 4N) ships.

## UNKNOWN / REQUIRES VERIFICATION

See the individual `docs/security/` documents for subsystem-specific unknowns; none are
resolved by this overview document.
