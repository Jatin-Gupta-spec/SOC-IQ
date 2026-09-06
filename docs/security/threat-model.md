# Threat Model

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §6, ADR-007 (NOT_FOUND != CLEAN), ADR-010,
`docs/architecture/10-security-architecture.md`.

## CURRENT STATE

CONFIRMED (prior audit + this documentation pass, direct source read): no
`subprocess`/`eval`/`exec`/`pickle`/`shell=True` usage anywhere in `app/`; parameterized SQL
throughout `app/database/repository.py`. These are real, existing mitigations against
code-injection and SQL-injection classes of threat, and are preserved unchanged as a baseline
discipline extended into the target architecture (see MIGRATION NOTES).

## TARGET STATE (PROPOSED) — enumerated threats and owning mitigation

| Threat | Mitigation / owning layer |
|---|---|
| Malicious report file crafted to exploit a parser | Extraction runs only in the Python sidecar; size caps + timeout on parsing; never executed, never shelled out |
| Malicious URL/domain/IP as IOC | Treated as inert data end-to-end; never used to construct shell commands or rendered as auto-clickable |
| Oversized report / regex DoS | Input size limits at the API boundary; extraction/scoring regexes reviewed for catastrophic backtracking during Phase 4B hardening |
| Path traversal on export | Export path resolution happens in Rust/Tauri's capability-scoped filesystem API, never by trusting a frontend-supplied string directly (see `filesystem-security-model.md`) |
| API-key theft | Key lives in OS secure storage (`docs/architecture/17-secrets-configuration-architecture.md`), never sent to the frontend, never logged |
| Frontend compromise (malicious/compromised JS dependency) | Frontend has zero direct filesystem/network capability beyond the local backend origin and whitelisted Tauri commands (`trust-boundary-model.md`) |
| IPC/command abuse | All commands schema-validated server-side before touching domain logic (`docs/contracts/ipc-rules.md`, rule 4) |
| Malicious Tauri command misuse | Capability manifest enumerates exactly the allowed commands per window (`tauri-capability-model.md`) |
| Dependency/supply-chain attack | Lockfiles + auditing across all three ecosystems (`dependency-supply-chain-security-model.md`) |

## Two Preserved Invariants (explicit, non-negotiable per Master Plan)

1. **`NOT_FOUND != CLEAN`** — a threat-intel provider's "no record" must never be treated as
   equivalent to "checked, clean." Conflating the two would give an analyst false assurance
   about an IOC that was simply never checked. See ADR-007 and
   `docs/architecture/08-threat-intelligence-architecture.md`.
2. **The frontend has no direct filesystem or network access.** Every filesystem write
   routes through a Tauri command behind a native dialog; every network call routes through
   the Python sidecar's allow-listed provider hosts. See `trust-boundary-model.md` and
   `filesystem-security-model.md`.

## MIGRATION NOTES

The existing no-`shell=True`/no-`eval`/no-`exec` discipline in Python (CONFIRMED above) is
explicitly extended as a cross-language rule during migration — Rust code is held to the same
standard (no dynamic shell construction from untrusted input), not just Python.

## UNKNOWN / REQUIRES VERIFICATION

Whether extraction/scoring regexes have been specifically audited for catastrophic
backtracking is **UNKNOWN — VERIFY IN PHASE 4B**; not claimed as already-mitigated above,
only planned as a Phase 4B hardening task.
