# ADR-010: Least-Privilege Security Capability Boundaries

**Status:** Proposed
**Related:** Master Plan §28, §6, §7, and the full `docs/security/` document set.

## Context

The current architecture has no cross-process trust boundary (single in-process PySide6
application). The target architecture introduces three distinct trust domains — React
(webview), Tauri/Rust (native shell), Python (domain core) — each capable, in principle, of
different levels of harm if compromised or misused.

## Problem

Without an explicit, declared capability model, a webview-based frontend could be granted
broad filesystem or network access "for convenience" during implementation, defeating the
security benefit of introducing a native shell boundary in the first place.

## Decision

Explicit least-privilege boundaries, declared and enforced at the Tauri capability-manifest
level (not left as an implicit convention):

- React may request: a fixed, versioned set of Tauri commands, and the local backend's
  documented command endpoints — nothing else.
- Tauri may execute: only the native operations enumerated in its capability config, with no
  dynamically-constructed operations built from unvalidated frontend strings.
- Rust may access: filesystem paths returned by native dialogs or explicit user-approved
  app-data directories — never an arbitrary frontend-supplied path trusted as-is.
- Python may access: its own SQLite file, its own app-data directory, and only
  allow-listed threat-intel provider hosts over the network.

Two invariants are treated as non-negotiable across every layer of this boundary:
**`NOT_FOUND != CLEAN`** (data-model integrity — see ADR-007) and **the frontend has no
direct filesystem or network access** (capability integrity — this ADR).

## Alternatives Considered

- **Grant the frontend broad `fs:*`/`http:*` Tauri capabilities and rely on code review to
  prevent misuse.** Rejected — code review is not a substitute for a structurally-enforced
  boundary, and is explicitly named as a "do not do this" item (Master Plan §30.H: "do not
  grant Tauri `shell:*` or unrestricted `fs:*` capabilities").

## Rejected Alternatives (explicit)

Trusting frontend-supplied file paths directly for export writes instead of requiring a
native dialog result — rejected; named explicitly as a top security risk in the Master Plan's
risk list (#3: "export path trusted from frontend input instead of native dialog result").

## Consequences

- Positive: a compromised or buggy frontend (e.g. via a malicious dependency) cannot, by
  itself, read/write arbitrary files or reach arbitrary network hosts — it is structurally
  contained by the capability manifest.
- Negative: every new frontend feature that needs a native capability requires an explicit,
  reviewed capability-manifest change — a deliberate friction point, not an oversight.

## Security Implications

This ADR is itself a security document; its full elaboration lives across
`docs/security/trust-boundary-model.md`, `docs/security/tauri-capability-model.md`,
`docs/security/ipc-security-model.md`, and `docs/security/filesystem-security-model.md`.

## Migration Implications

The capability manifest is finalized in Phase 4M (security hardening), with a
capability-manifest snapshot test (see `docs/testing/testing-architecture.md`) added so a
future PR cannot silently widen permissions without the change being visible in review.
