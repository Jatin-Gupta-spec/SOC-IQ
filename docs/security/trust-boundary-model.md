# Trust Boundary Model

**Status:** Documentation Foundation (Phase 4A).
**Related:** Master Plan §6.2, ADR-010, `docs/contracts/frontend-backend-responsibility-boundaries.md`.

## CURRENT STATE

No cross-process trust boundary exists today — the current application is a single in-process
Python + PySide6 program (CONFIRMED, Master Plan §1.1). This document describes the target
boundary model that the migration introduces; there is no current-state trust-boundary
diagram to preserve or reference beyond this absence.

## TARGET STATE (PROPOSED)

```
UNTRUSTED: report files, IOC values, external TI API responses, frontend-originated input
TRUSTED (within its own boundary, least-privilege toward its neighbors):
  React        — trusted to render, untrusted to decide filesystem/network access
  Tauri/Rust   — trusted to enforce capabilities, untrusted to contain business logic
  Python core  — trusted to hold domain logic + validated data, untrusted input in = validated first
```

**What React may request:** invoke a fixed, versioned set of Tauri commands; call the local
backend's documented command endpoints; nothing else.

**What Tauri may execute:** the explicit native operations enumerated in its capability
config (open/save dialog, notification, credential-store read/write, sidecar lifecycle) —
nothing dynamically constructed from unvalidated frontend strings.

**What Rust may access:** filesystem paths returned by native dialogs or explicit
user-approved app-data directories — never an arbitrary frontend-supplied path trusted as-is.

**What Python may access:** its own SQLite file, its own app-data directory, and the network
only to configured, allow-listed TI provider endpoints.

## MIGRATION NOTES

This model is established as part of Phase 4E (Tauri foundation) and finalized/tested in
Phase 4M (security hardening) — a capability-manifest snapshot test
(`docs/testing/testing-architecture.md`) guards against silent boundary erosion after it's
established.

## UNKNOWN / REQUIRES VERIFICATION

None outstanding — this is a fresh target design with no current-state ambiguity to resolve.
