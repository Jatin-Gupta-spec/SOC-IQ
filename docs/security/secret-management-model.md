# Secret Management Model

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §22, ADR-008, `docs/architecture/17-secrets-configuration-architecture.md`.

## CURRENT STATE (CONFIRMED)

`ApplicationSettings.virustotal_api_key` (`app/settings/models.py`) is a plain `str` field.
A custom `__repr__` redacts it (`<redacted>`) from anywhere the default dataclass repr would
otherwise surface it — logs, debuggers, tracebacks. The **persisted** value remains plaintext
JSON on disk; nothing in `app/settings/repository.py` encrypts the written file.
Precise characterization: log-safe, disk-unsafe.

## TARGET STATE (PROPOSED)

- API key storage moves to OS secure storage: Windows Credential Manager (primary target),
  with a keychain/libsecret path noted for future macOS/Linux support.
- Rust owns credential-store read/write (see `tauri-capability-model.md`).
- Python receives the key at sidecar startup via a short-lived, process-scoped handoff (e.g.
  an environment variable set only for the child process) — Python never reads the OS
  keystore directly, and never persists the key to a Python-owned file.
- **Development fallback:** a `.env`-style local override for running the Python backend
  standalone during development, explicitly excluded from production packaging (Master Plan
  Top-10 security risks, #8: "secret-store fallback (dev `.env`) accidentally shipped in a
  release build" — named specifically as a risk to guard against, not just a convenience to
  build).
- The existing redacted `__repr__` is preserved unchanged as a defense-in-depth measure
  regardless of where the value is ultimately sourced from.

## MIGRATION NOTES

Implemented in Phase 4M. This is one of the more security-sensitive pieces of Phase 4M and is
tested explicitly (a test asserting the dev `.env` fallback path is excluded from production
builds is part of the Phase 4M exit criteria, alongside general security tests in
`docs/testing/testing-architecture.md`).

## UNKNOWN / REQUIRES VERIFICATION

None outstanding — current-state facts were directly confirmed by source read.
